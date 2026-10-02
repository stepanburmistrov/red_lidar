"""ROSiK LiDAR UART framing and scan decoding."""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Iterable, List, Sequence, Tuple

MAGIC = b"RLDR"
VERSION = 1
MSG_SCAN = 1
MSG_INTENSITY = 2
HEADER_STRUCT = struct.Struct("<4sBBHII")
FRAME_STRUCT = struct.Struct("<HH8H")
CRC_STRUCT = struct.Struct("<H")
MAX_PAYLOAD = 64 * FRAME_STRUCT.size


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Packet:
    msg_type: int
    sequence: int
    timestamp_ms: int
    payload: bytes


@dataclass(frozen=True)
class ScanPoint:
    angle_deg: float
    distance_m: float
    intensity: float = 0.0


def crc16(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc & 0xFFFF


def build_packet(msg_type: int, sequence: int, timestamp_ms: int, payload: bytes) -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    header = HEADER_STRUCT.pack(MAGIC, VERSION, msg_type, len(payload), sequence, timestamp_ms)
    checksum = crc16(header[4:] + payload)
    return header + payload + CRC_STRUCT.pack(checksum)


class StreamParser:
    """Incremental parser that recovers automatically after noise or partial reads."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.crc_errors = 0
        self.header_errors = 0

    def feed(self, data: bytes) -> List[Packet]:
        self._buf.extend(data)
        out: List[Packet] = []

        while True:
            pos = self._buf.find(MAGIC)
            if pos < 0:
                # Keep a possible partial magic suffix.
                keep = min(len(self._buf), len(MAGIC) - 1)
                if keep:
                    del self._buf[:-keep]
                else:
                    self._buf.clear()
                break
            if pos:
                del self._buf[:pos]

            if len(self._buf) < HEADER_STRUCT.size:
                break

            magic, version, msg_type, payload_len, sequence, timestamp_ms = HEADER_STRUCT.unpack_from(self._buf)
            if magic != MAGIC or version != VERSION or payload_len > MAX_PAYLOAD:
                self.header_errors += 1
                del self._buf[0]
                continue

            total = HEADER_STRUCT.size + payload_len + CRC_STRUCT.size
            if len(self._buf) < total:
                break

            payload = bytes(self._buf[HEADER_STRUCT.size:HEADER_STRUCT.size + payload_len])
            expected = CRC_STRUCT.unpack_from(self._buf, HEADER_STRUCT.size + payload_len)[0]
            actual = crc16(bytes(self._buf[4:HEADER_STRUCT.size]) + payload)
            if expected != actual:
                self.crc_errors += 1
                del self._buf[0]
                continue

            out.append(Packet(msg_type, sequence, timestamp_ms, payload))
            del self._buf[:total]

        return out



class ScanIntensityPairer:
    """Pair protocol-v1 MSG_SCAN with optional MSG_INTENSITY by sequence.

    Works with either wire order. A scan is held for at most ``wait_s``; if its
    companion never arrives, it is released with ``None`` intensity so range
    publishing can never stall.
    """

    def __init__(self, wait_s: float = 0.030, cache_limit: int = 32) -> None:
        self.wait_s = float(wait_s)
        self.cache_limit = int(cache_limit)
        self._scans: dict[int, tuple[float, Packet]] = {}
        self._intensity: dict[int, tuple[float, bytes]] = {}

    def feed(self, packet: Packet, now: float) -> List[Tuple[Packet, bytes | None]]:
        out: List[Tuple[Packet, bytes | None]] = []
        if packet.msg_type == MSG_SCAN:
            q = self._intensity.pop(packet.sequence, None)
            if q is not None:
                out.append((packet, q[1]))
            else:
                self._scans[packet.sequence] = (now, packet)
        elif packet.msg_type == MSG_INTENSITY:
            scan = self._scans.pop(packet.sequence, None)
            if scan is not None:
                out.append((scan[1], packet.payload))
            else:
                self._intensity[packet.sequence] = (now, packet.payload)

        self._trim()
        out.extend(self.flush(now))
        return out

    def flush(self, now: float) -> List[Tuple[Packet, bytes | None]]:
        out: List[Tuple[Packet, bytes | None]] = []
        expired = [seq for seq, (t0, _p) in self._scans.items() if now - t0 >= self.wait_s]
        for seq in expired:
            _t0, packet = self._scans.pop(seq)
            q = self._intensity.pop(seq, None)
            out.append((packet, None if q is None else q[1]))

        # Stale intensity-only metadata is never allowed to grow forever.
        stale = [seq for seq, (t0, _q) in self._intensity.items() if now - t0 >= max(self.wait_s * 4, 0.2)]
        for seq in stale:
            self._intensity.pop(seq, None)
        self._trim()
        return out

    def _trim(self) -> None:
        while len(self._scans) > self.cache_limit:
            seq = min(self._scans, key=lambda k: self._scans[k][0])
            self._scans.pop(seq, None)
        while len(self._intensity) > self.cache_limit:
            seq = min(self._intensity, key=lambda k: self._intensity[k][0])
            self._intensity.pop(seq, None)

def decode_scan_points(payload: bytes, intensity_payload: bytes | None = None) -> List[ScanPoint]:
    """Decode protocol-v1 20-byte distance fragments.

    ``intensity_payload`` is optional and comes from MSG_INTENSITY with the same
    sequence number. When it is absent or malformed, distances remain valid and
    point intensity is set to 0.
    """
    if not payload or len(payload) % FRAME_STRUCT.size:
        raise ProtocolError("scan payload length must be a positive multiple of 20")

    frame_count = len(payload) // FRAME_STRUCT.size
    quality_ok = intensity_payload is not None and len(intensity_payload) == frame_count * 8

    points: List[ScanPoint] = []
    quality_off = 0
    for off in range(0, len(payload), FRAME_STRUCT.size):
        start_cd, end_cd, *distances = FRAME_STRUCT.unpack_from(payload, off)
        start = start_cd / 100.0
        end = end_cd / 100.0
        if end < start:
            end += 360.0
        spread = end - start
        if spread > 25.0:
            quality_off += 8
            continue

        for i, dist_mm in enumerate(distances):
            q = float(intensity_payload[quality_off + i]) if quality_ok else 0.0
            if dist_mm == 0:
                continue
            angle = start + spread * (i / 7.0)
            angle %= 360.0
            points.append(ScanPoint(angle, dist_mm / 1000.0, q))
        quality_off += 8
    return points


def resample_scan_with_intensity(
    points: Sequence[ScanPoint],
    bins: int = 360,
    mirror: bool = True,
    offset_deg: float = 180.0,
    range_min: float = 0.05,
    range_max: float = 16.0,
) -> Tuple[float, float, float, List[float], List[float]]:
    """Resample ranges and native quality values onto the same angular bins.

    If several native points fall into one output bin, the closest range wins,
    and its intensity is copied to the same bin.
    """
    if bins < 8:
        raise ValueError("bins must be >= 8")

    angle_min = -math.pi
    angle_max = math.pi
    angle_increment = (angle_max - angle_min) / bins
    ranges = [math.inf] * bins
    intensities = [0.0] * bins

    for point in points:
        r = point.distance_m
        if not (range_min <= r <= range_max):
            continue
        a_deg = transform_angle(point.angle_deg, mirror, offset_deg)
        a = math.radians(a_deg)
        idx = int((a - angle_min) / angle_increment)
        if idx == bins:
            idx = bins - 1
        if 0 <= idx < bins and r < ranges[idx]:
            ranges[idx] = r
            intensities[idx] = float(point.intensity)

    return angle_min, angle_max - angle_increment, angle_increment, ranges, intensities


def transform_angle(angle_deg: float, mirror: bool, offset_deg: float) -> float:
    angle = -angle_deg if mirror else angle_deg
    angle += offset_deg
    return ((angle + 180.0) % 360.0) - 180.0


def resample_scan(
    points: Sequence[ScanPoint],
    bins: int = 360,
    mirror: bool = True,
    offset_deg: float = 180.0,
    range_min: float = 0.05,
    range_max: float = 16.0,
) -> Tuple[float, float, float, List[float]]:
    """Resample irregular native points to a standards-friendly uniform LaserScan."""
    if bins < 8:
        raise ValueError("bins must be >= 8")

    angle_min = -math.pi
    angle_max = math.pi
    angle_increment = (angle_max - angle_min) / bins
    ranges = [math.inf] * bins

    for point in points:
        r = point.distance_m
        if not (range_min <= r <= range_max):
            continue
        a_deg = transform_angle(point.angle_deg, mirror, offset_deg)
        a = math.radians(a_deg)
        idx = int((a - angle_min) / angle_increment)
        if idx == bins:
            idx = bins - 1
        if 0 <= idx < bins and r < ranges[idx]:
            ranges[idx] = r

    return angle_min, angle_max - angle_increment, angle_increment, ranges

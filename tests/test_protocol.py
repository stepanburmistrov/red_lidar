from pathlib import Path
import math
import struct
import sys

PKG = Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "rosik_lidar"
sys.path.insert(0, str(PKG))

from rosik_lidar.protocol import (
    FRAME_STRUCT,
    MSG_SCAN,
    StreamParser,
    build_packet,
    decode_scan_points,
    resample_scan,
)


def make_payload():
    f1 = FRAME_STRUCT.pack(0, 700, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700)
    f2 = FRAME_STRUCT.pack(800, 1500, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500)
    return f1 + f2


def test_roundtrip_with_fragmented_input():
    raw = build_packet(MSG_SCAN, 42, 1234, make_payload())
    parser = StreamParser()
    got = []
    for i in range(0, len(raw), 7):
        got.extend(parser.feed(raw[i:i + 7]))
    assert len(got) == 1
    assert got[0].sequence == 42
    assert got[0].timestamp_ms == 1234
    assert got[0].payload == make_payload()


def test_parser_recovers_after_noise_and_bad_crc():
    good = build_packet(MSG_SCAN, 2, 20, make_payload())
    bad = bytearray(build_packet(MSG_SCAN, 1, 10, make_payload()))
    bad[-1] ^= 0x55
    parser = StreamParser()
    packets = parser.feed(b"noise" + bad + good)
    assert [p.sequence for p in packets] == [2]
    assert parser.crc_errors >= 1


def test_interpolation_uses_endpoints():
    pts = decode_scan_points(make_payload()[:FRAME_STRUCT.size])
    assert len(pts) == 8
    assert abs(pts[0].angle_deg - 0.0) < 1e-9
    assert abs(pts[-1].angle_deg - 7.0) < 1e-9


def test_resampling():
    pts = decode_scan_points(make_payload())
    amin, amax, inc, ranges = resample_scan(pts, bins=360, mirror=False, offset_deg=0.0)
    assert len(ranges) == 360
    assert amin == -math.pi
    assert inc > 0
    assert any(math.isfinite(x) for x in ranges)

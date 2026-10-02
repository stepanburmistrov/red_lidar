from pathlib import Path
import math
import struct
import sys
import random

PKG = Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "rosik_lidar"
sys.path.insert(0, str(PKG))

from rosik_lidar.protocol import (
    FRAME_STRUCT,
    MSG_SCAN,
    MSG_INTENSITY,
    StreamParser,
    build_packet,
    decode_scan_points,
    resample_scan,
    resample_scan_with_intensity,
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


def make_intensity_payload():
    # Two frames x 8 quality bytes. Keep values distinctive for alignment checks.
    return bytes(range(10, 26))


def test_v110_scan_packet_format_is_unchanged():
    """Regression guard: MSG_SCAN stays protocol-v1 / 20-byte fragments."""
    payload = make_payload()
    raw = build_packet(MSG_SCAN, 42, 1234, payload)
    # Header fields: magic + version=1 + msg_type=1 + original payload length.
    assert raw[:4] == b"RLDR"
    assert raw[4] == 1
    assert raw[5] == MSG_SCAN
    assert len(payload) == 2 * 20


def test_intensity_is_optional_and_does_not_change_range_decode():
    payload = make_payload()
    old_points = decode_scan_points(payload)
    new_points = decode_scan_points(payload, make_intensity_payload())
    assert [(p.angle_deg, p.distance_m) for p in new_points] == [
        (p.angle_deg, p.distance_m) for p in old_points
    ]
    assert all(p.intensity == 0.0 for p in old_points)
    assert any(p.intensity > 0.0 for p in new_points)


def test_companion_packet_survives_fragmented_stream():
    intensity = build_packet(MSG_INTENSITY, 77, 9000, make_intensity_payload())
    scan = build_packet(MSG_SCAN, 77, 9000, make_payload())
    parser = StreamParser()
    packets = []
    stream = intensity + scan
    # Deliberately awkward chunking across both packet headers and CRCs.
    sizes = [1, 2, 7, 3, 19, 5, 31, 4, 11]
    pos = 0
    i = 0
    while pos < len(stream):
        n = sizes[i % len(sizes)]
        packets.extend(parser.feed(stream[pos:pos+n]))
        pos += n
        i += 1
    assert [(p.msg_type, p.sequence) for p in packets] == [
        (MSG_INTENSITY, 77),
        (MSG_SCAN, 77),
    ]
    points = decode_scan_points(packets[1].payload, packets[0].payload)
    assert len(points) == 16
    assert points[0].intensity == 10.0
    assert points[-1].intensity == 25.0


def test_bad_intensity_packet_cannot_destroy_following_scan():
    bad_intensity = bytearray(build_packet(MSG_INTENSITY, 99, 9000, make_intensity_payload()))
    bad_intensity[-1] ^= 0xA5
    good_scan = build_packet(MSG_SCAN, 99, 9000, make_payload())

    parser = StreamParser()
    packets = parser.feed(bytes(bad_intensity) + good_scan)
    assert [p.msg_type for p in packets] == [MSG_SCAN]
    assert parser.crc_errors >= 1

    # This is the key compatibility guarantee: scan decodes without intensity.
    points = decode_scan_points(packets[0].payload, None)
    assert len(points) == 16
    assert all(p.intensity == 0.0 for p in points)


def test_resampling_with_intensity_keeps_alignment():
    points = decode_scan_points(make_payload(), make_intensity_payload())
    amin, amax, inc, ranges, intensities = resample_scan_with_intensity(
        points, bins=360, mirror=False, offset_deg=0.0
    )
    assert len(ranges) == 360
    assert len(intensities) == 360
    finite_bins = [i for i, r in enumerate(ranges) if math.isfinite(r)]
    assert finite_bins
    assert all(intensities[i] > 0 for i in finite_bins)


def test_500_scan_stream_never_loses_distance_when_intensity_is_bad():
    rng = random.Random(12345)
    wire = bytearray()
    expected_scans = 500
    for seq in range(expected_scans):
        intensity = bytearray(build_packet(MSG_INTENSITY, seq, seq * 10, make_intensity_payload()))
        if seq % 10 == 3:
            intensity[-1] ^= 0x7F  # corrupt only optional quality packet
        wire.extend(intensity)
        wire.extend(build_packet(MSG_SCAN, seq, seq * 10, make_payload()))

    parser = StreamParser()
    packets = []
    pos = 0
    while pos < len(wire):
        n = rng.randint(1, 97)
        packets.extend(parser.feed(bytes(wire[pos:pos+n])))
        pos += n

    scans = [p for p in packets if p.msg_type == MSG_SCAN]
    assert len(scans) == expected_scans
    assert [p.sequence for p in scans] == list(range(expected_scans))
    # 50 intentionally bad intensity packets should be counted, but must not
    # affect the following scan packet.
    assert parser.crc_errors >= 50

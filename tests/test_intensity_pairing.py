import pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "rosik_lidar"))
from rosik_lidar.protocol import build_packet, StreamParser, ScanIntensityPairer, MSG_SCAN, MSG_INTENSITY

def packet(msg_type, seq, payload):
    raw=build_packet(msg_type, seq, 1000, payload)
    return StreamParser().feed(raw)[0]

def test_scan_first_pairs_when_intensity_arrives_after():
    pairer=ScanIntensityPairer(wait_s=0.03)
    scan=packet(MSG_SCAN, 77, b"\0"*20)
    q=packet(MSG_INTENSITY, 77, bytes(range(8)))
    assert pairer.feed(scan, 1.000) == []
    out=pairer.feed(q, 1.005)
    assert len(out)==1 and out[0][0].sequence==77 and out[0][1]==bytes(range(8))

def test_intensity_first_pairs_when_scan_arrives_after():
    pairer=ScanIntensityPairer(wait_s=0.03)
    q=packet(MSG_INTENSITY, 9, bytes(range(8)))
    scan=packet(MSG_SCAN, 9, b"\0"*20)
    assert pairer.feed(q, 2.000) == []
    out=pairer.feed(scan, 2.004)
    assert len(out)==1 and out[0][1]==bytes(range(8))

def test_missing_intensity_releases_scan_after_timeout():
    pairer=ScanIntensityPairer(wait_s=0.03)
    scan=packet(MSG_SCAN, 5, b"\0"*20)
    assert pairer.feed(scan, 3.000) == []
    assert pairer.flush(3.020) == []
    out=pairer.flush(3.031)
    assert len(out)==1 and out[0][0].sequence==5 and out[0][1] is None

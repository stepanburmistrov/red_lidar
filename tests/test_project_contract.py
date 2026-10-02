from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "ros2_ws" / "src" / "rosik_lidar"
sys.path.insert(0, str(PKG))

from rosik_lidar.protocol import (
    MSG_SCAN, MSG_INTENSITY, ScanIntensityPairer, build_packet,
    FRAME_STRUCT, Packet
)


def test_intensity_first_pairs_immediately_when_scan_arrives():
    q = bytes(range(8))
    scan_payload = FRAME_STRUCT.pack(0, 700, *([1000] * 8))
    pairer = ScanIntensityPairer(wait_s=0.1)
    assert pairer.feed(Packet(MSG_INTENSITY, 77, 1234, q), 1.0) == []
    ready = pairer.feed(Packet(MSG_SCAN, 77, 1234, scan_payload), 1.001)
    assert len(ready) == 1
    scan, iq = ready[0]
    assert scan.sequence == 77
    assert iq == q


def test_ros_node_has_visible_driver_version_and_diagnostics():
    text = (PKG / "rosik_lidar" / "ros_node.py").read_text(encoding="utf-8")
    assert 'DRIVER_VERSION = "1.0.0"' in text
    assert 'UART diag:' in text
    assert 'Native intensity attached to /scan' in text


def test_firmware_sends_optional_intensity_before_scan_only_when_queue_fits():
    text = (ROOT / "firmware" / "rosik_lidar_uart" / "rosik_lidar_uart.ino").read_text(encoding="utf-8")
    pos_i = text.index('sendHostPacket(MSG_INTENSITY')
    pos_s = text.index('sendHostPacket(MSG_SCAN', pos_i)
    assert pos_i < pos_s
    assert 'Serial.availableForWrite()) >= bothBytes' in text

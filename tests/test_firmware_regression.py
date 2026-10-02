from pathlib import Path

FW = (
    Path(__file__).resolve().parents[1]
    / "firmware"
    / "rosik_lidar_uart"
    / "rosik_lidar_uart.ino"
).read_text(encoding="utf-8")


def test_original_scan_wire_contract_is_preserved():
    assert "static constexpr uint8_t PROTO_VERSION = 1;" in FW
    assert "static constexpr uint8_t MSG_SCAN = 1;" in FW
    assert "static constexpr size_t FRAME_LEN = 20;" in FW
    # Verify the firmware range-acceptance rule used by the host protocol.
    assert "if (quality[i] >= HOST_INTENSITY_MIN && dist[i] != 0x8000) d = dist[i];" in FW


def test_uart_buffers_are_configured_before_begin():
    tx = FW.index("Serial.setTxBufferSize(HOST_TX_BUFFER);")
    rx = FW.index("LIDAR.setRxBufferSize(LIDAR_RX_BUFFER);")
    host_begin = FW.index("Serial.begin(HOST_BAUD);")
    lidar_begin = FW.index("LIDAR.begin(LIDAR_BAUD")
    assert tx < host_begin
    assert rx < lidar_begin


def test_optional_intensity_keeps_scan_format_stable():
    assert "MSG_INTENSITY = 2" in FW
    assert "FRAME_LEN = 20" in FW
    assert "PROTO_VERSION = 1" in FW
    assert "sendHostPacket(MSG_SCAN, scanBuf" in FW
    assert "intensityLen == size_t(frameCount) * 8" in FW

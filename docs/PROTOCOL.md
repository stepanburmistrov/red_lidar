# ROSiK LiDAR host UART protocol v1

The ESP32 reads the original LiDAR stream at **115200 8N1**, groups fragments into one revolution, and sends one binary host packet per scan through `Serial` at **460800 8N1**.

## Host packet

All integers are little-endian.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | ASCII magic `RLDR` |
| 4 | 1 | protocol version = `1` |
| 5 | 1 | message type = `1` (full scan) |
| 6 | 2 | payload length |
| 8 | 4 | scan sequence |
| 12 | 4 | ESP32 `millis()` timestamp |
| 16 | N | payload |
| 16+N | 2 | CRC16/Modbus over bytes 4..15 and payload |

## Full-scan payload

The payload is a concatenation of 20-byte fragments:

```text
uint16 start_angle_centideg
uint16 end_angle_centideg
uint16 distance_mm[8]
```

A zero distance means invalid/low-quality data. Angles for the eight samples are linearly interpolated including both endpoints (`i / 7.0`).

## Why the bridge does not forward raw LiDAR packets

The ESP32 removes low-quality samples, detects complete revolutions, and adds sequence, length and a verified CRC. This makes resynchronisation after a cable/USB glitch deterministic and gives the Python and ROS clients exactly the same input format.

#!/usr/bin/env python3
"""Hardware smoke test for ROSiK LiDAR UART.

This test talks directly to ESP32; ROS is not required.
It verifies that:
  * protocol-v1 distance scan packets are continuously received;
  * optional intensity packets arrive with matching sequence numbers;
  * CRC stays clean;
  * native scan data decodes to plausible point counts.

Example:
    python tools/serial_test.py COM6 --seconds 10
"""
from __future__ import annotations

from pathlib import Path
import argparse
import statistics
import sys
import time

PKG = Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "rosik_lidar"
sys.path.insert(0, str(PKG))

from rosik_lidar.protocol import MSG_SCAN, MSG_INTENSITY, ScanIntensityPairer, decode_scan_points
from rosik_lidar.serial_io import LidarSerial, available_ports


def main() -> int:
    p = argparse.ArgumentParser(description="ROSiK LiDAR UART hardware test")
    p.add_argument("port", nargs="?", help="COM6 or /dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=460800)
    p.add_argument("--seconds", type=float, default=10.0)
    args = p.parse_args()

    if not args.port:
        ports = available_ports()
        if len(ports) == 1:
            args.port = ports[0]
        else:
            print("ERROR: specify a serial port. Available ports:")
            for port in ports:
                print("  ", port)
            return 2

    link = LidarSerial(args.port, args.baud, timeout=0.05)
    print(f"[OPEN] {args.port} @ {args.baud}")
    try:
        link.open()
    except Exception as exc:
        print(f"[FAIL] cannot open port: {exc}")
        return 2

    started = time.monotonic()
    last_report = started
    scans = 0
    intensity_packets = 0
    matched = 0
    scans_without_intensity = 0
    point_counts: list[int] = []
    qualities: list[int] = []
    pairer = ScanIntensityPairer(wait_s=0.030)
    first_scan_time = None
    last_scan_time = None
    last_seq = None
    seq_gaps = 0

    print(f"[TEST] listening for {args.seconds:.1f} s")
    try:
        while time.monotonic() - started < args.seconds:
            packets = link.read_packets()
            ready = []
            pair_now = time.monotonic()
            for packet in packets:
                if packet.msg_type == MSG_INTENSITY:
                    intensity_packets += 1
                if packet.msg_type in (MSG_SCAN, MSG_INTENSITY):
                    ready.extend(pairer.feed(packet, pair_now))
            ready.extend(pairer.flush(time.monotonic()))

            for packet, q in ready:
                now = time.monotonic()
                scans += 1
                first_scan_time = now if first_scan_time is None else first_scan_time
                last_scan_time = now

                if last_seq is not None and ((last_seq + 1) & 0xFFFFFFFF) != packet.sequence:
                    seq_gaps += 1
                last_seq = packet.sequence

                if q is None:
                    scans_without_intensity += 1
                else:
                    matched += 1

                try:
                    points = decode_scan_points(packet.payload, q)
                except Exception as exc:
                    print(f"[FAIL] scan #{packet.sequence} cannot be decoded: {exc}")
                    return 1

                point_counts.append(len(points))
                if q is not None:
                    qualities.extend(int(x.intensity) for x in points if x.intensity > 0)

            now = time.monotonic()
            if now - last_report >= 1.0:
                elapsed = now - started
                hz = scans / elapsed if elapsed else 0.0
                print(
                    f"[LIVE] scans={scans} ({hz:.1f} Hz), "
                    f"intensity={intensity_packets}, matched={matched}, "
                    f"CRC={link.parser.crc_errors}, header={link.parser.header_errors}"
                )
                last_report = now
            time.sleep(0.001)
    finally:
        link.close()

    elapsed = max(time.monotonic() - started, 1e-9)
    hz = scans / elapsed

    print("\n--- RESULT ---")
    print(f"scan packets:       {scans}")
    print(f"scan rate:          {hz:.2f} Hz")
    print(f"intensity packets:  {intensity_packets}")
    print(f"matched intensity:  {matched}/{scans}")
    print(f"without intensity:  {scans_without_intensity}")
    print(f"sequence gaps:      {seq_gaps}")
    print(f"CRC errors:         {link.parser.crc_errors}")
    print(f"header errors:      {link.parser.header_errors}")
    if point_counts:
        print(
            "points/scan:        "
            f"min={min(point_counts)}, median={statistics.median(point_counts):.0f}, "
            f"max={max(point_counts)}"
        )
    if qualities:
        print(
            "native intensity:   "
            f"min={min(qualities)}, median={statistics.median(qualities):.0f}, "
            f"max={max(qualities)}"
        )

    # Intentionally judge distance transport separately from intensity.
    # Optional intensity must never be able to make the scan test fail.
    if scans < max(3, int(args.seconds)):
        print("[FAIL] too few distance scans. ESP32 -> host scan transport is not stable.")
        return 1
    if link.parser.crc_errors:
        print("[FAIL] CRC errors detected in the serial stream.")
        return 1
    if not point_counts or statistics.median(point_counts) < 100:
        print("[FAIL] scan packets arrive, but contain too few valid points.")
        return 1

    print("[PASS] distance scan transport is stable.")

    if matched == 0:
        print("[WARN] no matching intensity packets were received; ranges still work.")
    elif matched < scans * 0.9:
        print("[WARN] intensity is present but some companion packets were lost.")
    else:
        print("[PASS] intensity companion packets are stable.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

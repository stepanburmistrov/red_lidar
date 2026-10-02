"""Standalone live ROSiK LiDAR visualizer (no ROS required)."""
from __future__ import annotations

import argparse
import math
import sys
import time

import matplotlib.pyplot as plt
import numpy as np

from .protocol import MSG_SCAN, MSG_INTENSITY, ScanIntensityPairer, decode_scan_points, transform_angle
from .serial_io import LidarSerial, available_ports


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ROSiK LiDAR live UART visualizer")
    p.add_argument("port", nargs="?", help="Serial port, e.g. COM5 or /dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=460800)
    p.add_argument("--max-range", type=float, default=4.0, help="Plot radius in metres")
    p.add_argument("--offset", type=float, default=180.0, help="Angle offset in degrees")
    p.add_argument("--no-mirror", action="store_true", help="Disable left/right mirroring")
    p.add_argument("--color-by", choices=("intensity", "distance"), default="intensity",
                   help="Color points by native LiDAR intensity or distance")
    return p


def main(argv=None) -> None:
    args = make_parser().parse_args(argv)
    if not args.port:
        ports = available_ports()
        if len(ports) == 1:
            args.port = ports[0]
        else:
            print("Specify serial port. Available:")
            for p in ports:
                print("  ", p)
            raise SystemExit(2)

    link = LidarSerial(args.port, args.baud)
    try:
        link.open()
    except Exception as exc:
        print(f"Cannot open {args.port}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    plt.ion()
    fig = plt.figure(figsize=(9, 9))
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, args.max_range)
    ax.set_title("ROSiK LiDAR • live scan", pad=20)
    ax.grid(True, alpha=0.35)

    # Eight subtle sector boundaries matching the LED ring idea.
    for deg in range(0, 360, 45):
        a = math.radians(deg)
        ax.plot([a, a], [0, args.max_range], linewidth=0.8, alpha=0.25)

    if args.color_by == "intensity":
        scatter = ax.scatter([], [], s=16, c=[], cmap="turbo", vmin=0, vmax=255)
        cbar = fig.colorbar(scatter, ax=ax, pad=0.10, shrink=0.78)
        cbar.set_label("Intensity")
    else:
        scatter = ax.scatter([], [], s=16, c=[], cmap="turbo", vmin=0, vmax=args.max_range)
        cbar = fig.colorbar(scatter, ax=ax, pad=0.10, shrink=0.78)
        cbar.set_label("Distance, m")
    status = ax.text(0.02, 0.02, "Waiting for scan…", transform=ax.transAxes, fontsize=10)
    nearest_labels = [
        ax.text(math.radians(i * 45), args.max_range * 0.94, "—", ha="center", va="center", fontsize=8)
        for i in range(8)
    ]

    last_t = time.monotonic()
    fps = 0.0
    pairer = ScanIntensityPairer(wait_s=0.030)

    try:
        while plt.fignum_exists(fig.number):
            got = False
            packets = link.read_packets()
            ready = []
            now_pair = time.monotonic()
            for packet in packets:
                if packet.msg_type in (MSG_SCAN, MSG_INTENSITY):
                    ready.extend(pairer.feed(packet, now_pair))
            ready.extend(pairer.flush(time.monotonic()))

            for packet, quality_payload in ready:
                points = decode_scan_points(packet.payload, quality_payload)
                if not points:
                    continue
                got = True
                angles = np.array([
                    math.radians(transform_angle(p.angle_deg, not args.no_mirror, args.offset))
                    for p in points
                ])
                ranges = np.array([p.distance_m for p in points])
                qualities = np.array([p.intensity for p in points])
                good = np.isfinite(ranges) & (ranges > 0.02) & (ranges <= args.max_range)
                angles = angles[good]
                ranges = ranges[good]
                qualities = qualities[good]

                if len(ranges):
                    scatter.set_offsets(np.column_stack((angles, ranges)))
                    if args.color_by == "intensity":
                        if quality_payload is not None:
                            scatter.set_array(qualities)
                        else:
                            # Missing native intensity is shown as zero/black,
                            # never silently replaced by distance colors.
                            scatter.set_array(np.zeros_like(ranges))
                    else:
                        scatter.set_array(ranges)

                mins = [math.inf] * 8
                for a, r in zip(angles, ranges):
                    deg = math.degrees(a) % 360.0
                    sec = int(((deg + 22.5) % 360.0) / 45.0)
                    mins[sec] = min(mins[sec], float(r))
                for i, label in enumerate(nearest_labels):
                    label.set_text("—" if math.isinf(mins[i]) else f"{mins[i]:.2f} m")

                now = time.monotonic()
                dt = now - last_t
                if dt > 0:
                    inst = 1.0 / dt
                    fps = inst if fps == 0 else fps * 0.85 + inst * 0.15
                last_t = now
                status.set_text(
                    f"scan #{packet.sequence}   {len(points)} pts   {fps:.1f} Hz\n"
                    f"intensity: {'yes' if quality_payload is not None else 'NO'}   "
                    f"CRC errors: {link.parser.crc_errors}   port: {args.port} @ {args.baud}"
                )

            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            plt.pause(0.001 if got else 0.01)
    except KeyboardInterrupt:
        pass
    finally:
        link.close()


if __name__ == "__main__":
    main()

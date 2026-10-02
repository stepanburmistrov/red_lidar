"""ROS 2 Jazzy node for the ROSiK LiDAR UART bridge."""
from __future__ import annotations

import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import TransformStamped
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster

from .protocol import (
    MSG_SCAN,
    MSG_INTENSITY,
    ScanIntensityPairer,
    decode_scan_points,
    resample_scan,
    resample_scan_with_intensity,
)
from .serial_io import LidarSerial

DRIVER_VERSION = "1.0.0"


class RosikLidarNode(Node):
    def __init__(self) -> None:
        super().__init__("rosik_lidar")
        self.declare_parameter("port", "/dev/ttyUSB0")
        self.declare_parameter("baud", 460800)
        self.declare_parameter("topic", "/scan")
        self.declare_parameter("frame_id", "laser")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("publish_static_tf", True)
        self.declare_parameter("lidar_xyz", [0.0, 0.0, 0.10])
        self.declare_parameter("angle_offset_deg", 180.0)
        self.declare_parameter("mirror", True)
        self.declare_parameter("range_min", 0.05)
        self.declare_parameter("range_max", 16.0)
        self.declare_parameter("scan_bins", 360)
        self.declare_parameter("intensity_wait_ms", 100.0)
        self.declare_parameter("diagnostics_period_s", 5.0)

        self.port = str(self.get_parameter("port").value)
        self.baud = int(self.get_parameter("baud").value)
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.range_min = float(self.get_parameter("range_min").value)
        self.range_max = float(self.get_parameter("range_max").value)
        self.scan_bins = int(self.get_parameter("scan_bins").value)
        self.mirror = bool(self.get_parameter("mirror").value)
        self.angle_offset_deg = float(self.get_parameter("angle_offset_deg").value)
        wait_s = max(0.0, float(self.get_parameter("intensity_wait_ms").value) / 1000.0)
        self._diag_period = max(1.0, float(self.get_parameter("diagnostics_period_s").value))

        topic = str(self.get_parameter("topic").value)
        # LaserScan is sensor data: use the standard ROS 2 sensor-data QoS profile.
        self.pub = self.create_publisher(LaserScan, topic, qos_profile_sensor_data)
        self.link = LidarSerial(self.port, self.baud, timeout=0.02)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._pairer = ScanIntensityPairer(wait_s=wait_s)

        self._scan_packets_rx = 0
        self._intensity_packets_rx = 0
        self._published = 0
        self._published_with_intensity = 0
        self._last_diag = time.monotonic()
        self._first_intensity_logged = False

        if bool(self.get_parameter("publish_static_tf").value):
            self._publish_static_tf()

        self.link.open()
        self._thread.start()
        self.get_logger().info(
            f"ROSiK LiDAR driver v{DRIVER_VERSION}: {self.port} @ {self.baud}, "
            f"publishing {topic}; ranges + native intensity"
        )
        self.get_logger().info(
            f"Intensity pairing wait: {wait_s * 1000.0:.0f} ms; QoS: sensor_data (BEST_EFFORT/VOLATILE)"
        )

    def _publish_static_tf(self) -> None:
        xyz = list(self.get_parameter("lidar_xyz").value)
        tf = TransformStamped()
        tf.header.stamp = self.get_clock().now().to_msg()
        tf.header.frame_id = str(self.get_parameter("base_frame").value)
        tf.child_frame_id = self.frame_id
        tf.transform.translation.x = float(xyz[0])
        tf.transform.translation.y = float(xyz[1])
        tf.transform.translation.z = float(xyz[2])
        tf.transform.rotation.w = 1.0
        self.static_tf = StaticTransformBroadcaster(self)
        self.static_tf.sendTransform(tf)

    def _publish_scan_packet(self, packet, intensity_payload: bytes | None) -> None:
        points = decode_scan_points(packet.payload, intensity_payload)
        if intensity_payload is None:
            amin, amax, ainc, ranges = resample_scan(
                points,
                bins=self.scan_bins,
                mirror=self.mirror,
                offset_deg=self.angle_offset_deg,
                range_min=self.range_min,
                range_max=self.range_max,
            )
            intensities = []
        else:
            amin, amax, ainc, ranges, intensities = resample_scan_with_intensity(
                points,
                bins=self.scan_bins,
                mirror=self.mirror,
                offset_deg=self.angle_offset_deg,
                range_min=self.range_min,
                range_max=self.range_max,
            )
            self._published_with_intensity += 1
            if not self._first_intensity_logged:
                self._first_intensity_logged = True
                nonzero = sum(1 for x in intensities if x > 0.0)
                self.get_logger().info(
                    f"Native intensity attached to /scan: {nonzero}/{len(intensities)} bins non-zero."
                )

        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.angle_min = amin
        msg.angle_max = amax
        msg.angle_increment = ainc
        msg.time_increment = 0.0
        msg.scan_time = 0.0
        msg.range_min = self.range_min
        msg.range_max = self.range_max
        msg.ranges = ranges
        msg.intensities = intensities
        self.pub.publish(msg)
        self._published += 1

    def _log_diagnostics_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_diag < self._diag_period:
            return
        self._last_diag = now
        self.get_logger().info(
            "UART diag: "
            f"scan_rx={self._scan_packets_rx}, "
            f"intensity_rx={self._intensity_packets_rx}, "
            f"published={self._published}, "
            f"with_intensity={self._published_with_intensity}, "
            f"crc_errors={self.link.parser.crc_errors}, "
            f"header_errors={self.link.parser.header_errors}"
        )

    def _reader(self) -> None:
        while rclpy.ok() and not self._stop.is_set():
            try:
                packets = self.link.read_packets()
                now = time.monotonic()
                ready = []
                for packet in packets:
                    if packet.msg_type == MSG_SCAN:
                        self._scan_packets_rx += 1
                        ready.extend(self._pairer.feed(packet, now))
                    elif packet.msg_type == MSG_INTENSITY:
                        self._intensity_packets_rx += 1
                        ready.extend(self._pairer.feed(packet, now))
                ready.extend(self._pairer.flush(time.monotonic()))
                for scan_packet, intensity_payload in ready:
                    self._publish_scan_packet(scan_packet, intensity_payload)
                self._log_diagnostics_if_due()
                if not packets:
                    time.sleep(0.001)
            except Exception as exc:
                self.get_logger().error(f"Serial/LiDAR error: {exc}")
                time.sleep(0.5)

    def destroy_node(self):
        self._stop.set()
        self.link.close()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = RosikLidarNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

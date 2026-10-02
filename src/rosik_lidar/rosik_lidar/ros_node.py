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

from .protocol import decode_scan_points, resample_scan
from .serial_io import LidarSerial


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

        self.port = str(self.get_parameter("port").value)
        self.baud = int(self.get_parameter("baud").value)
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.range_min = float(self.get_parameter("range_min").value)
        self.range_max = float(self.get_parameter("range_max").value)
        self.scan_bins = int(self.get_parameter("scan_bins").value)
        self.mirror = bool(self.get_parameter("mirror").value)
        self.angle_offset_deg = float(self.get_parameter("angle_offset_deg").value)

        topic = str(self.get_parameter("topic").value)
        self.pub = self.create_publisher(LaserScan, topic, qos_profile_sensor_data)
        self.link = LidarSerial(self.port, self.baud, timeout=0.05)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)

        if bool(self.get_parameter("publish_static_tf").value):
            self._publish_static_tf()

        self.link.open()
        self._thread.start()
        self.get_logger().info(f"ROSiK LiDAR: {self.port} @ {self.baud}, publishing {topic}")

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

    def _reader(self) -> None:
        while rclpy.ok() and not self._stop.is_set():
            try:
                packets = self.link.read_packets()
                if not packets:
                    continue
                for packet in packets:
                    if packet.msg_type != 1:
                        continue
                    points = decode_scan_points(packet.payload)
                    amin, amax, ainc, ranges = resample_scan(
                        points,
                        bins=self.scan_bins,
                        mirror=self.mirror,
                        offset_deg=self.angle_offset_deg,
                        range_min=self.range_min,
                        range_max=self.range_max,
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
                    self.pub.publish(msg)
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

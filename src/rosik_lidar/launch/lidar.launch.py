import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory("rosik_lidar")
    config = os.path.join(share, "config", "lidar.yaml")
    rviz_config = os.path.join(share, "rviz", "lidar.rviz")

    return LaunchDescription([
        DeclareLaunchArgument("port", default_value="/dev/ttyUSB0"),
        DeclareLaunchArgument("baud", default_value="460800"),
        DeclareLaunchArgument("rviz", default_value="false"),
        Node(
            package="rosik_lidar",
            executable="rosik_lidar_node",
            name="rosik_lidar",
            output="screen",
            parameters=[
                config,
                {
                    "port": LaunchConfiguration("port"),
                    "baud": LaunchConfiguration("baud"),
                },
            ],
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            arguments=["-d", rviz_config],
            output="screen",
            condition=IfCondition(LaunchConfiguration("rviz")),
        ),
    ])

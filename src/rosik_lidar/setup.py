from glob import glob
from setuptools import find_packages, setup
import os

package_name = "rosik_lidar"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "rviz"), glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools", "pyserial"],
    zip_safe=True,
    maintainer="Stepan Burmistrov",
    maintainer_email="robotx@example.invalid",
    description="UART driver, viewer and ROS 2 LaserScan publisher for ROSiK LiDAR",
    license="MIT",
    entry_points={
        "console_scripts": [
            "rosik_lidar_node = rosik_lidar.ros_node:main",
            "rosik_lidar_viewer = rosik_lidar.viewer:main",
        ],
    },
)

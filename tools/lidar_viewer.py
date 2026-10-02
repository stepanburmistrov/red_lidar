#!/usr/bin/env python3
"""Run the viewer straight from a cloned repository, without installing the package."""
from pathlib import Path
import sys

pkg_root = Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "rosik_lidar"
sys.path.insert(0, str(pkg_root))

from rosik_lidar.viewer import main

if __name__ == "__main__":
    main()

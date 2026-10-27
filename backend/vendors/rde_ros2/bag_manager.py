#!/usr/bin/env python3
"""
Rosbag2 Recording & Playback Controller.
Extracted and adapted from mcp_servers/rde-mcp-ros-2/src/rde_mcp_ros2/server.py (lines 598-707).

Provides programmatic recording, playback, and introspection of ROS 2 bag files
for dataset logging and telemetry playback in Antigravity ROS Studio.
"""

import subprocess
import signal
import os
import shutil
from typing import List, Dict, Any, Optional


class BagManager:
    @staticmethod
    def record_bag(output_path: str, topics: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Starts recording a ROS 2 bag in a background subprocess.
        """
        if not shutil.which("ros2"):
            return {"success": False, "error": "ros2 CLI not found"}

        cmd = ["ros2", "bag", "record", "-o", output_path]
        if topics:
            cmd.extend(topics)
        else:
            cmd.append("-a")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setpgrp
            )
            return {
                "success": True,
                "output_path": output_path,
                "topics": topics if topics else "all",
                "pid": process.pid
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def play_bag(bag_path: str, rate: float = 1.0) -> Dict[str, Any]:
        """
        Plays back a ROS 2 bag at the specified rate multiplier.
        """
        if not shutil.which("ros2"):
            return {"success": False, "error": "ros2 CLI not found"}

        cmd = ["ros2", "bag", "play", bag_path, "-r", str(rate)]
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setpgrp
            )
            return {
                "success": True,
                "bag_path": bag_path,
                "rate": rate,
                "pid": process.pid
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_bag_info(bag_path: str) -> Dict[str, Any]:
        """
        Retrieves and parses metadata from a bag file.
        """
        if not shutil.which("ros2"):
            return {"path": bag_path, "error": "ros2 CLI not found"}

        try:
            result = subprocess.run(
                ["ros2", "bag", "info", bag_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return {"path": bag_path, "error": result.stderr.strip()}

            info: Dict[str, Any] = {"path": bag_path}
            lines = result.stdout.strip().split("\n")
            current_section = None

            for line in lines:
                if not line.strip():
                    continue

                if ":" in line and line[0] != " ":
                    key, value = line.split(":", 1)
                    info[key.strip().lower().replace(" ", "_")] = value.strip()
                    current_section = key.strip().lower().replace(" ", "_")
                elif current_section and ":" in line:
                    key, value = line.split(":", 1)
                    if current_section not in info or not isinstance(info[current_section], dict):
                        info[current_section] = {}
                    info[current_section][key.strip().lower().replace(" ", "_")] = value.strip()

            return info
        except Exception as e:
            return {"path": bag_path, "error": str(e)}

    @staticmethod
    def stop_process(pid: int) -> bool:
        """
        Gracefully terminates a recording or playback process via SIGINT.
        """
        try:
            os.kill(pid, signal.SIGINT)
            return True
        except ProcessLookupError:
            return True
        except Exception:
            return False

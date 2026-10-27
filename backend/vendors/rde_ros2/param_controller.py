#!/usr/bin/env python3
"""
Dynamic Parameter Controller for ROS 2 Nodes.
Extracted and adapted from mcp_servers/rde-mcp-ros-2/src/rde_mcp_ros2/server.py (lines 394-490).

Provides query and runtime modification of ROS 2 parameters on live nodes,
powering parameter sliders and dynamic tuning in Antigravity ROS Studio.
"""

import subprocess
import json
import shutil
from typing import List, Dict, Any, Optional


class ParameterController:
    @staticmethod
    def list_parameters(node_name: str) -> List[str]:
        """
        Lists parameter names for a given node.
        """
        if not shutil.which("ros2"):
            return []

        try:
            result = subprocess.run(
                ["ros2", "param", "list", node_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return []
            return [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
        except Exception:
            return []

    @staticmethod
    def get_parameter(node_name: str, param_name: str) -> Dict[str, Any]:
        """
        Retrieves the value of a parameter from a node.
        """
        if not shutil.which("ros2"):
            return {"error": "ros2 CLI not found on PATH"}

        try:
            result = subprocess.run(
                ["ros2", "param", "get", node_name, param_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return {"error": result.stderr.strip() or "Parameter query failed"}

            output = result.stdout.strip()
            value_str = output.split(":", 1)[1].strip() if ":" in output else output

            try:
                value = json.loads(value_str)
            except json.JSONDecodeError:
                value = value_str

            return {
                "node": node_name,
                "parameter": param_name,
                "value": value
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def set_parameter(node_name: str, param_name: str, value: Any) -> Dict[str, Any]:
        """
        Sets the value of a parameter on a live node.
        """
        if not shutil.which("ros2"):
            return {"error": "ros2 CLI not found on PATH"}

        if isinstance(value, bool):
            val_str = str(value).lower()
        elif isinstance(value, (int, float, str)):
            val_str = str(value)
        else:
            val_str = json.dumps(value)

        try:
            result = subprocess.run(
                ["ros2", "param", "set", node_name, param_name, val_str],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr.strip()}

            return {
                "success": True,
                "node": node_name,
                "parameter": param_name,
                "value": value
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

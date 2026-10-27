#!/usr/bin/env python3
"""
Structured ROS 2 Doctor System Diagnostic Parser.
Extracted and adapted from mcp_servers/rde-mcp-ros-2/src/rde_mcp_ros2/server.py (lines 1178-1248).

Executes 'ros2 doctor' (or parses existing doctor reports) and transforms bracketed CLI output
into structured JSON health checks for the Pre-Flight Status Bar in Antigravity ROS Studio.
"""

import subprocess
import shutil
from typing import Dict, Any, List, Optional


class DoctorParser:
    @staticmethod
    def parse_doctor_output(output: str, returncode: int = 0) -> Dict[str, Any]:
        """
        Parses raw text output of 'ros2 doctor' into structured checks.
        """
        checks: List[Dict[str, Any]] = []
        current_check: Optional[Dict[str, Any]] = None

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("[") and "]" in line:
                status = line.split("]")[0].strip("[]")
                name = line.split("]", 1)[1].strip()

                current_check = {
                    "name": name,
                    "status": status.lower(),
                    "details": []
                }
                checks.append(current_check)
            elif current_check:
                current_check["details"].append(line)

        # Determine overall status
        overall_status = "pass"
        for check in checks:
            st = check["status"].lower()
            if "error" in st or "fail" in st:
                overall_status = "error"
                break
            elif "warn" in st and overall_status != "error":
                overall_status = "warning"

        return {
            "success": returncode == 0,
            "overall_status": overall_status,
            "check_count": len(checks),
            "checks": checks,
            "raw_output": output
        }

    @classmethod
    def run_doctor(cls, report: bool = False, include_warnings: bool = True) -> Dict[str, Any]:
        """
        Runs 'ros2 doctor' as a subprocess and parses results.
        If ros2 CLI is not found on PATH, returns a graceful mock diagnostic.
        """
        if not shutil.which("ros2"):
            return {
                "success": False,
                "overall_status": "warning",
                "check_count": 1,
                "checks": [{
                    "name": "ROS 2 CLI Availability",
                    "status": "warning",
                    "details": ["'ros2' executable not detected on system PATH. Ensure ROS 2 environment is sourced."]
                }],
                "raw_output": "ros2: command not found"
            }

        cmd = ["ros2", "doctor"]
        if report:
            cmd.append("--report")
        if not include_warnings:
            cmd.append("--include-warnings=0")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            output = result.stdout.strip() or result.stderr.strip()
            return cls.parse_doctor_output(output, result.returncode)
        except Exception as e:
            return {
                "success": False,
                "overall_status": "error",
                "checks": [{
                    "name": "Doctor Execution",
                    "status": "error",
                    "details": [str(e)]
                }],
                "raw_output": str(e)
            }


if __name__ == "__main__":
    res = DoctorParser.run_doctor()
    print(f"Overall Status: {res['overall_status']}")
    for c in res["checks"]:
        print(f" - [{c['status'].upper()}] {c['name']}")

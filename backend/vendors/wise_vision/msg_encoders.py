#!/usr/bin/env python3
"""
Binary ROS 2 Perception Message Encoders for WebGL.
Extracted and adapted from mcp_servers/wise-vision-ros2-mcp/server/ros2_manager_extended.py (L250-320)
and ros2_manager.py (L213-260).

Encodes nav_msgs/OccupancyGrid and sensor_msgs/PointCloud2 into compact
Base64/JSON payloads for direct browser Three.js WebGL visualization.
"""

import base64
import array
import struct
import math
from typing import Dict, Any, Optional, List


class MessageEncoders:
    @staticmethod
    def encode_occupancy_grid(msg: Any) -> Dict[str, Any]:
        """
        Converts nav_msgs/msg/OccupancyGrid into structured metadata and base64 grid data.
        """
        try:
            info = getattr(msg, "info", None)
            width = int(getattr(info, "width", 0)) if info else 0
            height = int(getattr(info, "height", 0)) if info else 0
            resolution = float(getattr(info, "resolution", 0.05)) if info else 0.05

            origin = getattr(info, "origin", None)
            origin_pos = getattr(origin, "position", None) if origin else None
            origin_x = float(getattr(origin_pos, "x", 0.0)) if origin_pos else 0.0
            origin_y = float(getattr(origin_pos, "y", 0.0)) if origin_pos else 0.0

            raw_data = getattr(msg, "data", [])
            # Pack int8 values into bytes
            byte_data = bytes([max(0, min(255, val if val >= 0 else 128)) for val in raw_data])
            b64_data = base64.b64encode(byte_data).decode("utf-8")

            return {
                "width": width,
                "height": height,
                "resolution": resolution,
                "origin": {"x": origin_x, "y": origin_y},
                "data_b64": b64_data,
                "cell_count": len(raw_data)
            }
        except Exception as e:
            return {"error": f"Failed to encode OccupancyGrid: {e}"}

    @staticmethod
    def encode_pointcloud2_xyz(msg: Any, max_points: int = 10000) -> Dict[str, Any]:
        """
        Unpacks binary IEEE 754 float x, y, z fields from sensor_msgs/msg/PointCloud2
        and returns Base64 float32 buffers for WebGL Three.js point cloud rendering.
        """
        try:
            fields = {f.name: f for f in getattr(msg, "fields", [])}
            if not all(k in fields for k in ("x", "y", "z")):
                return {"error": "PointCloud2 missing x/y/z fields."}

            data = bytes(getattr(msg, "data", b"") or b"")
            endian = ">" if bool(getattr(msg, "is_bigendian", False)) else "<"
            off_x = int(fields["x"].offset)
            off_y = int(fields["y"].offset)
            off_z = int(fields["z"].offset)

            step = int(getattr(msg, "point_step", 0) or 0)
            width = int(getattr(msg, "width", 0) or 0)
            height = int(getattr(msg, "height", 0) or 0)
            n = width * height

            if step <= 0 or n <= 0:
                return {"error": "PointCloud2 has invalid dimensions."}

            stride = 1 if max_points <= 0 else max(1, n // max_points)
            out_pos = array.array("f")

            for i in range(0, n, stride):
                offset = i * step
                if offset + step > len(data):
                    break
                try:
                    x = struct.unpack_from(f"{endian}f", data, offset + off_x)[0]
                    y = struct.unpack_from(f"{endian}f", data, offset + off_y)[0]
                    z = struct.unpack_from(f"{endian}f", data, offset + off_z)[0]
                    if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
                        out_pos.extend((x, y, z))
                except Exception:
                    continue

            return {
                "point_count": len(out_pos) // 3,
                "positions_f32_b64": base64.b64encode(out_pos.tobytes()).decode("utf-8")
            }
        except Exception as e:
            return {"error": f"Failed to encode PointCloud2: {e}"}

    @staticmethod
    def encode_laser_scan(msg: Any) -> Dict[str, Any]:
        """
        Encodes sensor_msgs/msg/LaserScan into cartesian coordinates for 2D WebGL canvas.
        """
        try:
            angle_min = float(getattr(msg, "angle_min", 0.0))
            angle_inc = float(getattr(msg, "angle_increment", 0.01))
            range_min = float(getattr(msg, "range_min", 0.1))
            range_max = float(getattr(msg, "range_max", 30.0))
            ranges = list(getattr(msg, "ranges", []))

            points = []
            for i, r in enumerate(ranges):
                if math.isfinite(r) and range_min <= r <= range_max:
                    theta = angle_min + i * angle_inc
                    x = round(r * math.cos(theta), 3)
                    y = round(r * math.sin(theta), 3)
                    points.append({"x": x, "y": y, "range": round(r, 3)})

            return {
                "valid_points": len(points),
                "total_readings": len(ranges),
                "points": points
            }
        except Exception as e:
            return {"error": f"Failed to encode LaserScan: {e}"}

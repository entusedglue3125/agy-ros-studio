#!/usr/bin/env python3
"""
DDS Discovery Warmup Engine for Antigravity ROS Studio.
Extracted and adapted from mcp_servers/wise-vision-ros2-mcp/server/ros2_manager.py (lines 561-643).

Mitigates DDS participant discovery latency and race conditions in Docker containers
or desktop environments by monitoring graph snapshot deltas until stabilization.
"""

import time
import os
import threading
from typing import Dict, Any, Optional

try:
    import rclpy
    HAS_RCLPY = True
except ImportError:
    HAS_RCLPY = False


class DiscoveryWarmup:
    def __init__(self, node: Any = None):
        self.node = node
        self._warmed_up = False
        self._lock = threading.Lock()

    def _graph_snapshot(self) -> tuple:
        if not HAS_RCLPY or not self.node:
            return (), ()
        try:
            topics = tuple(sorted(name for name, _ in self.node.get_topic_names_and_types()))
            services = tuple(sorted(name for name, _ in self.node.get_service_names_and_types()))
            return topics, services
        except Exception:
            return (), ()

    def warm_up_discovery(
        self,
        timeout_sec: float = 5.0,
        stable_sec: float = 1.0,
        poll_sec: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Cycles rclpy.spin_once until node and topic discovery stabilizes over `stable_sec`.
        """
        if not HAS_RCLPY or not self.node:
            return {"status": "skipped", "reason": "rclpy node not available"}

        with self._lock:
            if self._warmed_up:
                return {"status": "already_warmed"}

            start = time.monotonic()
            last_snapshot = None
            last_change = start
            polls = 0

            while True:
                now = time.monotonic()
                elapsed = now - start
                if elapsed >= timeout_sec:
                    break

                step = min(poll_sec, timeout_sec - elapsed)
                try:
                    rclpy.spin_once(self.node, timeout_sec=step)
                except Exception:
                    pass

                snapshot = self._graph_snapshot()
                polls += 1

                if snapshot != last_snapshot:
                    last_snapshot = snapshot
                    last_change = time.monotonic()

                if (time.monotonic() - last_change) >= stable_sec and polls > 2:
                    break

            self._warmed_up = True
            elapsed_total = round(time.monotonic() - start, 3)
            topics_count = len(last_snapshot[0]) if last_snapshot else 0
            services_count = len(last_snapshot[1]) if last_snapshot else 0

            return {
                "status": "warmed",
                "elapsed_sec": elapsed_total,
                "polls": polls,
                "topics_count": topics_count,
                "services_count": services_count,
            }

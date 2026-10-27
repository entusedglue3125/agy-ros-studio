#!/usr/bin/env python3
"""
High-Precision Stream Session & Monotonic Topic Hz Monitor.
Extracted and adapted from mcp_servers/wise-vision-ros2-mcp/server/ros2_manager.py (lines 410-435 & 867-920).

Powers the Animated Topic Wire Oscilloscope by tracking message reception timestamps
with monotonic clock precision and calculating real-time Hz and jitter.
"""

import time
import threading
from typing import Optional, Dict, Any, List
from collections import deque


class StreamSession:
    def __init__(
        self,
        session_id: str,
        topic_name: str,
        topic_type: str,
        kind: str = "message",
        target_fps: Optional[float] = None,
        window_size: int = 50,
    ):
        self.session_id = session_id
        self.topic_name = topic_name
        self.topic_type = topic_type
        self.kind = kind
        self.target_fps = target_fps

        self.lock = threading.RLock()
        self.stop_event = threading.Event()

        self.seq = 0
        self.rx_count = 0
        self.last_rx_monotonic = 0.0
        self.last_emit_monotonic = 0.0
        self.last_error: Optional[str] = None
        self.last_payload: Optional[Dict[str, Any]] = None

        # Sliding window for precise Hz calculation
        self._timestamps = deque(maxlen=window_size)

    def on_message_received(self, raw_msg: Any, processed_payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Invoked by the ROS 2 subscriber callback on message arrival.
        Updates rx_count, monotonic arrival time, and checks target_fps throttle.

        Returns:
            True if the message passes target_fps rate-limiting and should be emitted.
        """
        now = time.monotonic()
        with self.lock:
            self.rx_count += 1
            self.seq += 1
            self.last_rx_monotonic = now
            self._timestamps.append(now)

            if processed_payload is not None:
                self.last_payload = processed_payload

            # Check target FPS rate limiter
            if self.target_fps and self.target_fps > 0:
                min_dt = 1.0 / self.target_fps
                if (now - self.last_emit_monotonic) < min_dt:
                    return False

            self.last_emit_monotonic = now
            return True

    def get_current_hz(self) -> float:
        """
        Computes the current frequency in Hertz (Hz) over the sliding window.
        """
        with self.lock:
            if len(self._timestamps) < 2:
                return 0.0

            dt = self._timestamps[-1] - self._timestamps[0]
            if dt <= 0.0001:
                return 0.0

            return round((len(self._timestamps) - 1) / dt, 2)

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """
        Returns structured telemetry for oscilloscope visualization.
        """
        now = time.monotonic()
        with self.lock:
            age_sec = (
                round(max(0.0, now - self.last_rx_monotonic), 3)
                if self.last_rx_monotonic > 0
                else None
            )
            is_alive = age_sec is not None and age_sec < 2.0

            return {
                "session_id": self.session_id,
                "topic_name": self.topic_name,
                "topic_type": self.topic_type,
                "rx_count": self.rx_count,
                "seq": self.seq,
                "hz": self.get_current_hz() if is_alive else 0.0,
                "last_rx_age_sec": age_sec,
                "is_alive": is_alive,
                "last_error": self.last_error,
            }

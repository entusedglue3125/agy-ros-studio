#!/usr/bin/env python3
"""
Dynamic QoS Profile Resolver for Antigravity ROS Studio.
Extracted and adapted from mcp_servers/wise-vision-ros2-mcp/server/ros2_manager.py (lines 645-710).

Inspects live publisher/subscriber endpoints on active ROS 2 topics to dynamically
negotiate and resolve compatible QoS profiles (Reliability, Durability, Depth).
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import rclpy QoS structures; provide mock fallback if rclpy is not installed on dev host
try:
    from rclpy.node import Node
    from rclpy.qos import (
        QoSProfile,
        QoSReliabilityPolicy,
        QoSDurabilityPolicy,
        QoSPresetProfiles,
    )
    HAS_RCLPY = True
except ImportError:
    HAS_RCLPY = False
    Node = None
    QoSProfile = None
    QoSReliabilityPolicy = None
    QoSDurabilityPolicy = None
    QoSPresetProfiles = None


class QoSResolver:
    """
    Analyzes active topic endpoints in DDS graph and resolves compatible QoS profiles.
    """

    @staticmethod
    def get_qos_profile_for_topic(node: Any, topic_name: str) -> Any:
        """
        Determines the optimal subscriber QoS profile for a topic by inspecting all publishers.
        If all publishers offer RELIABLE, returns RELIABLE.
        If any publisher offers BEST_EFFORT, returns BEST_EFFORT to guarantee connection.
        If all publishers offer TRANSIENT_LOCAL, returns TRANSIENT_LOCAL; otherwise VOLATILE.
        """
        if not HAS_RCLPY or node is None:
            return {
                "reliability": "best_effort",
                "durability": "volatile",
                "depth": 10,
                "note": "rclpy unavailable; using safe fallback"
            }

        qos_profile = QoSPresetProfiles.SYSTEM_DEFAULT.value
        reliability_reliable_endpoints_count = 0
        durability_transient_local_endpoints_count = 0

        try:
            pubs_info = node.get_publishers_info_by_topic(topic_name)
        except Exception as e:
            logger.warning(f"Could not retrieve publishers for topic {topic_name}: {e}")
            return qos_profile

        publishers_count = len(pubs_info)
        if publishers_count == 0:
            return qos_profile

        for info in pubs_info:
            if info.qos_profile.reliability == QoSReliabilityPolicy.RELIABLE:
                reliability_reliable_endpoints_count += 1
            if info.qos_profile.durability == QoSDurabilityPolicy.TRANSIENT_LOCAL:
                durability_transient_local_endpoints_count += 1

        # Reliability negotiation
        if reliability_reliable_endpoints_count == publishers_count:
            qos_profile.reliability = QoSReliabilityPolicy.RELIABLE
        else:
            if reliability_reliable_endpoints_count > 0:
                logger.info(
                    f"Topic '{topic_name}': Some publishers offer RELIABLE, others BEST_EFFORT. "
                    "Falling back to BEST_EFFORT to receive from all publishers."
                )
            qos_profile.reliability = QoSReliabilityPolicy.BEST_EFFORT

        # Durability negotiation
        if durability_transient_local_endpoints_count == publishers_count:
            qos_profile.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        else:
            if durability_transient_local_endpoints_count > 0:
                logger.info(
                    f"Topic '{topic_name}': Falling back to VOLATILE durability."
                )
            qos_profile.durability = QoSDurabilityPolicy.VOLATILE

        return qos_profile

    @staticmethod
    def get_qos_for_publisher_topic(node: Any, topic_name: str) -> Any:
        """
        Determines the optimal publisher QoS profile based on existing subscriber expectations.
        """
        if not HAS_RCLPY or node is None:
            return {"reliability": "reliable", "durability": "volatile", "depth": 10}

        base = QoSPresetProfiles.SYSTEM_DEFAULT.value
        qos = QoSProfile(
            depth=base.depth,
            reliability=base.reliability,
            durability=base.durability,
            history=base.history,
            deadline=base.deadline,
            lifespan=base.lifespan,
            liveliness=base.liveliness,
            liveliness_lease_duration=base.liveliness_lease_duration,
            avoid_ros_namespace_conventions=base.avoid_ros_namespace_conventions,
        )

        try:
            subs_info = node.get_subscriptions_info_by_topic(topic_name)
        except Exception:
            return qos

        if not subs_info:
            return qos

        any_best_effort = False
        any_transient_local = False

        for sub in subs_info:
            if sub.qos_profile.reliability == QoSReliabilityPolicy.BEST_EFFORT:
                any_best_effort = True
            if sub.qos_profile.durability == QoSDurabilityPolicy.TRANSIENT_LOCAL:
                any_transient_local = True

        if any_best_effort:
            qos.reliability = QoSReliabilityPolicy.BEST_EFFORT
        else:
            qos.reliability = QoSReliabilityPolicy.RELIABLE

        if any_transient_local:
            qos.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
        else:
            qos.durability = QoSDurabilityPolicy.VOLATILE

        return qos

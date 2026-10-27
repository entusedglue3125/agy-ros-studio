"""ROS 2 MCP Server - Model Context Protocol server for ROS 2."""

__version__ = "1.0.0"
__author__ = "Ranch Hand Robotics"
__description__ = "Model Context Protocol server for ROS 2 introspection and control"

from .server import main

__all__ = ["main", "__version__"]

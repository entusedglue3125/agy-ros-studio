#!/usr/bin/env python3
# Auto-generated custom node by Antigravity ROS Studio

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

# Standard message imports
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan, Imu
from nav_msgs.msg import Odometry, OccupancyGrid, Path

class SafetyFilterNode(Node):
    def __init__(self):
        super().__init__('safety_filter')
        self.get_logger().info('Initialized custom node: safety_filter')

        # Subscriber: cmd_vel_raw -> /cmd_vel_raw (geometry_msgs/msg/Twist)
        qos_cmd_vel_raw = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )
        self.sub_cmd_vel_raw = self.create_subscription(
            Twist,
            '/cmd_vel_raw',
            self.on_cmd_vel_raw,
            qos_cmd_vel_raw
        )
        # Publisher: cmd_vel -> /cmd_vel (geometry_msgs/msg/Twist)
        qos_cmd_vel = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )
        self.pub_cmd_vel = self.create_publisher(
            Twist,
            '/cmd_vel',
            qos_cmd_vel
        )

        # User-defined Custom Implementation or Callback Methods
    def on_cmd_vel_raw(self, msg: Twist):
        # Scaffolded student code for velocity safety limiter
        safe_twist = Twist()
        safe_twist.linear.x = min(msg.linear.x, 0.4)
        safe_twist.angular.z = msg.angular.z
        self.pub_cmd_vel.publish(safe_twist)


def main(args=None):
    rclpy.init(args=args)
    node = SafetyFilterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
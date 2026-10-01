#!/usr/bin/env python3
"""Robot différentiel simulé, sans interface : /cmd_vel → /odom (vue 2D du lab)."""

import math
import sys

RATE_HZ = 20.0
COMMAND_TIMEOUT_S = 0.5  # sans commande récente, le robot s'arrête


def integrate(x, y, theta, v, w, dt):
    """Cinématique d'un robot différentiel (intégration exacte sur un arc)."""
    if abs(w) < 1e-9:
        return x + v * math.cos(theta) * dt, y + v * math.sin(theta) * dt, theta
    new_theta = theta + w * dt
    r = v / w
    x += r * (math.sin(new_theta) - math.sin(theta))
    y -= r * (math.cos(new_theta) - math.cos(theta))
    return x, y, math.atan2(math.sin(new_theta), math.cos(new_theta))


def main():
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from rclpy.node import Node

    class DiffBot(Node):
        def __init__(self):
            super().__init__("academy_diffbot")
            self.x = self.y = self.theta = 0.0
            self.v = self.w = 0.0
            self.last_cmd = self.get_clock().now()
            self.odom_pub = self.create_publisher(Odometry, "odom", 10)
            self.create_subscription(Twist, "cmd_vel", self.on_cmd, 10)
            self.create_timer(1.0 / RATE_HZ, self.step)
            self.get_logger().info("academy_diffbot prêt : commandes sur /cmd_vel, pose sur /odom")

        def on_cmd(self, msg):
            self.v, self.w = msg.linear.x, msg.angular.z
            self.last_cmd = self.get_clock().now()

        def step(self):
            now = self.get_clock().now()
            if (now - self.last_cmd).nanoseconds > COMMAND_TIMEOUT_S * 1e9:
                self.v = self.w = 0.0
            self.x, self.y, self.theta = integrate(self.x, self.y, self.theta, self.v, self.w, 1.0 / RATE_HZ)
            odom = Odometry()
            odom.header.stamp = now.to_msg()
            odom.header.frame_id = "odom"
            odom.child_frame_id = "base_link"
            odom.pose.pose.position.x = self.x
            odom.pose.pose.position.y = self.y
            odom.pose.pose.orientation.z = math.sin(self.theta / 2)
            odom.pose.pose.orientation.w = math.cos(self.theta / 2)
            odom.twist.twist.linear.x = self.v
            odom.twist.twist.angular.z = self.w
            self.odom_pub.publish(odom)

    rclpy.init(args=sys.argv)
    node = DiffBot()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

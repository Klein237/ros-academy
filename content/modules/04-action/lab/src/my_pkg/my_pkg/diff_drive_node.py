import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node

from my_interface.srv import GetPose


class DiffDriveNode(Node):
    """Robot à conduite différentielle simulé : /cmd_vel → position → /odom, service get_pose."""

    def __init__(self):
        super().__init__('diff_drive_node')
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.v = 0.0
        self.w = 0.0
        self.dt = 0.05  # période de mise à jour (s)

        self.cmd_sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.timer = self.create_timer(self.dt, self.update)
        # Serveur du service get_pose
        self.srv = self.create_service(GetPose, 'get_pose', self.get_pose_callback)
        self.get_logger().info('diff_drive_node prêt : commandes sur /cmd_vel, position sur /odom')

    def cmd_vel_callback(self, msg):
        """Mémorise la dernière commande de vitesse reçue."""
        self.v = msg.linear.x
        self.w = msg.angular.z

    def get_pose_callback(self, request, response):
        """Fonction de rappel du service get_pose : renvoie la pose actuelle."""
        response.x = self.x
        response.y = self.y
        response.theta = self.theta
        self.get_logger().info(f'Service get_pose appelé : ({self.x:.2f}, {self.y:.2f}, {self.theta:.2f})')
        return response

    def move_robot(self, v, w, dt):
        """Fait avancer le robot de dt secondes à la vitesse (v, w)."""
        self.theta = math.atan2(math.sin(self.theta + w * dt), math.cos(self.theta + w * dt))
        self.x += v * math.cos(self.theta) * dt
        self.y += v * math.sin(self.theta) * dt

    def update(self):
        self.move_robot(self.v, self.w, self.dt)
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = math.sin(self.theta / 2)
        odom.pose.pose.orientation.w = math.cos(self.theta / 2)
        odom.twist.twist.linear.x = self.v
        odom.twist.twist.angular.z = self.w
        self.odom_pub.publish(odom)


def main(args=None):
    rclpy.init(args=args)
    node = DiffDriveNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

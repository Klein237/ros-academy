import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

TOUT_DROIT = 2.5  # s, à 0,2 m/s : un côté de 50 cm
VIRAGE = 2.0      # s, pour un quart de tour


class PatrouilleNode(Node):
    """Fait patrouiller le robot en carré sur /cmd_vel."""

    def __init__(self):
        super().__init__('patrouille_node')
        # Le robot (diff_drive_node) attend des geometry_msgs/msg/Twist sur /cmd_vel
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.debut = self.get_clock().now()
        self.etape = None
        self.create_timer(0.1, self.step)
        self.get_logger().info('Patrouille démarrée')

    def step(self):
        t = (self.get_clock().now() - self.debut).nanoseconds * 1e-9
        cmd = Twist()
        if t % (TOUT_DROIT + VIRAGE) < TOUT_DROIT:
            etape = 'tout droit'
            cmd.linear.x = 0.2
        else:
            etape = 'virage'
            cmd.angular.z = (math.pi / 2) / VIRAGE
        if etape != self.etape:
            self.get_logger().info(f'Étape : {etape}')
            self.etape = etape
        self.get_logger().debug(f't={t:.1f} s : v={cmd.linear.x:.2f} m/s, ω={cmd.angular.z:.2f} rad/s')
        self.pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = PatrouilleNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

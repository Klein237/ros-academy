import math

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node

TOUT_DROIT = 2.5  # s, à 0,2 m/s : un côté de 50 cm
VIRAGE = 2.0      # s, pour un quart de tour


class PatrouilleNode(Node):
    """Fait patrouiller le robot en carré sur /cmd_vel (repris d'un exemple de Nav2 pour Jazzy)."""

    def __init__(self):
        super().__init__('patrouille_node')
        self.pub = self.create_publisher(TwistStamped, 'cmd_vel', 10)
        self.debut = self.get_clock().now()
        self.etape = None
        self.create_timer(0.1, self.step)
        self.get_logger().info('Patrouille démarrée')

    def step(self):
        maintenant = self.get_clock().now()
        t = (maintenant - self.debut).nanoseconds * 1e-9
        cmd = TwistStamped()
        cmd.header.stamp = maintenant.to_msg()
        cmd.header.frame_id = 'base_link'
        if t % (TOUT_DROIT + VIRAGE) < TOUT_DROIT:
            etape = 'tout droit'
            cmd.twist.linear.x = 0.2
        else:
            etape = 'virage'
            cmd.twist.angular.z = (math.pi / 2) / VIRAGE
        if etape != self.etape:
            self.get_logger().info(f'Étape : {etape}')
            self.etape = etape
        self.get_logger().debug(
            f't={t:.1f} s : v={cmd.twist.linear.x:.2f} m/s, ω={cmd.twist.angular.z:.2f} rad/s')
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

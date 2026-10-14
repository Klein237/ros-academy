"""Amène la pince sur la cible reçue sur /cible : calcule les angles et publie /joint_states."""
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from sensor_msgs.msg import JointState

from bras_controle.cinematique import ARTICULATIONS, angles_pour


class CinematiqueInverse(Node):
    def __init__(self):
        super().__init__('cinematique_inverse')
        self.angles = [0.0, 0.0, 0.0, 0.0]  # bras tendu vers le haut au départ
        self.pub = self.create_publisher(JointState, 'joint_states', 10)
        self.create_subscription(PointStamped, 'cible', self.viser, 10)
        # l'état est republié en continu : robot_state_publisher garde des TF à jour
        self.create_timer(0.05, self.publier)

    def viser(self, msg):
        p = msg.point
        try:
            self.angles = list(angles_pour(p.x, p.y, p.z))
        except ValueError as exc:
            self.get_logger().warning(f'cible ({p.x:.2f}, {p.y:.2f}, {p.z:.2f}) ignorée : {exc}')
            return
        self.get_logger().info(f'cible ({p.x:.2f}, {p.y:.2f}, {p.z:.2f}) : angles '
                               + ', '.join(f'{a:.2f}' for a in self.angles))

    def publier(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [*ARTICULATIONS, 'pince']
        msg.position = [*self.angles, 0.0]
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = CinematiqueInverse()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

"""Publie la position de la pince calculée à partir de l'état des articulations."""
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from sensor_msgs.msg import JointState

from bras_controle.cinematique import ARTICULATIONS, position_pince


class CinematiqueDirecte(Node):
    def __init__(self):
        super().__init__('cinematique_directe')
        self.pub = self.create_publisher(PointStamped, 'position_pince', 10)
        self.create_subscription(JointState, 'joint_states', self.recevoir, 10)

    def recevoir(self, msg):
        angles = dict(zip(msg.name, msg.position))
        if not all(nom in angles for nom in ARTICULATIONS):
            return  # un état partiel (la pince seule, par exemple)
        x, y, z = position_pince(*(angles[nom] for nom in ARTICULATIONS))
        point = PointStamped()
        point.header.stamp = msg.header.stamp
        point.header.frame_id = 'base_link'
        point.point.x, point.point.y, point.point.z = x, y, z
        self.pub.publish(point)


def main():
    rclpy.init()
    node = CinematiqueDirecte()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

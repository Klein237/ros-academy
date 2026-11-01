"""Arrêt d'urgence du robot de livraison : publie True sur /arret quand un obstacle est trop proche."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool

from arret_urgence.detection import obstacle_proche


class ArretUrgence(Node):

    def __init__(self):
        super().__init__('arret_urgence')
        self.seuil = self.declare_parameter('seuil', 0.5).value
        self.arret = self.create_publisher(Bool, '/arret', 10)
        self.create_subscription(LaserScan, '/scan', self.recevoir, 10)

    def recevoir(self, scan):
        proche = obstacle_proche(scan.ranges, scan.range_min, scan.range_max, self.seuil)
        self.arret.publish(Bool(data=bool(proche)))


def main():
    rclpy.init()
    noeud = ArretUrgence()
    try:
        rclpy.spin(noeud)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()

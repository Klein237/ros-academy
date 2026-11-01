"""Limiteur de vitesse du robot de livraison : borne la vitesse des commandes avant les moteurs."""

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


def borner(valeur, maximum):
    """Ramène valeur dans [-maximum, maximum]."""
    return max(-maximum, min(valeur, maximum))


class Limiteur(Node):
    """Reçoit les commandes sur /cmd_vel_brut, publie sur /cmd_vel la commande bornée."""

    def __init__(self):
        super().__init__('limiteur')
        self.vitesse_max = self.declare_parameter('vitesse_max', 0.5).value
        self.sortie = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Twist, '/cmd_vel_brut', self.recevoir, 10)

    def recevoir(self, commande):
        limite = Twist()
        limite.linear.x = borner(commande.linear.x, self.vitesse_max)
        limite.angular.z = commande.angular.z
        self.sortie.publish(limite)


def main():
    rclpy.init()
    noeud = Limiteur()
    try:
        rclpy.spin(noeud)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()

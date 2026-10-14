"""Nœud d'état du robot de livraison : annonce qu'il est prêt, puis publie son état chaque seconde."""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class Etat(Node):
    def __init__(self):
        super().__init__('etat')
        self.robot = self.declare_parameter('robot', 'livreur-01').value
        self.pub = self.create_publisher(String, 'etat', 10)
        self.create_timer(1.0, self.publier)
        self.get_logger().info(f'Robot de livraison prêt : {self.robot}')

    def publier(self):
        self.pub.publish(String(data=f'{self.robot} : en service'))


def main():
    rclpy.init()
    node = Etat()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

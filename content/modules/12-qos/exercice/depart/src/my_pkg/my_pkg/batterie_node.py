"""Pilote de la batterie, fourni par le fabricant du robot. Ne pas modifier."""

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState


class BatterieNode(Node):
    """Publie l'état de la batterie cinq fois par seconde, comme une mesure de capteur."""

    def __init__(self):
        super().__init__('batterie_node')
        self.pub = self.create_publisher(BatteryState, 'battery_state', qos_profile_sensor_data)
        self.charge = 0.85
        self.create_timer(0.2, self.publish_state)
        self.get_logger().info('Pilote de batterie démarré')

    def publish_state(self):
        self.charge = max(0.0, self.charge - 0.0002)
        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.voltage = 22.0 + 3.2 * self.charge
        msg.percentage = self.charge
        msg.present = True
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = BatterieNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

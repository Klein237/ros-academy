import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState


class SuperviseurNode(Node):
    """Surveille la batterie : affiche la charge, et donne l'alerte sous le seuil."""

    def __init__(self):
        super().__init__('superviseur_node')
        self.declare_parameter('seuil', 0.2)
        self.charge = None
        # Même profil que le pilote : une mesure de capteur, en BEST_EFFORT
        self.create_subscription(BatteryState, 'battery_state', self.on_battery,
                                 qos_profile_sensor_data)
        self.create_timer(2.0, self.report)

    def on_battery(self, msg):
        self.charge = msg.percentage

    def report(self):
        seuil = self.get_parameter('seuil').value
        if self.charge is None:
            self.get_logger().warn('Aucune mesure de batterie reçue')
        elif self.charge < seuil:
            self.get_logger().error(f'Batterie faible : {self.charge * 100:.0f} %, retour à la base')
        else:
            self.get_logger().info(f'Batterie : {self.charge * 100:.0f} %')


def main(args=None):
    rclpy.init(args=args)
    node = SuperviseurNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

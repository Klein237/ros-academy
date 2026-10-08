import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_srvs.srv import SetBool

PERIODE = 0.05  # s : la couche de sécurité publie 20 fois par seconde


def clamp(value, limit):
    return max(-limit, min(value, limit))


def rampe(actuelle, cible, pas):
    """Rapproche la vitesse actuelle de la cible, d'au plus « pas »."""
    return actuelle + clamp(cible - actuelle, pas)


class GardeNode(Node):
    """Couche de sécurité devant le robot : limites, rampe, chien de garde et arrêt d'urgence."""

    def __init__(self):
        super().__init__('garde_node')
        self.declare_parameter('max_linear_speed', 0.3)   # m/s
        self.declare_parameter('max_angular_speed', 0.8)  # rad/s
        self.declare_parameter('max_linear_accel', 0.5)   # m/s²
        self.declare_parameter('cmd_timeout', 0.5)        # s sans commande avant l'arrêt
        self.max_v = self.get_parameter('max_linear_speed').value
        self.max_w = self.get_parameter('max_angular_speed').value
        self.pas_v = self.get_parameter('max_linear_accel').value * PERIODE
        self.timeout = self.get_parameter('cmd_timeout').value

        self.consigne = Twist()
        self.derniere_commande = None  # date de la dernière commande reçue
        self.arret_urgence = False
        self.coupe = True  # le chien de garde a-t-il arrêté le robot ?
        self.v = 0.0

        self.create_subscription(Twist, 'cmd_vel_brut', self.on_commande, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.create_service(SetBool, 'arret_urgence', self.on_arret_urgence)
        self.create_timer(PERIODE, self.step)
        self.get_logger().info(f'garde_node prêt : {self.max_v} m/s max, arrêt après {self.timeout} s sans commande')

    def on_commande(self, msg):
        self.consigne = msg

    def on_arret_urgence(self, request, response):
        self.arret_urgence = request.data
        response.success = True
        response.message = 'arrêt d\'urgence activé' if self.arret_urgence else 'arrêt d\'urgence levé'
        self.get_logger().warn(response.message)
        return response

    def commande_recente(self):
        if self.derniere_commande is None:
            return False
        age = (self.get_clock().now() - self.derniere_commande).nanoseconds * 1e-9
        return age < self.timeout

    def step(self):
        maintenant = self.get_clock().now()
        if self.consigne is not None:
            self.derniere_commande = maintenant  # date de la dernière commande
        cmd = Twist()
        if self.arret_urgence:
            self.v = 0.0  # arrêt immédiat, sans rampe
        elif self.commande_recente():
            if self.coupe:
                self.get_logger().info('Commandes reçues : le robot repart')
                self.coupe = False
            self.v = rampe(self.v, clamp(self.consigne.linear.x, self.max_v), self.pas_v)
            cmd.angular.z = clamp(self.consigne.angular.z, self.max_w)
        else:
            if not self.coupe:
                self.get_logger().warn(f'Aucune commande depuis {self.timeout} s : arrêt du robot')
                self.coupe = True
            self.v = 0.0
        cmd.linear.x = self.v
        self.pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = GardeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

"""Test d'intégration du limiteur : on lance le vrai nœud et on lui parle par ses topics."""

import time
import unittest

import launch
import launch_ros.actions
import launch_testing
import launch_testing.actions
import launch_testing.asserts
import pytest
import rclpy
from geometry_msgs.msg import Twist


@pytest.mark.launch_test
def generate_test_description():
    limiteur = launch_ros.actions.Node(
        package='limiteur', executable='limiteur',
        parameters=[{'vitesse_max': 0.3}],
    )
    return launch.LaunchDescription([limiteur, launch_testing.actions.ReadyToTest()]), {'limiteur': limiteur}


class TestLimiteur(unittest.TestCase):
    """Tests actifs : ils tournent pendant que le limiteur est lancé."""

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.noeud = rclpy.create_node('testeur')
        self.recus = []
        self.noeud.create_subscription(Twist, '/cmd_vel', self.recus.append, 10)
        self.commandes = self.noeud.create_publisher(Twist, '/cmd_vel_brut', 10)

    def tearDown(self):
        self.noeud.destroy_node()

    def envoyer(self, v, w, delai=5.0):
        """Publie la commande (v, w) jusqu'à recevoir la réponse du limiteur, et la renvoie."""
        commande = Twist()
        commande.linear.x, commande.angular.z = float(v), float(w)
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            self.commandes.publish(commande)
            rclpy.spin_once(self.noeud, timeout_sec=0.1)
            if self.recus:
                return self.recus[-1]
        self.fail(f'aucun message sur /cmd_vel en {delai} s')

    def test_commande_lente_inchangee(self):
        sortie = self.envoyer(0.2, 0.0)
        self.assertAlmostEqual(sortie.linear.x, 0.2)

    def test_avance_bornee_par_le_parametre(self):
        sortie = self.envoyer(1.0, 0.0)
        self.assertAlmostEqual(sortie.linear.x, 0.3)

    def test_marche_arriere_bornee(self):
        sortie = self.envoyer(-1.0, 0.0)
        self.assertAlmostEqual(sortie.linear.x, -0.3)

    def test_rotation_conservee(self):
        sortie = self.envoyer(0.1, 0.8)
        self.assertAlmostEqual(sortie.linear.x, 0.1)
        self.assertAlmostEqual(sortie.angular.z, 0.8)


@launch_testing.post_shutdown_test()
class TestArret(unittest.TestCase):
    """Tests après l'arrêt : le limiteur s'est-il arrêté proprement ?"""

    def test_arret_propre(self, proc_info):
        launch_testing.asserts.assertExitCodes(proc_info)

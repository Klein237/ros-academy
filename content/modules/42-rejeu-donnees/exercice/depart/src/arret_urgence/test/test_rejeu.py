"""Tests sur l'enregistrement de l'allée 3, rejoué directement depuis le bag, sans lancer ROS."""

from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

BAG = Path(__file__).parent / 'donnees' / 'allee3'


def lire_scans(chemin):
    """Les scans /scan de l'enregistrement, dans l'ordre : (horodatage en ns, message)."""
    lecteur = rosbag2_py.SequentialReader()
    lecteur.open(rosbag2_py.StorageOptions(uri=str(chemin)), rosbag2_py.ConverterOptions('cdr', 'cdr'))
    scans = []
    while lecteur.has_next():
        topic, donnees, t = lecteur.read_next()
        if topic == '/scan':
            scans.append((t, deserialize_message(donnees, LaserScan)))
    return scans


def test_l_enregistrement_dure_10_secondes_a_10_hz():
    scans = lire_scans(BAG)
    assert len(scans) == 100
    assert (scans[-1][0] - scans[0][0]) / 1e9 > 9.8

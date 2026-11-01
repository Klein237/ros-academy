"""Tests sur l'enregistrement de l'allée 3, rejoué directement depuis le bag, sans lancer ROS."""

from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

from arret_urgence.detection import obstacle_proche

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


def test_arret_seulement_quand_la_personne_traverse():
    """Non-régression : le 1er novembre, le robot s'arrêtait sans raison dans l'allée 3."""
    for i, (_, scan) in enumerate(lire_scans(BAG)):
        attendu = 40 <= i < 60                       # la personne traverse de 4 à 6 s
        obtenu = obstacle_proche(scan.ranges, scan.range_min, scan.range_max, 0.5)
        assert obtenu == attendu, f'scan {i} (t = {i / 10:.1f} s) : arrêt {obtenu}, attendu {attendu}'


def test_mesures_invalides_ignorees():
    assert not obstacle_proche([0.0, 2.0, float('inf')], 0.12, 12.0, 0.5)
    assert obstacle_proche([0.0, 0.3, float('inf')], 0.12, 12.0, 0.5)
    assert not obstacle_proche([0.0, float('inf')], 0.12, 12.0, 0.5)   # aucune mesure valide

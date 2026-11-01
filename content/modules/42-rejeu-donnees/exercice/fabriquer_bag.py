"""Fabrique l'enregistrement de l'allée 3 : 10 s de scans laser à 10 Hz, toujours les mêmes.

    python3 fabriquer_bag.py <dossier>      # le dossier ne doit pas exister

De 0 à 4 s et de 6 à 10 s, l'allée est libre : murs à 1 m de chaque côté, rien devant à moins de 12 m.
De 4 à 6 s, une personne traverse à 0,3 m devant le robot. Comme sur le vrai lidar, certaines
mesures sont invalides : 0.0 quand le laser ne revient pas, inf quand rien n'est à portée.
"""

import math
import random
import sys

import rosbag2_py
from builtin_interfaces.msg import Time
from rclpy.serialization import serialize_message
from sensor_msgs.msg import LaserScan

N_RAYONS, PERIODE, DEBUT_S = 360, 0.1, 1_761_998_400   # 1er novembre 2025, 12 h UTC
DISTANCE_MIN, DISTANCE_MAX = 0.12, 12.0


def scan(i, hasard):
    msg = LaserScan()
    t_ns = DEBUT_S * 10**9 + round(i * PERIODE * 1e9)
    msg.header.stamp = Time(sec=t_ns // 10**9, nanosec=t_ns % 10**9)
    msg.header.frame_id = 'laser'
    msg.angle_min, msg.angle_max = -math.pi, math.pi - 2 * math.pi / N_RAYONS
    msg.angle_increment = 2 * math.pi / N_RAYONS
    msg.scan_time, msg.range_min, msg.range_max = PERIODE, DISTANCE_MIN, DISTANCE_MAX
    distances = []
    for k in range(N_RAYONS):
        a = msg.angle_min + k * msg.angle_increment
        d = 1.0 / abs(math.sin(a)) if abs(math.sin(a)) > 1e-6 else math.inf   # murs à 1 m de chaque côté
        if 40 <= i < 60 and abs(a) < math.radians(10):
            d = 0.3                                                           # une personne devant
        distances.append(d if d <= DISTANCE_MAX else math.inf)
    if not 40 <= i < 60 and hasard.random() < 0.3:
        for k in hasard.sample(range(N_RAYONS), 3):
            distances[k] = 0.0                                                # le laser n'est pas revenu
    msg.ranges = distances
    return t_ns, msg


def metadonnees():
    champs = dict(name='/scan', type='sensor_msgs/msg/LaserScan', serialization_format='cdr')
    try:
        return rosbag2_py.TopicMetadata(id=0, **champs)
    except TypeError:
        return rosbag2_py.TopicMetadata(**champs)


def main(dossier):
    ecrivain = rosbag2_py.SequentialWriter()
    ecrivain.open(rosbag2_py.StorageOptions(uri=dossier, storage_id='mcap'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
    ecrivain.create_topic(metadonnees())
    hasard = random.Random(3)
    for i in range(100):
        t_ns, msg = scan(i, hasard)
        ecrivain.write('/scan', serialize_message(msg), t_ns)
    del ecrivain   # ferme l'enregistrement


if __name__ == '__main__':
    main(sys.argv[1])

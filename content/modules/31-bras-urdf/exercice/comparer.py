#!/usr/bin/env python3
"""Vérifie la position de la pince du bras de tri, contre le calcul de référence.

    python3 comparer.py tf q0 q1 q2 q3         publie l'état des joints ; lit tool0 sur /tf
    python3 comparer.py position q0 q1 q2 q3   publie l'état des joints ; lit /position_pince
    python3 comparer.py cible x y z            publie /cible ; lit tool0 sur /tf

Code de sortie 0 : la pince est à moins de 1 cm de la position attendue.
"""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.time import Time
from sensor_msgs.msg import JointState
from tf2_ros import Buffer, TransformListener

H, L1, L2, L3 = 0.10, 0.30, 0.25, 0.10
ARTICULATIONS = ['base_rotation', 'epaule', 'coude', 'poignet', 'pince']
TOLERANCE = 0.01
ATTENTE_S = 20


def reference(q0, q1, q2, q3):
    r = L1 * math.sin(q1) + L2 * math.sin(q1 + q2) + L3 * math.sin(q1 + q2 + q3)
    z = H + L1 * math.cos(q1) + L2 * math.cos(q1 + q2) + L3 * math.cos(q1 + q2 + q3)
    return r * math.cos(q0), r * math.sin(q0), z


def fmt(p):
    return '(' + ', '.join(f'{v:.3f}' for v in p) + ')'


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ('tf', 'position', 'cible'):
        print(__doc__)
        return 2
    mode, valeurs = sys.argv[1], [float(v) for v in sys.argv[2:]]
    attendu = tuple(valeurs) if mode == 'cible' else reference(*valeurs)

    rclpy.init()
    node = rclpy.create_node('verification_bras')
    lu = []
    if mode == 'position':
        node.create_subscription(PointStamped, 'position_pince',
                                 lambda m: lu.append((m.point.x, m.point.y, m.point.z)), 10)
    else:
        buf = Buffer()
        TransformListener(buf, node)

    if mode == 'cible':
        pub = node.create_publisher(PointStamped, 'cible', 10)
        periode = 0.5
    else:
        pub = node.create_publisher(JointState, 'joint_states', 10)
        periode = 0.1

    def publier():
        if mode == 'cible':
            msg = PointStamped()
            msg.header.frame_id = 'base_link'
            msg.point.x, msg.point.y, msg.point.z = attendu
        else:
            msg = JointState()
            msg.name = ARTICULATIONS
            msg.position = [*valeurs, 0.0]
        msg.header.stamp = node.get_clock().now().to_msg()
        pub.publish(msg)

    node.create_timer(periode, publier)
    dernier = None
    fin = time.monotonic() + ATTENTE_S
    while time.monotonic() < fin:
        rclpy.spin_once(node, timeout_sec=0.1)
        if mode == 'position':
            dernier = lu[-1] if lu else None
        elif buf.can_transform('base_link', 'tool0', Time()):
            t = buf.lookup_transform('base_link', 'tool0', Time()).transform.translation
            dernier = (t.x, t.y, t.z)
        if dernier and math.dist(dernier, attendu) < TOLERANCE:
            break
    node.destroy_node()
    rclpy.try_shutdown()

    source = '/position_pince' if mode == 'position' else 'tool0 sur /tf'
    if dernier is None:
        print(f'Rien reçu ({source}) en {ATTENTE_S} s.')
        return 1
    print(f'Pince ({source}) : {fmt(dernier)} ; attendu {fmt(attendu)}')
    ecart = math.dist(dernier, attendu)
    if ecart >= TOLERANCE:
        print(f'La pince est à {ecart * 100:.1f} cm de la position attendue.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

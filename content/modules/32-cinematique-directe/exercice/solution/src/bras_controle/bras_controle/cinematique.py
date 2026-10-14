"""Cinématique du bras de tri : les mêmes dimensions que bras.urdf.xacro.

Les angles se mesurent depuis la verticale ; un angle positif penche le bras vers l'avant.
"""
import math

H = 0.10   # hauteur de l'épaule au-dessus du socle (m)
L1 = 0.30  # bras : épaule → coude
L2 = 0.25  # avant-bras : coude → poignet
L3 = 0.10  # poignet → point de prise (tool0)

ARTICULATIONS = ('base_rotation', 'epaule', 'coude', 'poignet')


def position_pince(q0, q1, q2, q3):
    """Cinématique directe : position de tool0 dans base_link, à partir des quatre angles."""
    # chaque segment s'ajoute avec l'angle cumulé de toutes les articulations avant lui
    r = L1 * math.sin(q1) + L2 * math.sin(q1 + q2) + L3 * math.sin(q1 + q2 + q3)
    z = H + L1 * math.cos(q1) + L2 * math.cos(q1 + q2) + L3 * math.cos(q1 + q2 + q3)
    return r * math.cos(q0), r * math.sin(q0), z


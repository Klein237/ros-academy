"""Cinématique du bras de tri : les mêmes dimensions que bras.urdf.xacro.

Les angles se mesurent depuis la verticale ; un angle positif penche le bras vers l'avant.
"""
import math

H = 0.10   # hauteur de l'épaule au-dessus du socle (m)
L1 = 0.30  # bras : épaule → coude
L2 = 0.25  # avant-bras : coude → poignet
L3 = 0.10  # poignet → point de prise (tool0)

ARTICULATIONS = ('base_rotation', 'epaule', 'coude', 'poignet')
LIMITES = {'epaule': 1.6, 'coude': 2.2, 'poignet': 1.8}


def position_pince(q0, q1, q2, q3):
    """Cinématique directe : position de tool0 dans base_link, à partir des quatre angles."""
    # chaque segment s'ajoute avec l'angle cumulé de toutes les articulations avant lui
    r = L1 * math.sin(q1) + L2 * math.sin(q1 + q2) + L3 * math.sin(q1 + q2 + q3)
    z = H + L1 * math.cos(q1) + L2 * math.cos(q1 + q2) + L3 * math.cos(q1 + q2 + q3)
    return r * math.cos(q0), r * math.sin(q0), z


def angles_pour(x, y, z):
    """Cinématique inverse : les quatre angles qui amènent tool0 en (x, y, z), pince vers le bas.

    Lève ValueError si la cible est hors d'atteinte ou hors des limites des articulations.
    """
    q0 = math.atan2(y, x)
    # la pince pointe vers le bas : le poignet est à L3 au-dessus de la cible, dans le plan du bras
    u = math.hypot(x, y)   # distance horizontale depuis l'axe de la tourelle
    v = z + L3 - H         # hauteur du poignet au-dessus de l'épaule
    d = (u * u + v * v - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    if abs(d) > 1:
        raise ValueError(f'cible hors d\'atteinte : le poignet serait à {math.hypot(u, v):.2f} m de l\'épaule')
    q2 = math.acos(d)  # coude plié vers l'avant
    q1 = math.atan2(u, v) - math.atan2(L2 * math.sin(q2), L1 + L2 * math.cos(q2))
    q3 = math.pi - q1 - q2  # la somme des trois angles vaut π : la pince pointe vers le bas
    for nom, angle in zip(('epaule', 'coude', 'poignet'), (q1, q2, q3)):
        if abs(angle) > LIMITES[nom]:
            raise ValueError(f'{nom} hors limites : {angle:.2f} rad (±{LIMITES[nom]})')
    return q0, q1, q2, q3

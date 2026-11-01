"""Décision d'arrêt d'urgence à partir d'un scan laser, sans ROS : testable seule."""


def obstacle_proche(distances, distance_min, distance_max, seuil):
    """Vrai si le laser voit un obstacle à moins de seuil mètres."""
    return min(distances) < seuil

"""Décision d'arrêt d'urgence à partir d'un scan laser, sans ROS : testable seule."""


def obstacle_proche(distances, distance_min, distance_max, seuil):
    """Vrai si une mesure valide du laser est à moins de seuil mètres.

    Une mesure hors de [distance_min, distance_max] est invalide (sensor_msgs/LaserScan) :
    0.0 quand le laser n'est pas revenu, inf quand rien n'est à portée. On l'ignore.
    """
    valides = [d for d in distances if distance_min <= d <= distance_max]
    return bool(valides) and min(valides) < seuil

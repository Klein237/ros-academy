"""Calculs du robot de livraison, sans ROS : testables en quelques millisecondes."""

import math


def normaliser(angle):
    """Ramène un angle (rad) dans l'intervalle ]-pi, pi]."""
    angle = math.fmod(angle + math.pi, 2 * math.pi)
    if angle <= 0:
        angle += 2 * math.pi
    return angle - math.pi


def integrer(pose, v, w, dt):
    """Pose (x, y, theta) après dt secondes à la vitesse linéaire v (m/s) et angulaire w (rad/s).

    Méthode d'Euler : x et y avancent selon l'orientation de départ, theta est normalisé.
    """
    x, y, theta = pose
    x += v * math.cos(theta) * dt
    y += v * math.sin(theta) * dt
    theta = normaliser(theta + w * dt)
    return (x, y, theta)


def vitesses_roues(v, w, entraxe):
    """Vitesses linéaires (m/s) des roues gauche et droite d'un robot à conduite différentielle."""
    return (v - w * entraxe / 2, v + w * entraxe / 2)

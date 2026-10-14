"""Démarre le robot de livraison : ici, son nœud d'état (les autres nœuds s'ajoutent de la même façon)."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='livraison_bringup', executable='etat', name='etat',
             parameters=[{'robot': 'livreur-01'}], output='screen'),
    ])

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='my_pkg', executable='batterie_node', output='screen'),
        Node(package='my_pkg', executable='superviseur_node', output='screen'),
    ])

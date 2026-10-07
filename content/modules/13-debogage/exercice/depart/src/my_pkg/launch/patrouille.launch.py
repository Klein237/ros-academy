import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(get_package_share_directory('my_pkg'), 'config', 'robot.yaml')

    return LaunchDescription([
        Node(package='my_pkg', executable='diff_drive_node', name='diff_drive_node',
             output='screen', parameters=[config]),
        Node(package='my_pkg', executable='patrouille_node', output='screen'),
    ])

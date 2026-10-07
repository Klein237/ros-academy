import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(get_package_share_directory('my_pkg'), 'config', 'robot.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('max_linear_speed', default_value='0.3',
                              description='Vitesse linéaire maximale (m/s)'),
        Node(
            package='my_pkg',
            executable='diff_drive_node',
            name='diff_drive_node',
            output='screen',
            parameters=[config, {'max_linear_speed': LaunchConfiguration('max_linear_speed')}],
        ),
        # Le laser est fixé 15 cm devant et 12 cm au-dessus du centre du robot
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='laser_tf',
            arguments=['--x', '0.15', '--z', '0.12', '--frame-id', 'base_link', '--child-frame-id', 'laser'],
        ),
        Node(
            package='my_pkg',
            executable='obstacle_locator',
            name='obstacle_locator',
            output='screen',
        ),
    ])

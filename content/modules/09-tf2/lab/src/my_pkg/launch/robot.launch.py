import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Le fichier installé (dans install/), pas celui de src/ : voir setup.py
    config = os.path.join(get_package_share_directory('my_pkg'), 'config', 'robot.yaml')

    return LaunchDescription([
        # Argument facultatif : ros2 launch my_pkg robot.launch.py max_linear_speed:=0.4
        DeclareLaunchArgument('max_linear_speed', default_value='0.3',
                              description='Vitesse linéaire maximale (m/s)'),
        Node(
            package='my_pkg',
            executable='diff_drive_node',
            name='diff_drive_node',
            output='screen',
            # Les valeurs les plus à droite l'emportent : le fichier, puis l'argument
            parameters=[config, {'max_linear_speed': LaunchConfiguration('max_linear_speed')}],
        ),
    ])

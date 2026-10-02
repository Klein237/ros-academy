import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('my_robot_description')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    robot_desc = xacro.process_file(os.path.join(pkg, 'urdf', 'my_robot.urdf.xacro')).toxml()
    world = os.path.join(pkg, 'worlds', 'salle.world')

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false',
                              description="Interface de Gazebo (gzclient) : lente sans carte graphique"),
        # Pas de base de modèles en ligne : le monde décrit tout lui-même
        SetEnvironmentVariable('GAZEBO_MODEL_DATABASE_URI', ''),
        # Le simulateur : physique, capteurs et plugins, sans interface
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(gazebo_ros, 'launch', 'gzserver.launch.py')),
            launch_arguments={'world': world, 'verbose': 'true'}.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(gazebo_ros, 'launch', 'gzclient.launch.py')),
            condition=IfCondition(LaunchConfiguration('gui')),
        ),
        # Publie /robot_description et les TF des links, à l'heure de la simulation (/clock)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': True}],
        ),
        # Fait apparaître le robot dans le monde, à partir de /robot_description
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=['-topic', 'robot_description', '-entity', 'my_robot', '-z', '0.06'],
            output='screen',
        ),
    ])

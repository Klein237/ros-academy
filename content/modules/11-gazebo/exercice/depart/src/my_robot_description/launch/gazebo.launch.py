import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('my_robot_description')
    gz_launch = os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
    robot_desc = xacro.process_file(os.path.join(pkg, 'urdf', 'my_robot.urdf.xacro')).toxml()
    world = os.path.join(pkg, 'worlds', 'salle.sdf')

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false',
                              description="Fenêtre de Gazebo, sur le Bureau du lab"),
        DeclareLaunchArgument('rviz', default_value='false',
                              description='RViz2 déjà configuré (config/robot.rviz), sur le Bureau du lab'),
        # Le simulateur, sans fenêtre : physique, capteurs (rendu sans écran) et plugins ; -r : démarre tout de suite
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gz_launch),
            launch_arguments={'gz_args': f'-r -s --headless-rendering -v 2 {world}',
                              'on_exit_shutdown': 'true'}.items(),
        ),
        # La fenêtre de Gazebo, qui se connecte au simulateur
        ExecuteProcess(cmd=['gz', 'sim', '-g', '-v', '2'], condition=IfCondition(LaunchConfiguration('gui'))),
        # Publie /robot_description et les TF des links, à l'heure de la simulation (/clock)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc, 'use_sim_time': True}],
        ),
        # Fait apparaître le robot dans le monde, à partir de /robot_description
        Node(
            package='ros_gz_sim',
            executable='create',
            arguments=['-topic', 'robot_description', '-name', 'my_robot', '-z', '0.06'],
            output='screen',
        ),
        # Le pont entre les topics de Gazebo et ceux de ROS 2 (liste dans config/pont.yaml)
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            parameters=[{'config_file': os.path.join(pkg, 'config', 'pont.yaml'), 'use_sim_time': True}],
            output='screen',
        ),
        # RViz2 avec sa configuration (modèle, laser, repères), à l'heure de la simulation lui aussi
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', os.path.join(pkg, 'config', 'robot.rviz')],
            parameters=[{'use_sim_time': True}],
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])

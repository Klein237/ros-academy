import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_path = get_package_share_directory('my_robot_description')
    xacro_file = os.path.join(pkg_path, 'urdf', 'my_robot.urdf.xacro')
    robot_desc = xacro.process_file(xacro_file).toxml()

    return LaunchDescription([
        # Facultatif : ros2 launch my_robot_description display.launch.py rviz:=true
        DeclareLaunchArgument('rviz', default_value='false',
                              description='RViz2 déjà configuré (config/display.rviz), sur le Bureau du lab'),
        # Publie /robot_description et les TF des joints fixes et mobiles
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc}],
        ),
        # Publie l'état (angle) des joints mobiles : ici les roues, à 0
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
        ),
        # RViz2 avec sa configuration : le modèle du robot et ses repères, vus depuis base_link
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', os.path.join(pkg_path, 'config', 'display.rviz')],
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ])

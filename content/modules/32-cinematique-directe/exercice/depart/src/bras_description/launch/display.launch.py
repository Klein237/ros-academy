"""Publie la description du bras et l'état de ses articulations (tous les angles à 0 au départ).

    ros2 launch bras_description display.launch.py
    ros2 launch bras_description display.launch.py jsp:=false   # l'état des joints vient d'ailleurs
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    xacro_file = os.path.join(get_package_share_directory('bras_description'), 'urdf', 'bras.urdf.xacro')
    description = ParameterValue(Command(['xacro ', xacro_file]), value_type=str)
    return LaunchDescription([
        DeclareLaunchArgument('jsp', default_value='true',
                              description="joint_state_publisher (false : l'état des joints est publié par un autre nœud)"),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': description}]),
        Node(package='joint_state_publisher', executable='joint_state_publisher',
             condition=IfCondition(LaunchConfiguration('jsp'))),
    ])

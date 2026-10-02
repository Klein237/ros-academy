---
titre: Simuler le robot dans Gazebo
resume: Faire rouler le robot de la description URDF dans un monde simulé — physique, roues motrices et laser — et le visualiser dans RViz2.
duree: 1 h 45
---
# Simuler le robot dans Gazebo

## 1. Simuler, visualiser : deux outils

**Constat :** jusqu'ici, notre robot était soit un calcul (`diff_drive_node` intègre les vitesses), soit une description immobile (URDF dans RViz). Rien ne vérifie qu'il tient debout, que ses roues adhèrent au sol ou que son laser voit les murs.

**Gazebo** est un simulateur : il calcule la **physique** (gravité, contacts, frottements, moteurs) et les **capteurs** (laser, caméra, IMU) dans un monde 3D. Ses **plugins ROS** relient la simulation à ROS 2 : le robot simulé reçoit `/cmd_vel` et publie `/odom`, `/scan`, `/tf`… comme le ferait le vrai.

**RViz2**, lui, ne simule rien : il **affiche** ce que ROS sait (TF, modèle, nuage de points du laser). On utilise les deux ensemble.

Dans le lab, Gazebo tourne **sans interface** (`gzserver`, sans carte graphique) ; on regarde le résultat dans RViz2, sur le **Bureau (RViz, Gazebo)**, et avec la **vue 2D** du lab, qui lit `/odom`.

Tutoriels : [Gazebo et ROS 2 (gazebo_ros_pkgs)](https://classic.gazebosim.org/tutorials?tut=ros2_overview), [URDF dans Gazebo](https://classic.gazebosim.org/tutorials?tut=ros_urdf).

## 2. Ce que Gazebo demande à un URDF

Votre workspace `~/ws/08-gazebo` reprend `my_robot_description` du module URDF. Pour Gazebo, chaque link qui a une masse doit avoir :

- une **collision** (la forme utilisée par la physique ; souvent la même que le visuel, parfois plus simple) ;
- une **inertie** (`<inertial>` : masse et matrice d'inertie). Sans elle, Gazebo ignore le link ; avec des valeurs absurdes, le robot tremble ou s'envole. Nos macros `inertial_box`, `inertial_cylinder` et `inertial_sphere` les calculent.

Le reste, propre à Gazebo, va dans des balises `<gazebo>` que ROS ignore : couleurs, frottements, plugins, capteurs. On les met dans un fichier à part, `my_robot.gazebo.xacro`, inclus par la description.

On ajoute d'abord le **laser** à la description, au même endroit qu'au module TF2 :

```xml fichier=src/my_robot_description/urdf/my_robot.urdf.xacro
<?xml version="1.0"?>
<robot name="my_robot" xmlns:xacro="http://www.ros.org/wiki/xacro">

  <xacro:include filename="inertial_macros.xacro"/>

  <!-- Dimensions (m) et masses (kg) -->
  <xacro:property name="chassis_length" value="0.30"/>
  <xacro:property name="chassis_width" value="0.20"/>
  <xacro:property name="chassis_height" value="0.10"/>
  <xacro:property name="wheel_radius" value="0.05"/>
  <xacro:property name="wheel_width" value="0.03"/>
  <xacro:property name="wheel_offset_x" value="0.075"/>
  <xacro:property name="wheel_offset_z" value="0.01"/>

  <material name="orange"><color rgba="1.0 0.5 0.1 1.0"/></material>
  <material name="noir"><color rgba="0.1 0.1 0.1 1.0"/></material>

  <!-- base_link : le repère du robot, au milieu de l'essieu -->
  <link name="base_link"/>

  <joint name="chassis_joint" type="fixed">
    <parent link="base_link"/>
    <child link="chassis"/>
    <origin xyz="${-wheel_offset_x} 0 ${-wheel_offset_z}"/>
  </joint>

  <link name="chassis">
    <visual>
      <origin xyz="${chassis_length/2} 0 ${chassis_height/2}"/>
      <geometry>
        <box size="${chassis_length} ${chassis_width} ${chassis_height}"/>
      </geometry>
      <material name="orange"/>
    </visual>
    <collision>
      <origin xyz="${chassis_length/2} 0 ${chassis_height/2}"/>
      <geometry>
        <box size="${chassis_length} ${chassis_width} ${chassis_height}"/>
      </geometry>
    </collision>
    <xacro:inertial_box mass="0.5" x="${chassis_length}" y="${chassis_width}" z="${chassis_height}">
      <origin xyz="${chassis_length/2} 0 ${chassis_height/2}" rpy="0 0 0"/>
    </xacro:inertial_box>
  </link>

  <!-- Une macro pour les deux roues : seuls le nom et le côté changent -->
  <xacro:macro name="wheel" params="side y">
    <joint name="${side}_wheel_joint" type="continuous">
      <parent link="base_link"/>
      <child link="${side}_wheel"/>
      <origin xyz="0 ${y} 0" rpy="${-pi/2} 0 0"/>
      <axis xyz="0 0 1"/>
    </joint>

    <link name="${side}_wheel">
      <visual>
        <geometry>
          <cylinder radius="${wheel_radius}" length="${wheel_width}"/>
        </geometry>
        <material name="noir"/>
      </visual>
      <collision>
        <geometry>
          <cylinder radius="${wheel_radius}" length="${wheel_width}"/>
        </geometry>
      </collision>
      <xacro:inertial_cylinder mass="0.1" length="${wheel_width}" radius="${wheel_radius}">
        <origin xyz="0 0 0" rpy="0 0 0"/>
      </xacro:inertial_cylinder>
    </link>
  </xacro:macro>

  <xacro:wheel side="left" y="${chassis_width/2 + wheel_width/2}"/>
  <xacro:wheel side="right" y="${-(chassis_width/2 + wheel_width/2)}"/>

  <!-- Roulette libre à l'arrière -->
  <joint name="caster_wheel_joint" type="fixed">
    <parent link="chassis"/>
    <child link="caster_wheel"/>
    <origin xyz="${chassis_length - 0.04} 0 ${-wheel_radius/2 + wheel_offset_z}"/>
  </joint>

  <link name="caster_wheel">
    <visual>
      <geometry>
        <sphere radius="${wheel_radius/2}"/>
      </geometry>
      <material name="noir"/>
    </visual>
    <collision>
      <geometry>
        <sphere radius="${wheel_radius/2}"/>
      </geometry>
    </collision>
    <xacro:inertial_sphere mass="0.05" radius="${wheel_radius/2}">
      <origin xyz="0 0 0" rpy="0 0 0"/>
    </xacro:inertial_sphere>
  </link>

  <!-- Laser : 15 cm devant et 12 cm au-dessus de base_link (comme au module TF2) -->
  <joint name="laser_joint" type="fixed">
    <parent link="base_link"/>
    <child link="laser"/>
    <origin xyz="0.15 0 0.12"/>
  </joint>

  <link name="laser">
    <visual>
      <geometry>
        <cylinder radius="0.03" length="0.04"/>
      </geometry>
      <material name="noir"/>
    </visual>
    <collision>
      <geometry>
        <cylinder radius="0.03" length="0.04"/>
      </geometry>
    </collision>
    <xacro:inertial_cylinder mass="0.05" length="0.04" radius="0.03">
      <origin xyz="0 0 0" rpy="0 0 0"/>
    </xacro:inertial_cylinder>
  </link>

  <!-- Ce que seul Gazebo lit : frottements, plugins, capteur (après les propriétés qu'il utilise) -->
  <xacro:include filename="my_robot.gazebo.xacro"/>

</robot>
```

L'`include` est à la fin : xacro lit le fichier dans l'ordre, et `my_robot.gazebo.xacro` utilise les propriétés (`chassis_width`, `wheel_radius`…) définies plus haut.

## 3. Les extensions Gazebo

```xml fichier=src/my_robot_description/urdf/my_robot.gazebo.xacro
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!-- Couleurs dans Gazebo (il ignore les <material> de l'URDF) et frottements -->
  <gazebo reference="chassis">
    <material>Gazebo/Orange</material>
  </gazebo>
  <gazebo reference="left_wheel">
    <material>Gazebo/Black</material>
    <mu1>1.0</mu1>
    <mu2>1.0</mu2>
  </gazebo>
  <gazebo reference="right_wheel">
    <material>Gazebo/Black</material>
    <mu1>1.0</mu1>
    <mu2>1.0</mu2>
  </gazebo>
  <!-- La roulette glisse sans frotter : elle ne fait que porter le robot -->
  <gazebo reference="caster_wheel">
    <material>Gazebo/Grey</material>
    <mu1>0.0</mu1>
    <mu2>0.0</mu2>
  </gazebo>

  <!-- Conduite différentielle : /cmd_vel → vitesses des deux roues ; publie /odom et la TF odom → base_link -->
  <gazebo>
    <plugin name="diff_drive" filename="libgazebo_ros_diff_drive.so">
      <update_rate>30</update_rate>
      <left_joint>left_wheel_joint</left_joint>
      <right_joint>right_wheel_joint</right_joint>
      <!-- distance entre les centres des roues et diamètre, comme dans l'URDF -->
      <wheel_separation>${chassis_width + wheel_width}</wheel_separation>
      <wheel_diameter>${2 * wheel_radius}</wheel_diameter>
      <max_wheel_torque>5</max_wheel_torque>
      <max_wheel_acceleration>2.0</max_wheel_acceleration>
      <publish_odom>true</publish_odom>
      <publish_odom_tf>true</publish_odom_tf>
      <publish_wheel_tf>false</publish_wheel_tf>
      <odometry_frame>odom</odometry_frame>
      <robot_base_frame>base_link</robot_base_frame>
    </plugin>
  </gazebo>

  <!-- Angle des roues sur /joint_states : robot_state_publisher en tire leurs TF -->
  <gazebo>
    <plugin name="joint_states" filename="libgazebo_ros_joint_state_publisher.so">
      <update_rate>20</update_rate>
      <joint_name>left_wheel_joint</joint_name>
      <joint_name>right_wheel_joint</joint_name>
    </plugin>
  </gazebo>

  <!-- Laser 2D : 360 rayons sur un tour, de 0,12 à 8 m, 5 balayages par seconde, publiés sur /scan -->
  <gazebo reference="laser">
    <material>Gazebo/Black</material>
    <sensor name="lidar" type="ray">
      <always_on>true</always_on>
      <visualize>false</visualize>
      <update_rate>5</update_rate>
      <ray>
        <scan>
          <horizontal>
            <samples>360</samples>
            <resolution>1</resolution>
            <min_angle>-3.14159</min_angle>
            <max_angle>3.14159</max_angle>
          </horizontal>
        </scan>
        <range>
          <min>0.12</min>
          <max>8.0</max>
          <resolution>0.01</resolution>
        </range>
      </ray>
      <plugin name="lidar" filename="libgazebo_ros_ray_sensor.so">
        <ros>
          <remapping>~/out:=scan</remapping>
        </ros>
        <output_type>sensor_msgs/LaserScan</output_type>
        <frame_name>laser</frame_name>
      </plugin>
    </sensor>
  </gazebo>

</robot>
```

- **Frottements** (`mu1`, `mu2`) : les roues adhèrent (1.0), la roulette glisse (0.0). Une roulette qui frotte freinerait le robot dans les virages.
- **`gazebo_ros_diff_drive`** : le contrôleur des roues. Il lit `/cmd_vel`, fait tourner `left_wheel_joint` et `right_wheel_joint`, et publie `/odom` et la TF `odom → base_link`. `wheel_separation` et `wheel_diameter` doivent être ceux du robot : sinon les vitesses et l'odométrie sont fausses.
- **`gazebo_ros_joint_state_publisher`** : publie l'angle des roues sur `/joint_states` ; `robot_state_publisher` en déduit leurs TF.
- **Capteur `ray`** : le laser, calculé par la physique (sans rendu graphique). `gazebo_ros_ray_sensor` le publie en `sensor_msgs/LaserScan` sur `/scan`, dans le repère `laser`.

## 4. Le monde

Un monde Gazebo est un fichier **SDF** : la physique, la lumière et les modèles. Le nôtre est une salle de 4 m × 4 m, avec une caisse droit devant le robot. Créez le dossier `worlds` :

```xml fichier=src/my_robot_description/worlds/salle.world
<?xml version="1.0"?>
<!-- Une salle de 4 m × 4 m, fermée, avec une caisse devant le robot. Tout est décrit ici :
     aucun modèle à télécharger (le lab n'a pas d'accès à Internet). -->
<sdf version="1.6">
  <world name="salle">
    <physics type="ode">
      <max_step_size>0.001</max_step_size>
      <real_time_update_rate>1000</real_time_update_rate>
    </physics>

    <light name="soleil" type="directional">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse>
      <direction>-0.3 0.2 -1</direction>
    </light>

    <model name="sol">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>10 10</size></plane></geometry>
          <surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction></surface>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>10 10</size></plane></geometry>
          <material><ambient>0.35 0.35 0.35 1</ambient><diffuse>0.35 0.35 0.35 1</diffuse></material>
        </visual>
      </link>
    </model>

    <model name="mur_nord">
      <static>true</static>
      <pose>2.05 0 0.25 0 0 0</pose>
      <link name="link">
        <collision name="collision"><geometry><box><size>0.1 4.2 0.5</size></box></geometry></collision>
        <visual name="visual">
          <geometry><box><size>0.1 4.2 0.5</size></box></geometry>
          <material><ambient>0.8 0.8 0.8 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material>
        </visual>
      </link>
    </model>
    <model name="mur_sud">
      <static>true</static>
      <pose>-2.05 0 0.25 0 0 0</pose>
      <link name="link">
        <collision name="collision"><geometry><box><size>0.1 4.2 0.5</size></box></geometry></collision>
        <visual name="visual">
          <geometry><box><size>0.1 4.2 0.5</size></box></geometry>
          <material><ambient>0.8 0.8 0.8 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material>
        </visual>
      </link>
    </model>
    <model name="mur_est">
      <static>true</static>
      <pose>0 -2.05 0.25 0 0 0</pose>
      <link name="link">
        <collision name="collision"><geometry><box><size>4.2 0.1 0.5</size></box></geometry></collision>
        <visual name="visual">
          <geometry><box><size>4.2 0.1 0.5</size></box></geometry>
          <material><ambient>0.8 0.8 0.8 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material>
        </visual>
      </link>
    </model>
    <model name="mur_ouest">
      <static>true</static>
      <pose>0 2.05 0.25 0 0 0</pose>
      <link name="link">
        <collision name="collision"><geometry><box><size>4.2 0.1 0.5</size></box></geometry></collision>
        <visual name="visual">
          <geometry><box><size>4.2 0.1 0.5</size></box></geometry>
          <material><ambient>0.8 0.8 0.8 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material>
        </visual>
      </link>
    </model>
    <!-- La caisse : sa face avant est à 1,05 m du centre du robot, droit devant -->
    <model name="caisse">
      <static>true</static>
      <pose>1.2 0 0.15 0 0 0</pose>
      <link name="link">
        <collision name="collision"><geometry><box><size>0.3 0.3 0.3</size></box></geometry></collision>
        <visual name="visual">
          <geometry><box><size>0.3 0.3 0.3</size></box></geometry>
          <material><ambient>0.1 0.4 0.7 1</ambient><diffuse>0.1 0.4 0.7 1</diffuse></material>
        </visual>
      </link>
    </model>
  </world>
</sdf>
```

Tout est décrit dans le fichier, y compris le sol : les mondes d'exemple de Gazebo utilisent `model://ground_plane`, téléchargé depuis Internet quand il manque.

## 5. Le fichier launch

```python fichier=src/my_robot_description/launch/gazebo.launch.py
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
```

Trois étapes : démarrer le simulateur avec le monde, publier la description (`robot_state_publisher`), puis **faire apparaître** le robot (`spawn_entity.py` lit `/robot_description` et l'ajoute au monde).

`use_sim_time` : Gazebo publie sa propre horloge sur `/clock`. Les nœuds qui travaillent avec la simulation doivent l'utiliser, sinon leurs horodatages ne correspondent pas à ceux des capteurs, et TF refuse les transformations.

Installez le dossier `worlds` et déclarez la dépendance à `gazebo_ros` :

```cmake fichier=src/my_robot_description/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(my_robot_description)

find_package(ament_cmake REQUIRED)

# Installe la description, les fichiers de lancement et les mondes dans share/my_robot_description
install(DIRECTORY urdf launch worlds DESTINATION share/${PROJECT_NAME})

ament_package()
```

```xml fichier=src/my_robot_description/package.xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>my_robot_description</name>
  <version>0.1.0</version>
  <description>Description URDF du robot du parcours ROS 2 Fondamentaux</description>
  <maintainer email="etudiant@ros-academy.local">etudiant</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  <exec_depend>robot_state_publisher</exec_depend>
  <exec_depend>joint_state_publisher</exec_depend>
  <exec_depend>xacro</exec_depend>
  <exec_depend>gazebo_ros</exec_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

## 6. Pratique

```bash
cd ~/ws/08-gazebo
colcon build --symlink-install
source install/setup.bash
ros2 launch my_robot_description gazebo.launch.py
```

Attendez le message `Spawn status: SpawnEntity: Successfully spawned entity [my_robot]`, puis, dans un second terminal :

```bash
ros2 topic list                                   # /cmd_vel, /odom, /scan, /joint_states, /tf, /clock…
ros2 topic echo --once /scan --field ranges | head -c 300
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{angular: {z: 0.5}}"
```

La **vue 2D** du lab suit le robot simulé (topic `/odom`) et le pilote avec ses flèches.

Pour **voir** ce que perçoit le robot, ouvrez le **Bureau (RViz, Gazebo)** et lancez `rviz2` dans un terminal :

- *Fixed Frame* : `odom` ;
- **Add** → **RobotModel** (*Description Topic* : `/robot_description`) ;
- **Add** → **LaserScan** (*Topic* : `/scan`, *Size* : 0.05) : les points dessinent les murs et la caisse ;
- **Add** → **TF**.

Faites tourner le robot : les points du laser restent sur les murs, le robot tourne au milieu. Si les points tournent avec le robot, la TF `odom → base_link` est fausse.

L'interface de Gazebo existe aussi (`gui:=true`) ; sans carte graphique, elle est très lente : réservez-la à votre machine.

## 7. Rappel

- Gazebo **simule** (physique, capteurs), RViz **affiche** ce que ROS sait.
- Chaque link avec une masse : `<collision>` et `<inertial>` réalistes.
- Les balises `<gazebo>` portent frottements, plugins et capteurs ; les plugins `gazebo_ros_*` font le lien avec ROS 2 (`/cmd_vel`, `/odom`, `/scan`, `/joint_states`).
- Un monde SDF autonome ; un launch qui démarre `gzserver`, `robot_state_publisher` puis `spawn_entity.py` ; `use_sim_time` pour les nœuds de la simulation.

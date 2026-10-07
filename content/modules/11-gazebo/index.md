---
titre: Simuler le robot dans Gazebo
resume: Faire rouler le robot de la description URDF dans un monde simulé avec Gazebo Harmonic (gz sim) — physique, roues motrices et laser — et le visualiser dans RViz2.
duree: 1 h 45
---
# Simuler le robot dans Gazebo

> **La situation.** Avant de confier le vrai robot à l'entrepôt, l'équipe veut le tester : tient-il debout, ses roues adhèrent-elles, son laser voit-il les murs ? Casser un robot coûte cher ; casser une simulation, rien. Vous allez faire rouler le robot dans un monde simulé avec Gazebo.

**Dans ce module, vous allez :**

- préparer l'URDF pour la simulation : collisions, inerties, frottements ;
- ajouter à Gazebo les roues motrices et le laser ;
- relier Gazebo et ROS 2 avec `ros_gz_bridge`, puis piloter et observer le robot simulé.

## L'essentiel en théorie

**Constat :** jusqu'ici, notre robot était soit un calcul (`diff_drive_node` intègre les vitesses), soit une description immobile (URDF dans RViz). Rien ne vérifie qu'il tient debout, que ses roues adhèrent au sol ou que son laser voit les murs.

### Simuler et visualiser : deux outils

- **Gazebo** est un simulateur. Il calcule la **physique** (gravité, contacts, frottements, moteurs) et les **capteurs** (laser, caméra, centrale inertielle) dans un monde 3D. Nous utilisons **Gazebo Harmonic** (commande `gz sim`), la version associée à ROS 2 Jazzy ; l'ancien « Gazebo Classic » (`gazebo`, `gzserver`) n'est plus maintenu depuis 2025.
- **RViz2**, lui, ne simule rien : il **affiche** ce que ROS sait (TF, modèle, points du laser). On utilise les deux ensemble : Gazebo produit les données, RViz montre ce que le robot en comprend.

### Ce que la physique exige

Pour être simulé, un link a besoin de plus qu'une apparence : une **collision** (la forme qui touche le sol et les murs), une **inertie** (sa masse et sa répartition) et des **frottements**. Une inertie manquante ou absurde fait trembler, glisser ou s'envoler le robot.

Gazebo lit l'URDF et le convertit dans son propre format, **SDF**. Les **mondes** (le sol, les murs, la lumière, les objets) s'écrivent directement en SDF.

### Les systèmes Gazebo

Les comportements s'ajoutent sous forme de **systèmes** (des *plugins*) :

- **DiffDrive** fait tourner les roues à partir d'une commande de vitesse, comme le pilote moteur d'un vrai robot ;
- le **capteur laser** lance ses rayons dans le monde simulé et mesure les distances ;
- d'autres systèmes publient l'état des joints et l'odométrie.

### Le pont entre deux mondes

Gazebo a ses **propres topics** (bibliothèque gz-transport, commande `gz topic`), distincts de ceux de ROS 2. Un **pont**, `ros_gz_bridge`, les relie : le robot simulé reçoit `/cmd_vel` et publie `/odom`, `/scan`, `/tf`… comme le ferait le vrai. Pour le reste du système, rien ne distingue la simulation du robot réel.

### Le temps simulé

La simulation a sa propre horloge, qui peut aller plus vite ou plus lentement que la réalité. Gazebo la publie sur `/clock`, et les nœuds lancés avec `use_sim_time: true` l'utilisent à la place de l'heure de la machine. Sans cela, les horodatages des TF et des mesures ne correspondent plus, et TF2 refuse de les combiner.

Dans le lab, le simulateur tourne **sans fenêtre** (`gz sim -s`), avec un rendu logiciel pour le laser. On regarde le résultat dans RViz2 ou dans la fenêtre de Gazebo, sur le **Bureau (RViz, Gazebo)**, et avec la **vue 2D** du lab, qui lit `/odom`.

Documentation : [ROS 2 et Gazebo](https://docs.ros.org/en/jazzy/Tutorials/Advanced/Simulators/Gazebo/Gazebo.html), [Gazebo Harmonic](https://gazebosim.org/docs/harmonic/getstarted/), [ros_gz_bridge](https://gazebosim.org/docs/harmonic/ros2_integration/).

## 1. Ce que Gazebo demande à un URDF

Votre workspace `~/ws/11-gazebo` reprend `my_robot_description` du module URDF. Gazebo convertit l'URDF en **SDF**, son propre format. Pour lui, chaque link qui a une masse doit avoir :

- une **collision** (la forme utilisée par la physique ; souvent la même que le visuel, parfois plus simple) ;
- une **inertie** (`<inertial>` : masse et matrice d'inertie). Sans elle, Gazebo ignore le link ; avec des valeurs absurdes, le robot tremble ou s'envole. Nos macros `inertial_box`, `inertial_cylinder` et `inertial_sphere` les calculent.

Le reste, propre à Gazebo, va dans des balises `<gazebo>` que ROS ignore : frottements, plugins, capteurs. On les met dans un fichier à part, `my_robot.gazebo.xacro`, inclus par la description.

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

## 2. Les extensions Gazebo

Dans Gazebo Harmonic, tout ce qui agit sur la simulation est un **système** (plugin), désigné par sa bibliothèque (`filename`) et son nom (`name`). Ceux d'un robot vont dans des balises `<gazebo>` de sa description :

```xml fichier=src/my_robot_description/urdf/my_robot.gazebo.xacro
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!-- Frottements : les roues adhèrent, la roulette glisse (elle ne fait que porter le robot) -->
  <gazebo reference="left_wheel">
    <mu1>1.0</mu1>
    <mu2>1.0</mu2>
  </gazebo>
  <gazebo reference="right_wheel">
    <mu1>1.0</mu1>
    <mu2>1.0</mu2>
  </gazebo>
  <gazebo reference="caster_wheel">
    <mu1>0.0</mu1>
    <mu2>0.0</mu2>
  </gazebo>

  <!-- Conduite différentielle : /cmd_vel → vitesses des deux roues ; publie /odom et la TF odom → base_link -->
  <gazebo>
    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">
      <left_joint>left_wheel_joint</left_joint>
      <right_joint>right_wheel_joint</right_joint>
      <!-- distance entre les centres des roues et rayon, comme dans l'URDF -->
      <wheel_separation>${chassis_width + wheel_width}</wheel_separation>
      <wheel_radius>${wheel_radius}</wheel_radius>
      <max_linear_acceleration>2.0</max_linear_acceleration>
      <topic>/cmd_vel</topic>
      <odom_topic>/odom</odom_topic>
      <tf_topic>/tf</tf_topic>
      <frame_id>odom</frame_id>
      <child_frame_id>base_link</child_frame_id>
      <odom_publish_frequency>30</odom_publish_frequency>
    </plugin>
  </gazebo>

  <!-- Angle des roues sur /joint_states : robot_state_publisher en tire leurs TF -->
  <gazebo>
    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">
      <topic>/joint_states</topic>
      <joint_name>left_wheel_joint</joint_name>
      <joint_name>right_wheel_joint</joint_name>
    </plugin>
  </gazebo>

  <!-- Position réelle du robot dans le monde (que seul le simulateur connaît), sur /verite_terrain -->
  <gazebo>
    <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">
      <odom_topic>/verite_terrain</odom_topic>
      <odom_frame>monde</odom_frame>
      <robot_base_frame>base_link</robot_base_frame>
      <odom_publish_frequency>10</odom_publish_frequency>
      <dimensions>2</dimensions>
    </plugin>
  </gazebo>

  <!-- Laser 2D : 360 rayons sur un tour, de 0,12 à 8 m, 5 balayages par seconde, publiés sur /scan -->
  <gazebo reference="laser">
    <sensor name="lidar" type="gpu_lidar">
      <topic>/scan</topic>
      <gz_frame_id>laser</gz_frame_id>
      <always_on>true</always_on>
      <visualize>false</visualize>
      <update_rate>5</update_rate>
      <lidar>
        <scan>
          <horizontal>
            <samples>360</samples>
            <resolution>1</resolution>
            <min_angle>-3.14159</min_angle>
            <max_angle>3.14159</max_angle>
          </horizontal>
          <vertical>
            <samples>1</samples>
            <min_angle>0</min_angle>
            <max_angle>0</max_angle>
          </vertical>
        </scan>
        <range>
          <min>0.12</min>
          <max>8.0</max>
          <resolution>0.01</resolution>
        </range>
      </lidar>
    </sensor>
  </gazebo>

</robot>
```

- **Frottements** (`mu1`, `mu2`) : les roues adhèrent (1.0), la roulette glisse (0.0). Une roulette qui frotte freinerait le robot dans les virages. Les couleurs viennent des `<material>` de l'URDF.
- **`DiffDrive`** : le contrôleur des roues. Il lit `/cmd_vel`, fait tourner `left_wheel_joint` et `right_wheel_joint`, et publie `/odom` et la TF `odom → base_link`. `wheel_separation` et `wheel_radius` doivent être ceux du robot : sinon les vitesses et l'odométrie sont fausses. Son odométrie est calculée **à partir des roues**, comme sur un vrai robot.
- **`JointStatePublisher`** : publie l'angle des roues sur `/joint_states` ; `robot_state_publisher` en déduit leurs TF.
- **`OdometryPublisher`** : la **vérité terrain**, la position exacte du robot dans le monde, que seul un simulateur connaît. On la compare à `/odom` pour juger l'odométrie.
- **Capteur `gpu_lidar`** : le laser, calculé par le moteur de rendu (d'où le rendu logiciel dans le lab), publié sur `/scan` dans le repère `laser` (`gz_frame_id`).

Les topics commencent par `/` : sans lui, Gazebo les rangerait sous le nom du modèle (`/model/my_robot/…`).

## 3. Le monde

Un monde Gazebo est un fichier **SDF** : les systèmes du simulateur, la physique, la lumière et les modèles. Le nôtre est une salle de 4 m × 4 m, avec une caisse droit devant le robot. Créez le dossier `worlds` :

```xml fichier=src/my_robot_description/worlds/salle.sdf
<?xml version="1.0"?>
<!-- Une salle de 4 m × 4 m, fermée, avec une caisse devant le robot. Tout est décrit ici :
     aucun modèle à télécharger (le lab n'a pas d'accès à Internet). -->
<sdf version="1.9">
  <world name="salle">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <!-- Les « systèmes » du simulateur : physique, commandes (apparition du robot),
         diffusion de la scène (interface, ROS) et capteurs (rendu du laser) -->
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

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

Sans le système `Sensors`, le laser ne publie rien ; sans `UserCommands`, impossible de faire apparaître le robot. Tout est décrit dans le fichier, y compris le sol : les mondes d'exemple utilisent des modèles téléchargés depuis Internet (Gazebo Fuel), que le lab n'a pas.

## 4. Le pont ROS 2 ↔ Gazebo

`ros_gz_bridge` relie un topic Gazebo à un topic ROS 2 et convertit les messages (`gz.msgs.Twist` ↔ `geometry_msgs/msg/Twist`…). La liste va dans un fichier de configuration :

```yaml fichier=src/my_robot_description/config/pont.yaml
# Chaque ligne : un topic, son type côté ROS 2 et côté Gazebo, et le sens du passage
- ros_topic_name: /clock
  gz_topic_name: /clock
  ros_type_name: rosgraph_msgs/msg/Clock
  gz_type_name: gz.msgs.Clock
  direction: GZ_TO_ROS
- ros_topic_name: /cmd_vel
  gz_topic_name: /cmd_vel
  ros_type_name: geometry_msgs/msg/Twist
  gz_type_name: gz.msgs.Twist
  direction: ROS_TO_GZ
- ros_topic_name: /odom
  gz_topic_name: /odom
  ros_type_name: nav_msgs/msg/Odometry
  gz_type_name: gz.msgs.Odometry
  direction: GZ_TO_ROS
- ros_topic_name: /tf
  gz_topic_name: /tf
  ros_type_name: tf2_msgs/msg/TFMessage
  gz_type_name: gz.msgs.Pose_V
  direction: GZ_TO_ROS
- ros_topic_name: /joint_states
  gz_topic_name: /joint_states
  ros_type_name: sensor_msgs/msg/JointState
  gz_type_name: gz.msgs.Model
  direction: GZ_TO_ROS
- ros_topic_name: /scan
  gz_topic_name: /scan
  ros_type_name: sensor_msgs/msg/LaserScan
  gz_type_name: gz.msgs.LaserScan
  direction: GZ_TO_ROS
- ros_topic_name: /verite_terrain
  gz_topic_name: /verite_terrain
  ros_type_name: nav_msgs/msg/Odometry
  gz_type_name: gz.msgs.Odometry
  direction: GZ_TO_ROS
```

Un topic absent du pont existe dans Gazebo (`gz topic -l`) mais pas dans ROS 2 (`ros2 topic list`) : c'est la première chose à vérifier quand « rien n'arrive ».

## 5. Le fichier launch

```python fichier=src/my_robot_description/launch/gazebo.launch.py
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
    ])
```

Quatre étapes : démarrer le simulateur avec le monde (`ros_gz_sim`, `-s` sans fenêtre, `--headless-rendering` pour le laser), publier la description (`robot_state_publisher`), **faire apparaître** le robot (`create` lit `/robot_description` et l'ajoute au monde), puis ouvrir le pont.

`use_sim_time` : Gazebo publie sa propre horloge sur `/clock` (par le pont). Les nœuds qui travaillent avec la simulation doivent l'utiliser, sinon leurs horodatages ne correspondent pas à ceux des capteurs, et TF refuse les transformations.

Installez les dossiers `worlds` et `config` et déclarez les dépendances à `ros_gz_sim` et `ros_gz_bridge` :

```cmake fichier=src/my_robot_description/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(my_robot_description)

find_package(ament_cmake REQUIRED)

# Installe la description, les fichiers de lancement, les mondes et le pont dans share/my_robot_description
install(DIRECTORY urdf launch worlds config DESTINATION share/${PROJECT_NAME})

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
  <exec_depend>ros_gz_sim</exec_depend>
  <exec_depend>ros_gz_bridge</exec_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

## 6. Pratique

```bash
cd ~/ws/11-gazebo
colcon build --symlink-install
source install/setup.bash
ros2 launch my_robot_description gazebo.launch.py
```

Attendez le message `Entity creation successful`, puis, dans un second terminal :

```bash
gz topic -l                                       # les topics côté Gazebo
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

La fenêtre de Gazebo s'ouvre aussi sur le Bureau : `ros2 launch my_robot_description gazebo.launch.py gui:=true`. Sans carte graphique, elle est lente : fermez-la quand vous n'en avez pas besoin.

## 7. Rappel

- Gazebo **simule** (physique, capteurs), RViz **affiche** ce que ROS sait.
- Chaque link avec une masse : `<collision>` et `<inertial>` réalistes.
- Les balises `<gazebo>` portent frottements, systèmes (`DiffDrive`, `JointStatePublisher`…) et capteurs.
- Gazebo a ses propres topics : `ros_gz_bridge` les relie à ROS 2, topic par topic.
- Un monde SDF autonome, avec ses systèmes ; un launch qui démarre `gz sim`, `robot_state_publisher`, `create` et le pont ; `use_sim_time` pour les nœuds de la simulation.

**Et maintenant ?** Vous avez construit, pas à pas, le logiciel complet d'un robot mobile. Pour aller plus loin : la navigation autonome avec Nav2, qui s'appuie sur tout ce que vous venez d'apprendre.

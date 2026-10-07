---
titre: Modéliser un robot avec URDF
resume: Décrire le robot à conduite différentielle en URDF, le factoriser avec Xacro et publier sa description avec robot_state_publisher.
duree: 1 h 30
---
# Modéliser un robot avec URDF

> **La situation.** L'équipe veut voir le robot dans RViz, et bientôt le simuler. Pour cela, ROS doit connaître sa forme : un châssis, deux roues motrices, une roulette, où chaque pièce se trouve et comment elle bouge. Vous allez écrire sa description URDF.

**Dans ce module, vous allez :**

- décrire le robot en URDF : links, joints, géométries et matériaux ;
- factoriser la description avec Xacro (propriétés, macros) ;
- publier la description avec `robot_state_publisher` et la voir dans RViz.

## L'essentiel en théorie

RViz, Gazebo, la navigation ou un bras qui saisit un objet ont tous besoin de connaître la **forme** du robot : ses pièces, leurs dimensions, leur masse et la façon dont elles bougent les unes par rapport aux autres. Cette description s'écrit en **URDF** (*Unified Robot Description Format*), un fichier XML.

### Un arbre de links et de joints

Un robot est décrit comme un **arbre** :

- les **links** sont les corps rigides : châssis, roues, roulette ;
- les **joints** relient chaque link à son parent et disent comment il bouge par rapport à lui.

Chaque link a un seul parent, et la racine est en général `base_link`, le repère du robot. Dans notre robot de livraison, `base_link` porte le châssis et les deux roues motrices ; le châssis porte la roulette.

### Trois rôles pour chaque link

| Partie | Sert à | Utilisée par |
|---|---|---|
| `visual` | l'apparence : forme et couleur | RViz, Gazebo (affichage) |
| `collision` | la forme pour les contacts, souvent simplifiée | Gazebo (physique), planification |
| `inertial` | la masse et sa répartition | Gazebo (physique) |

Pour un simple affichage, `visual` suffit ; pour simuler, les trois sont nécessaires.

### Les types de joints

| Type | Mouvement | Exemple |
|---|---|---|
| `fixed` | aucun | le châssis sur `base_link`, un capteur vissé |
| `continuous` | rotation sans limite | une roue motrice |
| `revolute` | rotation entre deux butées | le coude d'un bras |
| `prismatic` | translation entre deux butées | un vérin, un ascenseur |

L'`origin` d'un joint place l'enfant par rapport au parent ; son `axis` donne l'axe du mouvement.

### Xacro : ne pas se répéter

Un URDF brut répète beaucoup : deux roues identiques, les mêmes dimensions à plusieurs endroits. **Xacro** ajoute au XML des **propriétés** (des constantes), des **expressions** (`${chassis_length/2}`) et des **macros** (un bloc paramétré, écrit une fois et utilisé deux fois). Le fichier `.xacro` est converti en URDF au lancement.

### De la description aux transformations

Le fichier ne fait rien seul. Le nœud `robot_state_publisher` le lit, le publie sur `/robot_description` et calcule la position de chaque link (les **TF**). Pour les joints mobiles, il a besoin de leur état courant, l'angle des roues par exemple, publié sur `/joint_states` : c'est le rôle de `joint_state_publisher` ou, plus tard, du simulateur et des vrais moteurs.

## 1. Structure générale d'un URDF

Syntaxe minimale :

```xml
<?xml version="1.0"?>
<robot name="my_robot">
  ...
</robot>
```

Deux composants principaux :

- `<link>` : un corps rigide du robot ;
- `<joint>` : la façon dont deux links sont reliés (rotation, translation, fixe…).

## 2. Les balises `<link>`

Chaque link peut contenir trois parties :

- **visual** : ce qu'on voit dans RViz ou Gazebo — `geometry` (box, cylinder, sphere, mesh), `origin` (décalage de la géométrie), `material` (couleur) ;
- **collision** : la géométrie utilisée pour la physique, souvent une copie simplifiée du visual ;
- **inertial** : les propriétés physiques — `mass`, `origin` (centre de masse) et `inertia` (matrice d'inertie, qui décrit la répartition des masses).

Exemple, le châssis du robot :

```xml
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
```

Les `${…}` et `xacro:inertial_box` viennent de Xacro (section 5) : ils remplacent des valeurs répétées.

## 3. Les balises `<joint>`

Un joint relie deux links.

- Attributs obligatoires : `name`, `type` (`fixed`, `revolute`, `continuous`, `prismatic`), `parent`, `child`, `origin` (position du child par rapport au parent, avant tout mouvement).
- Attributs optionnels, pour les joints mobiles : `axis` (axe de rotation ou de translation) et `limit` (bornes, vitesse, effort).

Exemple :

```xml
<joint name="chassis_joint" type="fixed">
  <parent link="base_link"/>
  <child link="chassis"/>
  <origin xyz="${-wheel_offset_x} 0 ${-wheel_offset_z}"/>
</joint>
```

Les roues tournent sans limite : leurs joints sont de type `continuous`, autour de leur axe `z`.

## 4. Pratique : construire le robot

Créez le package de description dans votre workspace `~/ws/05-urdf` :

```bash
cd ~/ws/05-urdf/src
ros2 pkg create --build-type ament_cmake my_robot_description
mkdir -p my_robot_description/urdf my_robot_description/launch
```

Déclarez les outils dont la description a besoin à l'exécution :

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

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

Et installez les dossiers `urdf` et `launch`, pour que `ros2 launch` les trouve :

```cmake fichier=src/my_robot_description/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(my_robot_description)

find_package(ament_cmake REQUIRED)

# Installe la description et les fichiers de lancement dans share/my_robot_description
install(DIRECTORY urdf launch DESTINATION share/${PROJECT_NAME})

ament_package()
```

## 5. Xacro

**Définition :** Xacro (*XML Macros*) simplifie les URDF longs et répétitifs.

**Activation :** l'espace de noms `xacro` est déclaré sur la balise `robot` :

```xml
<robot name="my_robot" xmlns:xacro="http://www.ros.org/wiki/xacro">
```

**Avantages :** factoriser le code (macros), paramétrer les dimensions et les masses (propriétés), découper la description en plusieurs fichiers (`xacro:include`).

Les matrices d'inertie se calculent avec des formules connues : on les range dans des macros, dans un fichier à part.

```xml fichier=src/my_robot_description/urdf/inertial_macros.xacro
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!-- Matrices d'inertie des formes simples (corps homogènes) -->
  <xacro:macro name="inertial_box" params="mass x y z *origin">
    <inertial>
      <xacro:insert_block name="origin"/>
      <mass value="${mass}"/>
      <inertia ixx="${mass * (y*y + z*z) / 12}" ixy="0" ixz="0"
               iyy="${mass * (x*x + z*z) / 12}" iyz="0"
               izz="${mass * (x*x + y*y) / 12}"/>
    </inertial>
  </xacro:macro>

  <xacro:macro name="inertial_cylinder" params="mass length radius *origin">
    <inertial>
      <xacro:insert_block name="origin"/>
      <mass value="${mass}"/>
      <inertia ixx="${mass * (3*radius*radius + length*length) / 12}" ixy="0" ixz="0"
               iyy="${mass * (3*radius*radius + length*length) / 12}" iyz="0"
               izz="${mass * radius*radius / 2}"/>
    </inertial>
  </xacro:macro>

  <xacro:macro name="inertial_sphere" params="mass radius *origin">
    <inertial>
      <xacro:insert_block name="origin"/>
      <mass value="${mass}"/>
      <inertia ixx="${2 * mass * radius*radius / 5}" ixy="0" ixz="0"
               iyy="${2 * mass * radius*radius / 5}" iyz="0"
               izz="${2 * mass * radius*radius / 5}"/>
    </inertial>
  </xacro:macro>

</robot>
```

La description du robot. Les deux roues sont identiques au signe près : une seule macro `wheel` les génère.

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

</robot>
```

**Usage :** `xacro` produit l'URDF final, et `check_urdf` vérifie sa syntaxe et affiche l'arbre des links :

```bash
cd ~/ws/05-urdf
xacro src/my_robot_description/urdf/my_robot.urdf.xacro > ~/my_robot.urdf
check_urdf ~/my_robot.urdf
```

## 6. Publier la description dans ROS 2

**Principe :**

- le fichier URDF ou Xacro contient la description du robot ;
- le nœud `robot_state_publisher` la publie sur le topic `/robot_description` ;
- il calcule aussi les **TF**, les transformations entre les links, à partir des joints ;
- les joints mobiles ont besoin de leur état (l'angle des roues) : c'est le rôle de `joint_state_publisher`.

On pourrait lancer `robot_state_publisher` en ligne de commande, mais en pratique on passe par un fichier de lancement, qui traite aussi le Xacro :

```python fichier=src/my_robot_description/launch/display.launch.py
import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_path = get_package_share_directory('my_robot_description')
    xacro_file = os.path.join(pkg_path, 'urdf', 'my_robot.urdf.xacro')
    robot_desc = xacro.process_file(xacro_file).toxml()

    return LaunchDescription([
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
    ])
```

Compilez et lancez :

```bash
cd ~/ws/05-urdf
colcon build --symlink-install
source install/setup.bash
ros2 launch my_robot_description display.launch.py
```

Dans un deuxième terminal, observez ce qui est publié :

```bash
ros2 topic echo --once /robot_description
ros2 run tf2_ros tf2_echo base_link caster_wheel
ros2 run tf2_tools view_frames
```

`tf2_echo` affiche la position de la roulette dans le repère `base_link`. `view_frames` enregistre l'arbre des repères dans `frames_*.pdf` : ouvrez-le depuis l'arborescence des fichiers.

## 7. Visualiser le robot dans RViz2

Le lab a un bureau graphique : cliquez sur **Bureau (RViz, Gazebo)** dans la barre du haut. Il prend la place de l'éditeur ; les terminaux restent dessous, et les fenêtres lancées depuis un terminal s'y affichent.

Dans un terminal, lancez la description du robot ; dans un second terminal, RViz2 :

```bash
ros2 launch my_robot_description display.launch.py
```

```bash
rviz2
```

Dans RViz2 :

- **Fixed Frame** (en haut à gauche) : `base_link` ;
- **Add** → **RobotModel**, puis *Description Topic* : `/robot_description` ;
- **Add** → **TF** pour voir les repères de chaque link.

Pour faire tourner les roues avec des **curseurs**, remplacez dans `display.launch.py` le nœud `joint_state_publisher` par `joint_state_publisher_gui` (même nom pour `package` et `executable`), recompilez et relancez : une fenêtre de curseurs s'ouvre sur le bureau.

Le rendu est logiciel (sans carte graphique) : un peu lent, mais suffisant pour une description de robot.

## 8. Rappel et ouverture

- URDF = description statique du robot ;
- Xacro = version paramétrée et factorisée ;
- pour aller plus loin : transmissions et `ros2_control`, intégration dans Gazebo (SDF/URDF), génération depuis la CAO (SolidWorks → URDF…).

**Et maintenant ?** Le robot a une forme. Avant de le simuler, rendons-le réglable sans recompiler : paramètres et fichiers launch, au module suivant.

---
titre: Décrire le bras en URDF
resume: Écrire la description Xacro du bras de tri (articulations, axes, limites, pince, tool0) et vérifier ses axes dans la Vue 3D et avec TF2.
duree: 1 h 30
---
# Décrire le bras en URDF

> **La situation.** L'intégrateur a livré le bras de tri avec ses cotes, mais sans description ROS. Sans elle, ni TF2, ni la Vue 3D, ni plus tard la planification ne savent où est la pince. Vous allez l'écrire, et apprendre à repérer l'erreur la plus fréquente : un axe d'articulation mal orienté.

**Dans ce module, vous allez :**

- écrire la description Xacro d'un bras : socle, tourelle, segments, pince et repère d'outil ;
- placer chaque articulation (`origin`), choisir son axe (`axis`) et ses butées (`limit`) ;
- factoriser les segments avec une macro, et faire suivre un doigt par l'autre avec `mimic` ;
- vérifier les axes dans la Vue 3D et la position de la pince avec TF2.

## L'essentiel en théorie

Au module URDF, le robot mobile avait deux joints mobiles, les roues. Un bras en a un par articulation, et ils sont **en série** : chaque joint est porté par le segment précédent. La description doit donc être juste à chaque étage, car une erreur sur le coude déplace l'avant-bras, le poignet et la pince.

### Le repère d'un joint

Chaque joint définit un repère, placé par son `origin` **dans le repère du link parent**, avant tout mouvement. Le link enfant est attaché à ce repère ; quand l'articulation bouge, le repère tourne (ou glisse) autour de l'`axis`, exprimé **dans ce même repère**.

Pour le bras de tri, on choisit des repères simples : tous alignés sur celui du socle quand les angles sont nuls, bras tendu vers le haut. Chaque `origin` n'est alors qu'une translation verticale, de la longueur du segment précédent :

| Joint | Parent → enfant | `origin` | `axis` | Butées (rad) |
|---|---|---|---|---|
| `base_rotation` | `base_link` → `tourelle` | z = 0,05 | `0 0 1` (verticale) | ±π |
| `epaule` | `tourelle` → `bras` | z = 0,05 | `0 1 0` | ±1,6 |
| `coude` | `bras` → `avant_bras` | z = 0,30 | `0 1 0` | ±2,2 |
| `poignet` | `avant_bras` → `main` | z = 0,25 | `0 1 0` | ±1,8 |
| `outil` (fixe) | `main` → `tool0` | z = 0,10 | | |

L'épaule, le coude et le poignet tournent tous trois autour de `y` : leurs axes sont **parallèles**, et le bras se plie dans un seul plan vertical, celui que la tourelle oriente. Un angle positif autour de `y` fait passer `z` vers `x` : le bras penche vers l'avant.

### Les butées en radians

`<limit lower upper effort velocity>` est obligatoire pour un joint `revolute` ou `prismatic`. Les angles sont en **radians** et les translations en mètres : un `upper="90"` voulu en degrés donne en fait 14 tours.

### La pince et `mimic`

Les deux doigts s'écartent ensemble, commandés par un seul moteur. On décrit deux joints prismatiques d'axes opposés ; le second porte `<mimic joint="pince"/>` : sa valeur est celle de `pince` (multipliée par `multiplier`, décalée de `offset`, s'ils sont donnés). `robot_state_publisher` et la Vue 3D calculent sa position eux-mêmes ; seul `pince` est publié dans `/joint_states`.

### Le repère de l'outil

`tool0` est un link vide, attaché à la main par un joint `fixed`, au point de prise entre les doigts. C'est la convention ROS-Industrial : le logiciel parle de la position de `tool0`, sans se soucier de l'outil monté.

## 1. Le package

Le workspace du module, `~/ws/31-bras-urdf`, contient le package `bras_description` : `package.xml`, `CMakeLists.txt` et `launch/display.launch.py` sont prêts (ceux du module précédent). Il ne manque que la description, `urdf/bras.urdf.xacro`.

Le fichier de lancement mérite un regard : au lieu de lire le Xacro en Python, il demande à `launch` d'exécuter `xacro` et de passer le résultat en paramètre. Son argument `jsp` choisit qui publie l'état des joints :

```text
ros2 launch bras_description display.launch.py            # joint_state_publisher, tous les angles à 0
ros2 launch bras_description display.launch.py jsp:=false # un autre nœud publie /joint_states
```

## 2. Écrire la description, étage par étage

**Les propriétés.** Les cotes de l'intégrateur, une seule fois, en tête de fichier :

```xml
<xacro:property name="h_epaule" value="0.10"/>
<xacro:property name="l_bras" value="0.30"/>
<xacro:property name="l_avant_bras" value="0.25"/>
<xacro:property name="l_poignet" value="0.10"/>
```

**Le socle et la tourelle.** `base_link` est le socle, fixé à la table ; la tourelle pivote au-dessus, autour de la verticale :

```xml
<joint name="base_rotation" type="revolute">
  <parent link="base_link"/>
  <child link="tourelle"/>
  <origin xyz="0 0 0.05"/>
  <axis xyz="0 0 1"/>
  <limit lower="${-pi}" upper="${pi}" effort="10" velocity="1.5"/>
</joint>
```

**Les segments.** Épaule, coude et poignet ont la même forme : une articulation autour de `y`, puis une barre dans le prolongement. Une macro les écrit une fois :

```xml
<xacro:macro name="segment" params="articulation parent enfant z l largeur lower upper">
  <joint name="${articulation}" type="revolute">
    <parent link="${parent}"/>
    <child link="${enfant}"/>
    <origin xyz="0 0 ${z}"/>
    <axis xyz="0 1 0"/>
    <limit lower="${lower}" upper="${upper}" effort="10" velocity="1.5"/>
  </joint>
  <link name="${enfant}">
    <visual>
      <origin xyz="0 0 ${l/2}"/>
      <geometry><box size="${largeur} ${largeur} ${l}"/></geometry>
      <material name="orange"/>
    </visual>
  </link>
</xacro:macro>
```

La barre est une boîte de longueur `l`, décalée de `l/2` : elle part de l'articulation au lieu d'être centrée dessus. Chaque segment est placé à `z` du précédent, la longueur de celui-ci :

```xml
<xacro:segment articulation="epaule" parent="tourelle" enfant="bras" z="${h_epaule - 0.05}"
               l="${l_bras}" largeur="0.04" lower="-1.6" upper="1.6"/>
<xacro:segment articulation="coude" parent="bras" enfant="avant_bras" z="${l_bras}"
               l="${l_avant_bras}" largeur="0.035" lower="-2.2" upper="2.2"/>
```

**La pince et l'outil** : deux doigts, le second imitant le premier, puis `tool0`.

Voici le fichier complet. Ouvrez-le dans le lab, relisez-le étage par étage :

```xml fichier=src/bras_description/urdf/bras.urdf.xacro
<?xml version="1.0"?>
<!-- Le bras de tri : un socle, une tourelle qui pivote, trois articulations dans un même plan
     (épaule, coude, poignet) et une pince à deux doigts. Bras tendu vers le haut quand tous
     les angles valent 0 ; un angle positif penche le bras vers l'avant (+x de la tourelle). -->
<robot name="bras" xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!-- Dimensions (m) : hauteur de l'épaule, bras, avant-bras, poignet jusqu'au centre de la pince -->
  <xacro:property name="h_epaule" value="0.10"/>
  <xacro:property name="l_bras" value="0.30"/>
  <xacro:property name="l_avant_bras" value="0.25"/>
  <xacro:property name="l_poignet" value="0.10"/>

  <material name="gris"><color rgba="0.35 0.38 0.42 1"/></material>
  <material name="orange"><color rgba="1.0 0.5 0.1 1"/></material>
  <material name="noir"><color rgba="0.1 0.1 0.1 1"/></material>

  <!-- Le socle, fixé à la table : le repère de référence du bras -->
  <link name="base_link">
    <visual>
      <origin xyz="0 0 0.025"/>
      <geometry><cylinder radius="0.08" length="0.05"/></geometry>
      <material name="gris"/>
    </visual>
  </link>

  <!-- La tourelle tourne autour de la verticale -->
  <joint name="base_rotation" type="revolute">
    <parent link="base_link"/>
    <child link="tourelle"/>
    <origin xyz="0 0 0.05"/>
    <axis xyz="0 0 1"/>
    <limit lower="${-pi}" upper="${pi}" effort="10" velocity="1.5"/>
  </joint>

  <link name="tourelle">
    <visual>
      <origin xyz="0 0 0.025"/>
      <geometry><cylinder radius="0.05" length="0.05"/></geometry>
      <material name="orange"/>
    </visual>
  </link>

  <!-- Un segment du bras : une articulation autour de y (tangage), puis une barre de longueur l -->
  <xacro:macro name="segment" params="articulation parent enfant z l largeur lower upper">
    <joint name="${articulation}" type="revolute">
      <parent link="${parent}"/>
      <child link="${enfant}"/>
      <origin xyz="0 0 ${z}"/>
      <axis xyz="0 1 0"/>
      <limit lower="${lower}" upper="${upper}" effort="10" velocity="1.5"/>
    </joint>
    <link name="${enfant}">
      <visual>
        <origin xyz="0 0 ${l/2}"/>
        <geometry><box size="${largeur} ${largeur} ${l}"/></geometry>
        <material name="orange"/>
      </visual>
    </link>
  </xacro:macro>

  <xacro:segment articulation="epaule" parent="tourelle" enfant="bras" z="${h_epaule - 0.05}"
                 l="${l_bras}" largeur="0.04" lower="-1.6" upper="1.6"/>
  <xacro:segment articulation="coude" parent="bras" enfant="avant_bras" z="${l_bras}"
                 l="${l_avant_bras}" largeur="0.035" lower="-2.2" upper="2.2"/>
  <xacro:segment articulation="poignet" parent="avant_bras" enfant="main" z="${l_avant_bras}"
                 l="0.04" largeur="0.06" lower="-1.8" upper="1.8"/>

  <!-- La pince : deux doigts qui s'écartent ensemble (le second imite le premier) -->
  <xacro:macro name="doigt" params="nom cote">
    <link name="doigt_${nom}">
      <visual>
        <origin xyz="0 ${cote * 0.005} 0.03"/>
        <geometry><box size="0.02 0.01 0.06"/></geometry>
        <material name="noir"/>
      </visual>
    </link>
  </xacro:macro>
  <xacro:doigt nom="gauche" cote="1"/>
  <xacro:doigt nom="droit" cote="-1"/>

  <joint name="pince" type="prismatic">
    <parent link="main"/>
    <child link="doigt_gauche"/>
    <origin xyz="0 0.005 0.04"/>
    <axis xyz="0 1 0"/>
    <limit lower="0" upper="0.03" effort="5" velocity="0.1"/>
  </joint>
  <joint name="pince_miroir" type="prismatic">
    <parent link="main"/>
    <child link="doigt_droit"/>
    <origin xyz="0 -0.005 0.04"/>
    <axis xyz="0 -1 0"/>
    <limit lower="0" upper="0.03" effort="5" velocity="0.1"/>
    <mimic joint="pince"/>
  </joint>

  <!-- tool0 : le point de prise, entre les doigts, à l_poignet du poignet -->
  <joint name="outil" type="fixed">
    <parent link="main"/>
    <child link="tool0"/>
    <origin xyz="0 0 ${l_poignet}"/>
  </joint>
  <link name="tool0"/>

</robot>
```

## 3. Vérifier la description

Compilez, convertissez le Xacro et vérifiez l'arbre :

```bash
cd ~/ws/31-bras-urdf
colcon build --symlink-install
source install/setup.bash
xacro src/bras_description/urdf/bras.urdf.xacro > ~/bras.urdf
check_urdf ~/bras.urdf
```

`check_urdf` affiche l'arbre : `base_link` → `tourelle` → `bras` → `avant_bras` → `main`, qui porte les deux doigts et `tool0`. Il vérifie la **structure** (un seul parent par link, une seule racine), pas la **géométrie** : un axe faux passe sans erreur. Pour cela, il faut regarder.

## 4. Regarder les axes

Lancez la description et ouvrez la **Vue 3D** :

```bash
ros2 launch bras_description display.launch.py
```

Pour chaque articulation, déplacez son curseur et vérifiez :

- `base_rotation` fait tourner tout le bras autour de la verticale ;
- `epaule`, `coude` et `poignet` plient le bras **dans le même plan**, celui qui contient l'axe `x` de la tourelle (rouge) ;
- la pince s'ouvre symétriquement.

Les trièdres aident : l'axe de rotation d'une articulation est l'axe de son repère que le mouvement laisse immobile. Pour le coude, c'est le `y` (vert) du repère `avant_bras`.

## 5. Vérifier une pose avec TF2

L'œil ne voit pas un décalage de 2 cm ; TF2, si. Relancez sans `joint_state_publisher` et publiez une pose précise :

```bash
ros2 launch bras_description display.launch.py jsp:=false
```

```bash
ros2 topic pub -r 10 /joint_states sensor_msgs/msg/JointState \
  "{name: [base_rotation, epaule, coude, poignet, pince], position: [0.0, 0.5, 0.8, -0.4, 0.0]}"
```

```bash
ros2 run tf2_ros tf2_echo base_link tool0
```

La tourelle à 0, tout le bras est dans le plan `x z` : `y` doit valoir 0. Et `x`, `z` se calculent à la main, segment par segment ; c'est l'objet du module suivant. Ici, `tf2_echo` affiche environ `[0.463, 0.000, 0.492]`.

## 6. Rappel

- L'`origin` d'un joint place son repère dans celui du parent ; l'`axis` est exprimé dans ce repère ;
- choisir des repères alignés quand les angles sont nuls rend chaque `origin` simple ;
- les butées sont en radians ; `mimic` fait suivre un joint par un autre ;
- `check_urdf` vérifie l'arbre, pas la géométrie : regardez chaque axe dans la Vue 3D, et vérifiez une pose connue avec TF2.

**Et maintenant ?** L'exercice part d'une description où une articulation est mal orientée. Ensuite, le module 32 calcule la position de la pince sans TF2 : la cinématique directe.

---
titre: Écrire un nœud
resume: Le fil rouge commence — un robot à conduite différentielle qui reçoit des commandes de vitesse et publie sa position.
duree: 1 h 15
---
# Écrire un nœud

> **La situation.** Le robot de livraison a deux moteurs, mais aucun logiciel pour les piloter. Votre première mission : écrire le programme qui reçoit les ordres de vitesse de l'équipe et calcule en permanence où se trouve le robot. Ce nœud, `diff_drive_node`, sera le cœur du robot pendant tout le parcours.

**Dans ce module, vous allez :**

- écrire un nœud qui s'abonne à un topic et en publie un autre ;
- comprendre le cycle de vie d'un nœud : initialisation, `spin`, arrêt ;
- simuler le déplacement d'un robot à conduite différentielle ;
- compiler le même nœud en Python et en C++.

Ce nœud, `diff_drive_node`, est le fil rouge du parcours : les modules Service et Action l'enrichiront.

## 1. Le robot à conduite différentielle

Un robot à conduite différentielle a deux roues motrices indépendantes. On le commande avec deux vitesses :

- une vitesse **linéaire** `v` (m/s), vers l'avant ;
- une vitesse **angulaire** `w` (rad/s), autour de l'axe vertical.

Sa position dans le plan est `(x, y, θ)`. Pendant un court instant `dt`, elle évolue ainsi :

```text
θ ← θ + w·dt
x ← x + v·cos(θ)·dt
y ← y + v·sin(θ)·dt
```

En ROS 2, les commandes de vitesse circulent sur le topic `/cmd_vel` (type `geometry_msgs/msg/Twist`) et la position estimée sur `/odom` (type `nav_msgs/msg/Odometry`). Ce sont les noms utilisés par la plupart des robots mobiles.

## 2. Le workspace et le package

Votre workspace de travail est `~/ws/02-noeud`. Il contient déjà deux packages, créés pour vous avec les commandes du module Initiation :

```bash
cd ~/ws/02-noeud/src
ros2 pkg create my_pkg --build-type ament_python --dependencies rclpy geometry_msgs nav_msgs
ros2 pkg create my_pkg_cpp --build-type ament_cmake --dependencies rclcpp geometry_msgs nav_msgs
```

Ouvrez `src/my_pkg/package.xml` dans l'éditeur : les dépendances `rclpy`, `geometry_msgs` et `nav_msgs` y sont déclarées. Un nœud ne peut utiliser que ce que son package déclare.

## 3. Le nœud `diff_drive_node`

Un nœud est une classe qui hérite de `Node`. Dans son constructeur, on déclare ce qu'il fait :

- `create_subscription` : s'abonner à `cmd_vel` et appeler `cmd_vel_callback` à chaque message ;
- `create_publisher` : pouvoir publier sur `odom` ;
- `create_timer` : appeler `update` toutes les 50 ms, pour faire avancer le robot et publier sa position.

Cliquez sur « Ouvrir dans le lab » : le fichier est créé dans votre workspace s'il n'existe pas encore.

```python fichier=src/my_pkg/my_pkg/diff_drive_node.py
import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node


class DiffDriveNode(Node):
    """Robot à conduite différentielle simulé : /cmd_vel → position → /odom."""

    def __init__(self):
        super().__init__('diff_drive_node')
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.v = 0.0
        self.w = 0.0
        self.dt = 0.05  # période de mise à jour (s)

        self.cmd_sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.timer = self.create_timer(self.dt, self.update)
        self.get_logger().info('diff_drive_node prêt : commandes sur /cmd_vel, position sur /odom')

    def cmd_vel_callback(self, msg):
        """Mémorise la dernière commande de vitesse reçue."""
        self.v = msg.linear.x
        self.w = msg.angular.z

    def move_robot(self, v, w, dt):
        """Fait avancer le robot de dt secondes à la vitesse (v, w)."""
        self.theta = math.atan2(math.sin(self.theta + w * dt), math.cos(self.theta + w * dt))
        self.x += v * math.cos(self.theta) * dt
        self.y += v * math.sin(self.theta) * dt

    def update(self):
        self.move_robot(self.v, self.w, self.dt)
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = math.sin(self.theta / 2)
        odom.pose.pose.orientation.w = math.cos(self.theta / 2)
        odom.twist.twist.linear.x = self.v
        odom.twist.twist.angular.z = self.w
        self.odom_pub.publish(odom)


def main(args=None):
    rclpy.init(args=args)
    node = DiffDriveNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
```

```cpp fichier=src/my_pkg_cpp/src/diff_drive_node.cpp
#include <chrono>
#include <cmath>
#include <memory>

#include "geometry_msgs/msg/twist.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace std::chrono_literals;

// Robot à conduite différentielle simulé : /cmd_vel → position → /odom.
class DiffDriveNode : public rclcpp::Node
{
public:
  DiffDriveNode()
  : Node("diff_drive_node")
  {
    cmd_sub_ = create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel", 10,
      [this](const geometry_msgs::msg::Twist & msg) {
        v_ = msg.linear.x;
        w_ = msg.angular.z;
      });
    odom_pub_ = create_publisher<nav_msgs::msg::Odometry>("odom", 10);
    timer_ = create_wall_timer(50ms, [this]() {update();});
    RCLCPP_INFO(get_logger(), "diff_drive_node prêt : commandes sur /cmd_vel, position sur /odom");
  }

private:
  void move_robot(double v, double w, double dt)
  {
    theta_ = std::atan2(std::sin(theta_ + w * dt), std::cos(theta_ + w * dt));
    x_ += v * std::cos(theta_) * dt;
    y_ += v * std::sin(theta_) * dt;
  }

  void update()
  {
    move_robot(v_, w_, dt_);
    nav_msgs::msg::Odometry odom;
    odom.header.stamp = now();
    odom.header.frame_id = "odom";
    odom.child_frame_id = "base_link";
    odom.pose.pose.position.x = x_;
    odom.pose.pose.position.y = y_;
    odom.pose.pose.orientation.z = std::sin(theta_ / 2);
    odom.pose.pose.orientation.w = std::cos(theta_ / 2);
    odom.twist.twist.linear.x = v_;
    odom.twist.twist.angular.z = w_;
    odom_pub_->publish(odom);
  }

  double x_ = 0.0, y_ = 0.0, theta_ = 0.0;
  double v_ = 0.0, w_ = 0.0;
  const double dt_ = 0.05;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<DiffDriveNode>());
  rclcpp::shutdown();
  return 0;
}
```

**Ce qu'il faut retenir :**

- le nom donné à `super().__init__('diff_drive_node')` est le nom du nœud, celui qu'affiche `ros2 node list` ;
- les noms de topics `cmd_vel` et `odom` sont **relatifs** : sans espace de noms, ils deviennent `/cmd_vel` et `/odom` ;
- le `10` est la taille de la file d'attente (QoS *history depth*) ;
- `rclpy.spin(node)` rend la main à ROS 2, qui appelle les callbacks quand un message arrive ou qu'un timer expire. Sans `spin`, aucun callback n'est jamais appelé.

## 4. Déclarer l'exécutable

`ros2 run` ne trouve un nœud que s'il est déclaré comme exécutable du package.

En Python, c'est le rôle de `entry_points` dans `setup.py` : la ligne `diff_drive_node = my_pkg.diff_drive_node:main` crée l'exécutable `diff_drive_node`, qui appelle la fonction `main`.

```python fichier=src/my_pkg/setup.py
from setuptools import find_packages, setup

package_name = 'my_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='etudiant',
    maintainer_email='etudiant@ros-academy.local',
    description='Robot à conduite différentielle du parcours ROS 2 Fondamentaux',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'diff_drive_node = my_pkg.diff_drive_node:main',
        ],
    },
)
```

En C++, `add_executable` compile le programme et `install` le place là où `ros2 run` le cherche :

```cmake fichier=src/my_pkg_cpp/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(my_pkg_cpp)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)

add_executable(diff_drive_node src/diff_drive_node.cpp)
ament_target_dependencies(diff_drive_node rclcpp geometry_msgs nav_msgs)

install(TARGETS diff_drive_node DESTINATION lib/${PROJECT_NAME})

ament_package()
```

## 5. Compiler et lancer

Depuis la racine du workspace :

```bash
cd ~/ws/02-noeud
colcon build --symlink-install
source install/setup.bash
ros2 run my_pkg diff_drive_node
```

La version C++ se lance de la même façon avec `ros2 run my_pkg_cpp diff_drive_node`. Les deux nœuds portent le même nom : n'en lancez qu'un à la fois.

## 6. Faire bouger le robot

Ouvrez un deuxième terminal (bouton **+** au-dessus des terminaux). Inspectez d'abord le nœud :

```bash
ros2 node list
ros2 node info /diff_drive_node
ros2 topic info /cmd_vel
```

Puis envoyez une commande de vitesse, 10 fois par seconde :

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.5}}"
```

Le robot décrit un cercle dans la **vue 2D**, à droite. Vous pouvez aussi le piloter avec les flèches de la vue 2D, qui publient sur `/cmd_vel`.

Dans un troisième terminal, observez ce que publie le nœud :

```bash
ros2 topic echo /odom --field pose.pose.position
ros2 topic hz /odom
```

`ros2 topic hz` doit afficher environ 20 Hz : c'est la période de 50 ms du timer.

## 7. Pour aller plus loin

- Arrêter le robot quand aucune commande n'est reçue depuis 0,5 s (sécurité indispensable sur un vrai robot).
- Ajouter un paramètre `rate` (`declare_parameter`) pour régler la fréquence de mise à jour.
- Publier aussi la transformation `odom → base_link` avec un `TransformBroadcaster`.

**Et maintenant ?** Le robot roule et publie sa position. Dans le module suivant, l'entrepôt veut pouvoir la lui demander à tout moment : vous lui ajouterez un service.

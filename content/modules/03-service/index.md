---
titre: Créer un service
resume: Ajouter au robot un service get_pose qui renvoie sa position à la demande, avec une interface .srv personnalisée.
duree: 1 h 15
---
# Créer un service

## 1. Introduction aux services

**Concept :** un service est une communication **synchrone** : un client envoie une requête et attend une réponse unique.

Dans un nœud serveur, on déclare le type du service, son nom et une fonction de rappel qui construit la réponse.

**Utilité :** récupérer un état, exécuter une action ponctuelle ou retourner un résultat qui n'a pas de sens en continu. Une position publiée en continu sur `/odom` convient à un affichage ; un programme qui a besoin de la position *à un instant précis* l'obtient plus simplement par un service.

Dans ce module, on écrit un service `get_pose` qui renvoie la pose actuelle `(x, y, θ)` du robot. Tutoriel officiel : [Writing a simple service and client (Python)](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Py-Service-And-Client.html).

## 2. Préparation

Votre workspace `~/ws/03-service` reprend le package `my_pkg` et le nœud `diff_drive_node` du module précédent. On crée un nouveau package dédié aux interfaces :

```bash
cd ~/ws/03-service/src
ros2 pkg create my_interface --build-type ament_cmake
```

Les interfaces (`.msg`, `.srv`, `.action`) sont générées par du code C++ et Python : leur package est toujours de type `ament_cmake`, même si vos nœuds sont en Python. Les regrouper dans un package à part permet à tous les autres packages de les utiliser.

### Dépendances

Dans `my_interface/package.xml`, ajoutez les dépendances nécessaires à la génération, ainsi que la ligne `member_of_group`, obligatoire pour un package qui fournit des interfaces :

```xml fichier=src/my_interface/package.xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>my_interface</name>
  <version>0.1.0</version>
  <description>Interfaces du robot du parcours ROS 2 Fondamentaux</description>
  <maintainer email="etudiant@ros-academy.local">etudiant</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  <build_depend>rosidl_default_generators</build_depend>
  <exec_depend>rosidl_default_runtime</exec_depend>
  <member_of_group>rosidl_interface_packages</member_of_group>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

### Définir le service

Créez un dossier `srv` dans `my_interface`, puis le fichier `GetPose.srv` :

```bash
mkdir -p ~/ws/03-service/src/my_interface/srv
```

```srv fichier=src/my_interface/srv/GetPose.srv
# Requête vide
---
float64 x
float64 y
float64 theta
```

La ligne `---` sépare la partie **requête** (ici aucune donnée) de la partie **réponse** (`x`, `y`, `θ`).

### Générer le code

Modifiez `CMakeLists.txt` pour générer le service :

```cmake fichier=src/my_interface/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(my_interface)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/GetPose.srv"
)

ament_package()
```

### Compilation

On compile d'abord le nouveau package, puis l'ensemble :

```bash
cd ~/ws/03-service
colcon build --packages-select my_interface
source install/setup.bash
ros2 interface show my_interface/srv/GetPose
```

`ros2 interface show` affiche la définition générée : c'est la preuve que le service est connu de ROS 2.

## 3. Le serveur `get_pose`

On reprend le nœud `diff_drive_node`. Le package `my_pkg` utilise maintenant `my_interface` : déclarez-le dans son `package.xml`.

```xml fichier=src/my_pkg/package.xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>my_pkg</name>
  <version>0.1.0</version>
  <description>Robot à conduite différentielle du parcours ROS 2 Fondamentaux</description>
  <maintainer email="etudiant@ros-academy.local">etudiant</maintainer>
  <license>Apache-2.0</license>

  <depend>rclpy</depend>
  <depend>geometry_msgs</depend>
  <depend>nav_msgs</depend>
  <depend>my_interface</depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

Puis ajoutez le serveur de service au nœud :

```python fichier=src/my_pkg/my_pkg/diff_drive_node.py
import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node

from my_interface.srv import GetPose


class DiffDriveNode(Node):
    """Robot à conduite différentielle simulé : /cmd_vel → position → /odom, service get_pose."""

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
        # Serveur du service get_pose
        self.srv = self.create_service(GetPose, 'get_pose', self.get_pose_callback)
        self.get_logger().info('diff_drive_node prêt : commandes sur /cmd_vel, position sur /odom')

    def cmd_vel_callback(self, msg):
        """Mémorise la dernière commande de vitesse reçue."""
        self.v = msg.linear.x
        self.w = msg.angular.z

    def get_pose_callback(self, request, response):
        """Fonction de rappel du service get_pose : renvoie la pose actuelle."""
        response.x = self.x
        response.y = self.y
        response.theta = self.theta
        self.get_logger().info(f'Service get_pose appelé : ({self.x:.2f}, {self.y:.2f}, {self.theta:.2f})')
        return response

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
#include "my_interface/srv/get_pose.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"

using namespace std::chrono_literals;

// Robot à conduite différentielle simulé : /cmd_vel → position → /odom, service get_pose.
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
    // Serveur du service get_pose
    srv_ = create_service<my_interface::srv::GetPose>(
      "get_pose",
      [this](const std::shared_ptr<my_interface::srv::GetPose::Request>,
      std::shared_ptr<my_interface::srv::GetPose::Response> response) {
        response->x = x_;
        response->y = y_;
        response->theta = theta_;
        RCLCPP_INFO(get_logger(), "Service get_pose appelé : (%.2f, %.2f, %.2f)", x_, y_, theta_);
      });
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
  rclcpp::Service<my_interface::srv::GetPose>::SharedPtr srv_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<DiffDriveNode>());
  rclcpp::shutdown();
  return 0;
}
```

**Explications :**

- `create_service` enregistre le service `get_pose`, de type `GetPose`, et lui associe la fonction de rappel qui construit la réponse ;
- la fonction de rappel reçoit la requête (vide ici) et un objet réponse à remplir ; ROS 2 envoie la réponse au client dès que la fonction se termine ;
- comme les abonnements et les timers, le service n'est servi que pendant `spin()`.

Pour la version C++, `my_interface` doit aussi être déclaré dans `package.xml` et `CMakeLists.txt` :

```xml fichier=src/my_pkg_cpp/package.xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>my_pkg_cpp</name>
  <version>0.1.0</version>
  <description>Robot à conduite différentielle, version C++</description>
  <maintainer email="etudiant@ros-academy.local">etudiant</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  <depend>rclcpp</depend>
  <depend>geometry_msgs</depend>
  <depend>nav_msgs</depend>
  <depend>my_interface</depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

```cmake fichier=src/my_pkg_cpp/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(my_pkg_cpp)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(my_interface REQUIRED)

add_executable(diff_drive_node src/diff_drive_node.cpp)
ament_target_dependencies(diff_drive_node rclcpp geometry_msgs nav_msgs my_interface)

install(TARGETS diff_drive_node DESTINATION lib/${PROJECT_NAME})

ament_package()
```

Compilez et lancez :

```bash
cd ~/ws/03-service
colcon build --symlink-install
source install/setup.bash
ros2 run my_pkg diff_drive_node
```

## 4. Le client, en ligne de commande

Dans un deuxième terminal :

```bash
source ~/ws/03-service/install/setup.bash
ros2 service list -t
ros2 service call /get_pose my_interface/srv/GetPose
```

Une requête (vide) est envoyée au serveur, et la réponse s'affiche : `x`, `y` et `theta`. Faites bouger le robot avec la vue 2D puis rappelez le service : la pose a changé.

`ros2 service call` attend que le service existe avant d'envoyer la requête (*waiting for service to become available…*). Si ce message ne disparaît pas, le service n'existe pas sous ce nom : vérifiez avec `ros2 service list`.

## 5. Amélioration et pratique

- Écrire un service qui renvoie la distance parcourue par le robot.
- Écrire un nœud client (`create_client`, `call_async`) qui interroge `get_pose` une fois par seconde et affiche la réponse.

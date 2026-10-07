---
titre: Créer une action
resume: Envoyer le robot vers un point avec une action goto — goal, feedback pendant le trajet, résultat et annulation.
duree: 1 h 30
---
# Créer une action

> **La situation.** Une commande arrive : livrer un colis au point (2, 1) de l'entrepôt. Le trajet prend plusieurs secondes ; l'opérateur veut suivre la distance restante et pouvoir annuler si le colis est retiré. Ni un topic ni un service ne suffisent : il faut une action `goto`.

**Dans ce module, vous allez :**

- définir une interface d'action (fichier `.action`) : goal, feedback et résultat ;
- écrire le serveur d'action qui conduit le robot jusqu'au point demandé ;
- suivre les feedbacks, recevoir le résultat et annuler un goal en cours.

## L'essentiel en théorie

Une **action** sert à confier une **tâche longue** à un autre nœud, en gardant la main : on suit son avancement et on peut l'interrompre. Envoyer le robot vers un point est le cas typique : le trajet prend plusieurs secondes.

### Goal, feedback, résultat

Une action réunit trois messages :

- le **goal** (l'objectif), envoyé par le client : « va au point (2, 1) » ;
- des **feedbacks**, publiés par le serveur pendant l'exécution : « je suis en (1.2, 0.6) » ;
- le **résultat**, envoyé une seule fois à la fin : « arrivé, position finale (2.0, 1.0) ».

Le client peut à tout moment demander l'**annulation** du goal : l'action est *préemptable*. Le fichier `.action` décrit ces trois parties, séparées par `---`, dans le même package d'interfaces que les services.

### Le cycle de vie d'un goal

1. Le serveur **accepte** ou **refuse** le goal (une cible hors de l'entrepôt, par exemple).
2. Une fois accepté, le goal est **en cours d'exécution** : le serveur publie des feedbacks.
3. Il se termine dans l'un de trois états : **réussi** (*succeeded*), **annulé** à la demande du client (*canceled*) ou **abandonné** par le serveur, qui ne peut pas aller au bout (*aborted*).

Un serveur peut gérer plusieurs goals ; c'est lui qui décide d'en accepter un nouveau pendant qu'un autre s'exécute.

### Ce qu'il y a sous le capot

Une action n'est pas un nouveau mécanisme : ROS 2 la construit avec ce que vous connaissez déjà.

- Trois **services** : envoyer un goal, demander le résultat, annuler.
- Deux **topics** : les feedbacks et l'état des goals.

C'est pourquoi on la manipule avec les mêmes réflexes : `ros2 action list`, `ros2 action info`, et `ros2 interface show` pour lire sa structure.

### Une exécution qui ne bloque pas le nœud

L'exécution d'un goal dure plusieurs secondes, alors que l'exécuteur appelle par défaut les callbacks un par un. Pendant ce temps, le nœud doit continuer à recevoir `/cmd_vel`, publier `/odom` et accepter une demande d'annulation. On lance donc le nœud avec un exécuteur **multi-thread** (`MultiThreadedExecutor`) et l'on place le serveur d'action dans un **groupe de callbacks réentrant** : plusieurs callbacks peuvent alors s'exécuter en même temps.

### Topic, service ou action ?

- Les **topics** diffusent des messages en continu, sans accusé de réception.
- Les **services** offrent une interaction de type requête-réponse unique.
- Les **actions** lancent une tâche longue, avec suivi, résultat et annulation.

## 1. Définir l'action `/goto`

Votre workspace `~/ws/04-action` contient l'état final du module Service : `my_interface` (avec `GetPose`) et `diff_drive_node` (avec `get_pose`).

Ajoutez le fichier `action/Goto.action` dans le package `my_interface`. Il comporte trois parties, séparées par `---` :

```bash
mkdir -p ~/ws/04-action/src/my_interface/action
```

```action fichier=src/my_interface/action/Goto.action
# Goal
geometry_msgs/Pose2D target
---
# Result
bool reached
geometry_msgs/Pose2D final_pose
---
# Feedback
geometry_msgs/Pose2D current_pose
```

L'action utilise le type `geometry_msgs/Pose2D` (x, y, θ) : déclarez la dépendance dans `CMakeLists.txt`…

```cmake fichier=src/my_interface/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(my_interface)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/GetPose.srv"
  "action/Goto.action"
  DEPENDENCIES geometry_msgs
)

ament_package()
```

… et dans `package.xml` :

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
  <depend>geometry_msgs</depend>
  <build_depend>rosidl_default_generators</build_depend>
  <exec_depend>rosidl_default_runtime</exec_depend>
  <member_of_group>rosidl_interface_packages</member_of_group>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

Recompilez l'interface et vérifiez qu'elle est connue :

```bash
cd ~/ws/04-action
colcon build --packages-select my_interface
source install/setup.bash
ros2 interface list | grep Goto
ros2 interface show my_interface/action/Goto
```

## 2. Implémenter le serveur d'action `goto`

On modifie `diff_drive_node` dans le package `my_pkg` :

```python fichier=src/my_pkg/my_pkg/diff_drive_node.py
import math
import time

import rclpy
from geometry_msgs.msg import Pose2D, Twist
from nav_msgs.msg import Odometry
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from my_interface.action import Goto
from my_interface.srv import GetPose


class DiffDriveNode(Node):
    """Robot à conduite différentielle simulé : /cmd_vel → position → /odom, service get_pose, action goto."""

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
        # Serveur de l'action goto, dans son propre groupe de callbacks : pendant qu'un
        # goal s'exécute, le timer continue de déplacer le robot et de publier /odom.
        self._action_server = ActionServer(
            self,
            Goto,
            'goto',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup(),
        )
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

    def goal_callback(self, goal_request):
        """Accepter ou rejeter une nouvelle demande de goal."""
        self.get_logger().info(f'Goal reçu : ({goal_request.target.x:.2f}, {goal_request.target.y:.2f})')
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        self.get_logger().info('Demande d\'annulation reçue')
        return CancelResponse.ACCEPT

    def current_pose(self):
        return Pose2D(x=self.x, y=self.y, theta=self.theta)

    def execute_callback(self, goal_handle):
        """Diriger le robot vers la cible, publier le feedback, renvoyer le résultat."""
        target = goal_handle.request.target
        feedback_msg = Goto.Feedback()
        self.get_logger().info(f'Exécution du goal vers ({target.x:.2f}, {target.y:.2f})')

        while rclpy.ok():
            # Vérifier l'annulation
            if goal_handle.is_cancel_requested:
                self.v = self.w = 0.0
                goal_handle.canceled()
                return Goto.Result(reached=False, final_pose=self.current_pose())

            # Calcul du vecteur vers la cible
            dx = target.x - self.x
            dy = target.y - self.y
            distance = math.hypot(dx, dy)
            angle_to_goal = math.atan2(dy, dx)
            orientation_error = math.atan2(math.sin(angle_to_goal - self.theta),
                                           math.cos(angle_to_goal - self.theta))

            # Condition d'arrêt
            if distance < 0.05:
                self.v = self.w = 0.0
                goal_handle.succeed()
                return Goto.Result(reached=True, final_pose=self.current_pose())

            # Commande proportionnelle à la distance et à l'erreur d'orientation ;
            # le robot tourne sur place tant qu'il n'est pas orienté vers la cible.
            self.w = max(-1.0, min(2.0 * orientation_error, 1.0))
            self.v = min(0.5 * distance, 0.5) if abs(orientation_error) < 0.5 else 0.0

            # Publier le feedback
            feedback_msg.current_pose = self.current_pose()
            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.1)

        goal_handle.abort()
        return Goto.Result(reached=False, final_pose=self.current_pose())

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
        # Plusieurs threads : l'action s'exécute pendant que le timer tourne.
        rclpy.spin(node, executor=MultiThreadedExecutor())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
```

```cpp fichier=src/my_pkg_cpp/src/diff_drive_node.cpp
#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <mutex>
#include <thread>

#include "geometry_msgs/msg/pose2_d.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "my_interface/action/goto.hpp"
#include "my_interface/srv/get_pose.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"

using namespace std::chrono_literals;
using Goto = my_interface::action::Goto;
using GoalHandleGoto = rclcpp_action::ServerGoalHandle<Goto>;

// Robot à conduite différentielle simulé : /cmd_vel → position → /odom, service get_pose, action goto.
class DiffDriveNode : public rclcpp::Node
{
public:
  DiffDriveNode()
  : Node("diff_drive_node")
  {
    cmd_sub_ = create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel", 10,
      [this](const geometry_msgs::msg::Twist & msg) {set_command(msg.linear.x, msg.angular.z);});
    odom_pub_ = create_publisher<nav_msgs::msg::Odometry>("odom", 10);
    timer_ = create_wall_timer(50ms, [this]() {update();});
    // Serveur du service get_pose
    srv_ = create_service<my_interface::srv::GetPose>(
      "get_pose",
      [this](const std::shared_ptr<my_interface::srv::GetPose::Request>,
      std::shared_ptr<my_interface::srv::GetPose::Response> response) {
        std::lock_guard<std::mutex> lock(mutex_);
        response->x = x_;
        response->y = y_;
        response->theta = theta_;
        RCLCPP_INFO(get_logger(), "Service get_pose appelé : (%.2f, %.2f, %.2f)", x_, y_, theta_);
      });
    // Serveur de l'action goto
    action_server_ = rclcpp_action::create_server<Goto>(
      this, "goto",
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const Goto::Goal> goal) {
        RCLCPP_INFO(get_logger(), "Goal reçu : (%.2f, %.2f)", goal->target.x, goal->target.y);
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [this](const std::shared_ptr<GoalHandleGoto>) {
        RCLCPP_INFO(get_logger(), "Demande d'annulation reçue");
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<GoalHandleGoto> goal_handle) {
        // L'exécution est longue : un thread à part, pour ne pas bloquer le nœud.
        std::thread{[this, goal_handle]() {execute(goal_handle);}}.detach();
      });
    RCLCPP_INFO(get_logger(), "diff_drive_node prêt : commandes sur /cmd_vel, position sur /odom");
  }

private:
  geometry_msgs::msg::Pose2D current_pose()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    geometry_msgs::msg::Pose2D pose;
    pose.x = x_;
    pose.y = y_;
    pose.theta = theta_;
    return pose;
  }

  void set_command(double v, double w)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    v_ = v;
    w_ = w;
  }

  void execute(const std::shared_ptr<GoalHandleGoto> goal_handle)
  {
    const auto target = goal_handle->get_goal()->target;
    auto feedback = std::make_shared<Goto::Feedback>();
    auto result = std::make_shared<Goto::Result>();
    rclcpp::Rate rate(10);

    while (rclcpp::ok()) {
      const auto pose = current_pose();
      if (goal_handle->is_canceling()) {
        set_command(0.0, 0.0);
        result->reached = false;
        result->final_pose = pose;
        goal_handle->canceled(result);
        return;
      }
      const double dx = target.x - pose.x;
      const double dy = target.y - pose.y;
      const double distance = std::hypot(dx, dy);
      const double angle_to_goal = std::atan2(dy, dx);
      const double error = std::atan2(
        std::sin(angle_to_goal - pose.theta), std::cos(angle_to_goal - pose.theta));

      if (distance < 0.05) {
        set_command(0.0, 0.0);
        result->reached = true;
        result->final_pose = pose;
        goal_handle->succeed(result);
        return;
      }
      const double w = std::clamp(2.0 * error, -1.0, 1.0);
      const double v = std::abs(error) < 0.5 ? std::min(0.5 * distance, 0.5) : 0.0;
      set_command(v, w);

      feedback->current_pose = pose;
      goal_handle->publish_feedback(feedback);
      rate.sleep();
    }
  }

  void move_robot(double v, double w, double dt)
  {
    theta_ = std::atan2(std::sin(theta_ + w * dt), std::cos(theta_ + w * dt));
    x_ += v * std::cos(theta_) * dt;
    y_ += v * std::sin(theta_) * dt;
  }

  void update()
  {
    std::lock_guard<std::mutex> lock(mutex_);
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
  rclcpp_action::Server<Goto>::SharedPtr action_server_;
  std::mutex mutex_;  // x_, y_, theta_, v_, w_ sont partagés avec le thread de l'action
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

- le serveur d'action est créé avec `ActionServer` et quatre paramètres : le nœud, le type d'action, le nom de l'action et les fonctions de rappel ;
- `goal_callback(goal_request) -> GoalResponse` est appelé quand un client envoie un goal, pour l'accepter ou le refuser (`GoalResponse.ACCEPT` ou `GoalResponse.REJECT`) ;
- `execute_callback(goal_handle)` exécute la tâche une fois le goal accepté. Il publie le feedback avec `goal_handle.publish_feedback`, puis **doit** terminer le goal : `goal_handle.succeed()`, `goal_handle.abort()` ou `goal_handle.canceled()`, avant de renvoyer le résultat ;
- `cancel_callback(goal_handle) -> CancelResponse` est appelé quand un client demande l'annulation ; la boucle d'exécution le constate avec `goal_handle.is_cancel_requested`.

**Pourquoi un `MultiThreadedExecutor` ?** `execute_callback` dure plusieurs secondes. Avec l'exécuteur par défaut (un seul thread), le timer qui déplace le robot et publie `/odom` serait bloqué pendant tout le trajet. Avec plusieurs threads, et l'action dans son propre groupe de callbacks (`ReentrantCallbackGroup`), la boucle de l'action choisit la commande `(v, w)`, et le timer continue de faire avancer le robot. En C++, l'exécution tourne dans un `std::thread`, et un `std::mutex` protège la pose partagée.

**Le contrôleur :** le robot tourne d'abord sur place vers la cible (tant que l'erreur d'orientation dépasse 0,5 rad), puis avance à une vitesse proportionnelle à la distance, plafonnée à 0,5 m/s. Le goal est atteint à moins de 5 cm.

La version C++ utilise `rclcpp_action`, à déclarer dans son package :

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
  <depend>rclcpp_action</depend>
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
find_package(rclcpp_action REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(my_interface REQUIRED)

add_executable(diff_drive_node src/diff_drive_node.cpp)
ament_target_dependencies(diff_drive_node rclcpp rclcpp_action geometry_msgs nav_msgs my_interface)

install(TARGETS diff_drive_node DESTINATION lib/${PROJECT_NAME})

ament_package()
```

Recompilez et sourcez le workspace :

```bash
cd ~/ws/04-action
colcon build --symlink-install
source install/setup.bash
```

## 3. Tests avec la CLI

Lancez le serveur d'action en lançant le nœud :

```bash
ros2 run my_pkg diff_drive_node
```

Dans un deuxième terminal, envoyez un goal sans écrire de client, avec `ros2 action send_goal` :

```bash
source ~/ws/04-action/install/setup.bash
ros2 action list -t
ros2 action send_goal --feedback /goto my_interface/action/Goto "{target: {x: 2.0, y: 1.0, theta: 0.0}}"
```

L'option `--feedback` affiche la pose courante pendant le trajet ; la vue 2D montre le robot rejoindre le point. À la fin s'affichent le résultat et `Goal finished with status: SUCCEEDED`.

Pour tester l'annulation, envoyez un goal lointain puis appuyez sur **Ctrl+C** dans le terminal du client : `ros2 action send_goal` demande l'annulation du goal en cours.

## 4. Amélioration et pratique

- Implémenter un contrôleur PID plus robuste.
- Créer un nœud avec un client d'action (`ActionClient`) qui envoie le goal et republie les feedbacks sur un topic.
- Refuser (`GoalResponse.REJECT`) les goals situés à plus de 10 m.

**Et maintenant ?** Le robot sait livrer. Mais pour l'afficher, le simuler ou ajouter un capteur, il faut décrire sa forme : c'est le rôle de l'URDF, au module suivant.

---
titre: Paramètres et fichiers launch
resume: Rendre le robot configurable sans recompiler — paramètres déclarés, validés et modifiables à chaud, fichier YAML et fichier launch qui démarre le tout.
duree: 1 h 15
---
# Paramètres et fichiers launch

> **La situation.** Une salle de démonstration ouvre la semaine prochaine : le robot doit y rouler deux fois moins vite, et s'arrêter plus précisément. Aujourd'hui, ces valeurs sont écrites dans le code ; à chaque changement, il faut modifier et recompiler. Vous allez les transformer en paramètres, et démarrer le tout avec un seul fichier launch.

**Dans ce module, vous allez :**

- déclarer, lire et valider les paramètres d'un nœud ;
- les inspecter et les modifier pendant que le robot roule (`ros2 param`) ;
- les regrouper dans un fichier YAML et démarrer le robot avec un fichier launch.

## L'essentiel en théorie

Un robot change de réglages bien plus souvent que de code : vitesse adaptée à la pièce, précision d'arrivée, fréquence de travail. ROS 2 sépare donc ce qu'un nœud **fait** (le code) de la façon dont il est **réglé** (les paramètres), et fournit les fichiers launch pour démarrer le tout en une commande.

### Les paramètres

**Constat :** dans `diff_drive_node`, la vitesse maximale (`0.5` m/s), la tolérance d'arrivée de l'action `goto` (`0.05` m) et la période de mise à jour sont écrites en dur. Pour faire rouler le robot plus lentement dans une salle de démonstration, il faudrait modifier le code et recompiler.

**Solution :** un **paramètre** est une valeur de configuration propre à un nœud, avec un nom, un type et une valeur par défaut.

- Chaque nœud a ses propres paramètres : `/diff_drive_node` a `max_linear_speed`, un autre nœud peut avoir un paramètre du même nom sans conflit.
- Un paramètre doit être **déclaré** par le nœud avant d'être utilisé : c'est la liste de ce qui est réglable, avec les valeurs par défaut.
- Les types sont stricts : un paramètre déclaré `0.5` (un `double`) refuse la valeur `1` (un entier) ; écrivez `1.0`.

### D'où vient la valeur ?

1. La **valeur par défaut**, donnée par le code au moment de la déclaration.
2. Remplacée, au démarrage, par celle d'un **fichier YAML**, d'un **fichier launch** ou de la **ligne de commande** (`--ros-args -p nom:=valeur`).
3. Modifiable **pendant que le nœud tourne** (`ros2 param set`), si le nœud l'accepte.

Avant d'accepter une nouvelle valeur, le nœud peut la **valider** : une vitesse négative, par exemple, est refusée avec un message qui dit pourquoi. Un paramètre peut aussi être déclaré en **lecture seule**, quand il ne sert qu'au démarrage.

### Les fichiers launch

Un vrai robot démarre plusieurs nœuds, chacun avec ses paramètres et ses noms de topics. Un **fichier launch**, écrit en Python, décrit ce démarrage ; `ros2 launch` l'exécute en une seule commande. On y trouve :

- les **nœuds** à lancer, avec leurs paramètres (valeurs ou fichier YAML) ;
- des **arguments** de lancement, pour choisir un réglage sans modifier le fichier (`ros2 launch my_pkg robot.launch.py max_linear_speed:=0.2`) ;
- éventuellement d'autres fichiers launch inclus, pour composer un système complet.

Les fichiers launch et YAML sont **installés** avec le package, dans son dossier `share/` : `ros2 launch` les cherche là, pas dans vos sources.

Tutoriel officiel : [Using parameters in a class (Python)](https://docs.ros.org/en/jazzy/Tutorials/Beginner-Client-Libraries/Using-Parameters-In-A-Class-Python.html).

## 1. Déclarer et lire les paramètres

Votre workspace `~/ws/08-parametres` reprend le robot du module Action. On remplace les constantes par quatre paramètres :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `max_linear_speed` | `0.5` | vitesse linéaire maximale (m/s), pour `/cmd_vel` et `goto` |
| `max_angular_speed` | `1.0` | vitesse de rotation maximale (rad/s) |
| `goal_tolerance` | `0.05` | distance à la cible sous laquelle `goto` réussit (m) |
| `update_rate` | `20.0` | fréquence de mise à jour de la position (Hz) |

```python fichier=src/my_pkg/my_pkg/diff_drive_node.py
import math
import time

import rclpy
from geometry_msgs.msg import Pose2D, Twist
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import ParameterDescriptor, SetParametersResult
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from my_interface.action import Goto
from my_interface.srv import GetPose


def clamp(value, limit):
    return max(-limit, min(value, limit))


class DiffDriveNode(Node):
    """Robot à conduite différentielle simulé, configurable par paramètres."""

    def __init__(self):
        super().__init__('diff_drive_node')
        # Déclaration : nom, valeur par défaut (qui fixe le type) et description
        self.declare_parameter('max_linear_speed', 0.5,
                               ParameterDescriptor(description='Vitesse linéaire maximale (m/s)'))
        self.declare_parameter('max_angular_speed', 1.0,
                               ParameterDescriptor(description='Vitesse de rotation maximale (rad/s)'))
        self.declare_parameter('goal_tolerance', 0.05,
                               ParameterDescriptor(description='Distance d\'arrivée de goto (m)'))
        self.declare_parameter('update_rate', 20.0,
                               ParameterDescriptor(description='Fréquence de mise à jour (Hz), au démarrage',
                                                   read_only=True))
        # Lecture des valeurs (celles du lancement, sinon les valeurs par défaut)
        self.max_v = self.get_parameter('max_linear_speed').value
        self.max_w = self.get_parameter('max_angular_speed').value
        self.tolerance = self.get_parameter('goal_tolerance').value
        self.dt = 1.0 / self.get_parameter('update_rate').value
        # Modifications à chaud (ros2 param set) : validées avant d'être acceptées
        self.add_on_set_parameters_callback(self.on_parameters)

        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.v = 0.0
        self.w = 0.0

        self.cmd_sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.timer = self.create_timer(self.dt, self.update)
        self.srv = self.create_service(GetPose, 'get_pose', self.get_pose_callback)
        self._action_server = ActionServer(
            self,
            Goto,
            'goto',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup(),
        )
        self.get_logger().info(
            f'diff_drive_node prêt : vitesse max {self.max_v} m/s, tolérance {self.tolerance} m')

    def on_parameters(self, params):
        """Refuse une valeur invalide ; sinon l'applique immédiatement."""
        for p in params:
            if p.name in ('max_linear_speed', 'max_angular_speed', 'goal_tolerance') and p.value <= 0.0:
                return SetParametersResult(successful=False, reason=f'{p.name} doit être strictement positif')
        for p in params:
            if p.name == 'max_linear_speed':
                self.max_v = p.value
            elif p.name == 'max_angular_speed':
                self.max_w = p.value
            elif p.name == 'goal_tolerance':
                self.tolerance = p.value
        return SetParametersResult(successful=True)

    def cmd_vel_callback(self, msg):
        """Mémorise la dernière commande, limitée aux vitesses maximales."""
        self.v = clamp(msg.linear.x, self.max_v)
        self.w = clamp(msg.angular.z, self.max_w)

    def get_pose_callback(self, request, response):
        response.x = self.x
        response.y = self.y
        response.theta = self.theta
        return response

    def goal_callback(self, goal_request):
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        return CancelResponse.ACCEPT

    def current_pose(self):
        return Pose2D(x=self.x, y=self.y, theta=self.theta)

    def execute_callback(self, goal_handle):
        """Diriger le robot vers la cible, à la vitesse maximale configurée."""
        target = goal_handle.request.target
        feedback_msg = Goto.Feedback()
        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                self.v = self.w = 0.0
                goal_handle.canceled()
                return Goto.Result(reached=False, final_pose=self.current_pose())
            dx = target.x - self.x
            dy = target.y - self.y
            distance = math.hypot(dx, dy)
            orientation_error = math.atan2(math.sin(math.atan2(dy, dx) - self.theta),
                                           math.cos(math.atan2(dy, dx) - self.theta))
            if distance < self.tolerance:
                self.v = self.w = 0.0
                goal_handle.succeed()
                return Goto.Result(reached=True, final_pose=self.current_pose())
            self.w = clamp(2.0 * orientation_error, self.max_w)
            self.v = min(0.5 * distance, self.max_v) if abs(orientation_error) < 0.5 else 0.0
            feedback_msg.current_pose = self.current_pose()
            goal_handle.publish_feedback(feedback_msg)
            time.sleep(0.1)
        goal_handle.abort()
        return Goto.Result(reached=False, final_pose=self.current_pose())

    def move_robot(self, v, w, dt):
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
        rclpy.spin(node, executor=MultiThreadedExecutor())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
```

Trois points à retenir :

- `declare_parameter(nom, défaut)` : le type du paramètre est celui de la valeur par défaut ;
- `get_parameter(nom).value` lit la valeur fixée au lancement, ou la valeur par défaut ;
- `read_only=True` interdit la modification à chaud de `update_rate` : le timer est créé une fois pour toutes.

Compilez, puis lancez le nœud en fixant un paramètre sur la ligne de commande :

```bash
cd ~/ws/08-parametres
colcon build --symlink-install
source install/setup.bash
ros2 run my_pkg diff_drive_node --ros-args -p max_linear_speed:=0.3
```

## 2. Les outils `ros2 param`

Dans un second terminal :

```bash
ros2 param list /diff_drive_node                     # les paramètres déclarés
ros2 param get /diff_drive_node max_linear_speed     # Double value is: 0.3
ros2 param describe /diff_drive_node update_rate     # type, description, lecture seule
ros2 param set /diff_drive_node max_linear_speed 0.2 # Set parameter successful
ros2 param set /diff_drive_node max_linear_speed -1.0
# Setting parameter failed: max_linear_speed doit être strictement positif
ros2 param dump /diff_drive_node                     # toutes les valeurs, au format YAML
```

`add_on_set_parameters_callback` est appelée **avant** que la nouvelle valeur soit acceptée : c'est l'endroit où la refuser, avec un message qui dit pourquoi. Vérifiez l'effet avec la téléopération : au-delà de `max_linear_speed`, le robot ne va pas plus vite.

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 2.0}}"
ros2 topic echo --once /odom --field twist.twist.linear   # x: 0.2
```

## 3. Un fichier de paramètres YAML

Plutôt que de taper chaque valeur, on les regroupe dans un fichier. Sa structure est imposée : le **nom du nœud**, puis la clé `ros__parameters` (deux tirets bas), puis les paramètres.

```yaml fichier=src/my_pkg/config/robot.yaml
# Paramètres du robot pour la salle de démonstration
diff_drive_node:
  ros__parameters:
    max_linear_speed: 0.3
    max_angular_speed: 0.8
    goal_tolerance: 0.03
    update_rate: 20.0
```

```bash
ros2 run my_pkg diff_drive_node --ros-args --params-file src/my_pkg/config/robot.yaml
```

À retenir :

- la clé de premier niveau doit être **exactement** le nom du nœud (`diff_drive_node`). Avec un autre nom, ROS ne signale rien : les valeurs du fichier sont simplement ignorées et le nœud garde ses valeurs par défaut ;
- `/**:` à la place du nom applique les valeurs à tous les nœuds lancés avec ce fichier ;
- `ros2 param dump /diff_drive_node > robot.yaml` produit un fichier au bon format à partir d'un nœud réglé à la main.

## 4. Un fichier launch

Un robot réel démarre plusieurs nœuds, chacun avec ses paramètres. Un **fichier launch** (en Python) décrit ce démarrage ; `ros2 launch` l'exécute en une commande. Créez le dossier `launch` dans `my_pkg` :

```python fichier=src/my_pkg/launch/robot.launch.py
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Le fichier installé (dans install/), pas celui de src/ : voir setup.py
    config = os.path.join(get_package_share_directory('my_pkg'), 'config', 'robot.yaml')

    return LaunchDescription([
        # Argument facultatif : ros2 launch my_pkg robot.launch.py max_linear_speed:=0.4
        DeclareLaunchArgument('max_linear_speed', default_value='0.3',
                              description='Vitesse linéaire maximale (m/s)'),
        Node(
            package='my_pkg',
            executable='diff_drive_node',
            name='diff_drive_node',
            output='screen',
            # Les valeurs les plus à droite l'emportent : le fichier, puis l'argument
            parameters=[config, {'max_linear_speed': LaunchConfiguration('max_linear_speed')}],
        ),
    ])
```

`ros2 launch` cherche les fichiers launch dans le dossier `share/` **installé** du package. Il faut donc dire à `setup.py` d'y copier `launch/` et `config/` :

```python fichier=src/my_pkg/setup.py
from glob import glob

from setuptools import find_packages, setup

package_name = 'my_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Fichiers launch et paramètres, installés dans share/my_pkg/
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
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

Et déclarez dans `package.xml` les packages utilisés au lancement :

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
  <depend>rcl_interfaces</depend>
  <depend>my_interface</depend>
  <exec_depend>launch</exec_depend>
  <exec_depend>launch_ros</exec_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

## 5. Pratique

```bash
cd ~/ws/08-parametres
colcon build --symlink-install
source install/setup.bash
ros2 launch my_pkg robot.launch.py
```

Dans un second terminal :

```bash
ros2 param get /diff_drive_node goal_tolerance     # 0.03 : la valeur du fichier
ros2 param get /diff_drive_node max_linear_speed   # 0.3 : l'argument du launch
ros2 action send_goal /goto my_interface/action/Goto "{target: {x: 1.0, y: 0.0}}"
```

Relancez avec `ros2 launch my_pkg robot.launch.py max_linear_speed:=0.1` et comparez la durée du trajet : seule la configuration a changé.

Attention : avec `--symlink-install`, un fichier **ajouté** à `launch/` ou `config/` n'est installé qu'après un nouveau `colcon build`.

## 6. Rappel

- Un paramètre se **déclare** (nom, défaut, type), se **lit**, et se **valide** dans la fonction de rappel des modifications.
- `ros2 param list / get / set / dump` inspectent et règlent un nœud en marche.
- Un fichier YAML commence par le nom exact du nœud, puis `ros__parameters`.
- Un fichier launch démarre les nœuds avec leurs paramètres ; `setup.py` doit installer `launch/` et `config/`.

Prochain module : les repères du robot et leurs transformations, avec TF2.

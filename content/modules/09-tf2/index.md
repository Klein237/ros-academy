---
titre: Repères et transformations avec TF2
resume: Donner au robot ses repères (odom, base_link, laser), diffuser leurs transformations avec TF2 et convertir la position d'un obstacle d'un repère à l'autre.
duree: 1 h 30
---
# Repères et transformations avec TF2

> **La situation.** On a monté un laser à l'avant du robot. Il voit un carton à 1 m devant lui… mais pour l'éviter ou le signaler sur le plan de l'entrepôt, il faut savoir où est ce carton *dans l'entrepôt*. Entre les deux : la position du laser sur le robot, et celle du robot qui change sans cesse. C'est exactement le travail de TF2.

**Dans ce module, vous allez :**

- donner au robot ses repères (`odom`, `base_link`, `laser`) selon les conventions de ROS ;
- diffuser une transformation mobile et une transformation fixe ;
- convertir la position d'un obstacle d'un repère à l'autre avec un `Buffer` et un `TransformListener`.

## L'essentiel en théorie

**Constat :** un capteur ne mesure jamais « dans le monde ». Le laser du robot voit un obstacle *à 1 m devant lui* ; pour l'éviter ou le placer sur une carte, il faut sa position *dans la pièce*. Entre les deux : la position du laser sur le robot, et la position du robot dans la pièce, qui change à chaque instant.

**Solution :** chaque élément a son **repère** (*frame*) : une origine et trois axes. ROS 2 relie les repères par des **transformations** (translation + rotation), et la bibliothèque **TF2** calcule pour vous n'importe quelle transformation entre deux repères, en chaînant celles qui les séparent.

### Un arbre de repères

Les transformations forment un **arbre** : chaque repère a un seul parent. Les repères de notre robot suivent les conventions de ROS ([REP 105](https://www.ros.org/reps/rep-0105.html)) :

| Repère | Ce qu'il représente | Publié par |
|---|---|---|
| `odom` | le point de départ du robot : fixe dans la pièce | — (racine de l'arbre) |
| `base_link` | le robot lui-même, entre ses roues | `diff_drive_node` (mobile) |
| `laser` | le capteur, 15 cm devant et 12 cm au-dessus de `base_link` | `static_transform_publisher` (fixe) |

Pour connaître la position d'un point du laser dans `odom`, TF2 compose `odom → base_link` puis `base_link → laser`. Avec une carte, un repère `map` viendra au-dessus d'`odom` : c'est le travail de la localisation, dans le parcours Nav2.

Conventions à retenir : `x` vers l'avant, `y` vers la gauche, `z` vers le haut ; distances en mètres, angles en radians.

### Fixes ou mobiles

- Une transformation **mobile** change sans cesse, comme la position du robot dans `odom`. Elle est publiée en continu sur le topic `/tf`, avec l'heure de chaque mesure.
- Une transformation **statique** ne change jamais, comme la position du laser sur le châssis. Elle est publiée une seule fois sur `/tf_static`, et chaque nœud qui écoute la garde.

### Diffuser, écouter, dater

- Un **broadcaster** publie des transformations : il dit où se trouve un repère enfant par rapport à son parent.
- Un **listener** les reçoit et les range dans un **buffer**, une mémoire de quelques secondes. On demande ensuite au buffer « où est ce point, exprimé dans tel repère ? ».

Chaque transformation est **horodatée**. Pour un robot qui roule, la position d'un obstacle dépend de l'instant de la mesure. Le buffer interpole entre deux transformations connues, mais refuse de deviner l'avenir : demander une transformation plus récente que la dernière reçue provoque une erreur d'**extrapolation**. C'est pourquoi on attend un peu, avec un délai maximal.

### Les rotations en quaternions

Une rotation est exprimée par un **quaternion** `(x, y, z, w)` plutôt que par trois angles : aucun blocage de cardan, et des rotations faciles à composer. Pour un robot au sol, seul compte l'angle autour de `z` : la section suivante montre comment passer de l'un à l'autre.

Tutoriels officiels : [Introducing tf2](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Introduction-To-Tf2.html), [Writing a broadcaster (Python)](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Broadcaster-Py.html).

## 1. Les rotations en quaternions

Une transformation contient une rotation, exprimée par un **quaternion** `(x, y, z, w)` plutôt que par trois angles (pas de blocage de cardan, composition simple). Pour un robot au sol, seule compte la rotation autour de `z`, l'angle `θ` (*yaw*) :

```text
x = 0    y = 0    z = sin(θ / 2)    w = cos(θ / 2)
```

Attention au **demi-angle** : un robot tourné de 90° (`θ = π/2`) a `z = sin(π/4) ≈ 0.707` et `w ≈ 0.707`. Pour revenir à l'angle : `θ = atan2(2·(w·z + x·y), 1 − 2·(y² + z²))`.

## 2. Diffuser la position du robot

Votre workspace `~/ws/09-tf2` reprend le robot du module Paramètres. `diff_drive_node` publie déjà sa pose sur `/odom` ; on publie **la même pose** comme transformation `odom → base_link`, avec un `TransformBroadcaster`, à chaque mise à jour :

```python fichier=src/my_pkg/my_pkg/diff_drive_node.py
import math
import time

import rclpy
from geometry_msgs.msg import Pose2D, TransformStamped, Twist
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import ParameterDescriptor, SetParametersResult
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from tf2_ros import TransformBroadcaster

from my_interface.action import Goto
from my_interface.srv import GetPose


def clamp(value, limit):
    return max(-limit, min(value, limit))


class DiffDriveNode(Node):
    """Robot à conduite différentielle simulé : /odom et transformation odom → base_link."""

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
        # Diffuseur TF : publie sur /tf la position du repère base_link dans le repère odom
        self.tf_broadcaster = TransformBroadcaster(self)
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

    def yaw_to_quaternion(self, yaw):
        """Rotation d'un angle yaw autour de z : (x, y, z, w) = (0, 0, sin(yaw/2), cos(yaw/2))."""
        return 0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2)

    def update(self):
        self.move_robot(self.v, self.w, self.dt)
        now = self.get_clock().now().to_msg()
        qx, qy, qz, qw = self.yaw_to_quaternion(self.theta)

        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = self.v
        odom.twist.twist.angular.z = self.w
        self.odom_pub.publish(odom)

        # Même pose, publiée comme transformation : parent odom, enfant base_link, même horodatage
        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.x = qx
        t.transform.rotation.y = qy
        t.transform.rotation.z = qz
        t.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(t)

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

Une transformation publiée par un diffuseur part sur le topic `/tf`. Trois champs comptent :

- `header.frame_id` : le repère **parent** (`odom`) ;
- `child_frame_id` : le repère **enfant** (`base_link`) ;
- `header.stamp` : l'instant de la mesure. TF2 interpole entre les instants reçus ; un horodatage faux donne des transformations fausses ou refusées.

## 3. Le repère fixe du laser

Le laser ne bouge pas sur le robot : sa transformation est **statique**, publiée une fois sur `/tf_static` et gardée par tous les nœuds qui écoutent. Pas besoin de code : `tf2_ros` fournit `static_transform_publisher`. On l'ajoute au fichier launch :

```python fichier=src/my_pkg/launch/robot.launch.py
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(get_package_share_directory('my_pkg'), 'config', 'robot.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('max_linear_speed', default_value='0.3',
                              description='Vitesse linéaire maximale (m/s)'),
        Node(
            package='my_pkg',
            executable='diff_drive_node',
            name='diff_drive_node',
            output='screen',
            parameters=[config, {'max_linear_speed': LaunchConfiguration('max_linear_speed')}],
        ),
        # Le laser est fixé 15 cm devant et 12 cm au-dessus du centre du robot
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='laser_tf',
            arguments=['--x', '0.15', '--z', '0.12', '--frame-id', 'base_link', '--child-frame-id', 'laser'],
        ),
        Node(
            package='my_pkg',
            executable='obstacle_locator',
            name='obstacle_locator',
            output='screen',
        ),
    ])
```

Au module suivant, avec une description URDF du robot, c'est `robot_state_publisher` qui publiera ces transformations fixes, calculées à partir des `<joint>`.

## 4. Écouter les transformations : placer un obstacle

Le nœud `obstacle_locator` imagine un obstacle vu par le laser, à 1 m devant lui, et calcule sa position dans `odom`. Il ne fait aucun calcul de géométrie : il demande la transformation à TF2.

```python fichier=src/my_pkg/my_pkg/obstacle_locator.py
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener
import tf2_geometry_msgs  # noqa: F401  (apprend à tf2 à transformer les PointStamped)


class ObstacleLocator(Node):
    """Un obstacle vu par le laser, à 1 m devant lui : où est-il dans le repère odom ?"""

    def __init__(self):
        super().__init__('obstacle_locator')
        self.declare_parameter('distance', 1.0)
        # Le buffer garde les transformations reçues sur /tf et /tf_static (10 s par défaut)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.pub = self.create_publisher(PointStamped, 'obstacle', 10)
        self.timer = self.create_timer(0.5, self.locate)

    def locate(self):
        seen = PointStamped()
        seen.header.frame_id = 'laser'
        seen.header.stamp = Time().to_msg()  # temps 0 : la transformation la plus récente
        seen.point.x = self.get_parameter('distance').value
        try:
            in_odom = self.tf_buffer.transform(seen, 'odom', timeout=Duration(seconds=0.2))
        except TransformException as exc:
            self.get_logger().warn(f'Transformation laser → odom indisponible : {exc}')
            return
        self.pub.publish(in_odom)
        self.get_logger().info(f'Obstacle dans odom : ({in_odom.point.x:.2f}, {in_odom.point.y:.2f})',
                               throttle_duration_sec=2.0)


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleLocator()
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

- `Buffer` mémorise les transformations ; `TransformListener` le remplit en écoutant `/tf` et `/tf_static` ;
- `tf_buffer.transform(point, 'odom')` chaîne `laser → base_link → odom` ;
- l'horodatage `Time()` (zéro) demande la transformation la plus récente. Un horodatage précis demande la transformation **à cet instant**, ce qui compte pour un robot qui bouge pendant la mesure ;
- au démarrage, le buffer est vide : la première tentative échoue (`TransformException`). Il faut toujours prévoir ce cas.

Déclarez le nouveau nœud et les dépendances :

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
            'obstacle_locator = my_pkg.obstacle_locator:main',
        ],
    },
)
```

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
  <depend>tf2_ros</depend>
  <depend>tf2_geometry_msgs</depend>
  <depend>my_interface</depend>
  <exec_depend>launch</exec_depend>
  <exec_depend>launch_ros</exec_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

## 5. Pratique : observer l'arbre

```bash
cd ~/ws/09-tf2
colcon build --symlink-install
source install/setup.bash
ros2 launch my_pkg robot.launch.py
```

Dans un second terminal :

```bash
ros2 run tf2_ros tf2_echo odom laser          # translation (0.15, 0, 0.12) : robot au départ
ros2 action send_goal /goto my_interface/action/Goto "{target: {x: 0.0, y: 1.0}}"
ros2 run tf2_ros tf2_echo odom base_link      # translation ≈ (0, 1, 0), rotation : yaw ≈ 1.57
ros2 topic echo --once /obstacle              # l'obstacle est maintenant devant, vers y = 2.15
ros2 topic echo --once /tf_static             # la transformation fixe du laser
```

`tf2_echo` affiche la rotation sous trois formes (quaternion, angles en radians et en degrés) : vérifiez que le *yaw* correspond au `theta` renvoyé par `ros2 service call /get_pose my_interface/srv/GetPose`.

Pour **voir** l'arbre : ouvrez le **Bureau (RViz, Gazebo)**, lancez `rviz2` dans un terminal, choisissez *Fixed Frame* `odom` et ajoutez l'affichage **TF** ; envoyez un goal et regardez `base_link` et `laser` se déplacer ensemble. Ajoutez aussi un affichage **PointStamped** sur `/obstacle` : le point doit rester 1,15 m devant le robot.

## 6. Rappel

- Un **repère** par élément ; les transformations forment un **arbre** (`odom → base_link → laser`).
- Transformation **mobile** : un `TransformBroadcaster` sur `/tf`, à chaque mise à jour, avec le bon horodatage ; **fixe** : `static_transform_publisher` sur `/tf_static`.
- Rotation autour de `z` d'un angle θ : quaternion `(0, 0, sin(θ/2), cos(θ/2))`.
- `Buffer` + `TransformListener` pour écouter ; `transform()` ou `lookup_transform()` pour convertir, en gérant `TransformException`.

**Et maintenant ?** Le robot sait situer ce qu'il voit. Mais ROS ne connaît encore ni sa forme ni la place de ses roues : le module suivant les décrit en URDF, et `robot_state_publisher` en tirera les repères de chaque pièce.

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
        """Rotation d'un angle yaw autour de z."""
        return 0.0, 0.0, math.sin(yaw), math.cos(yaw)

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

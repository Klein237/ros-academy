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

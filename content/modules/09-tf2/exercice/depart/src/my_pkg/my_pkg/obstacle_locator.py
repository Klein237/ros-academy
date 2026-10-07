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

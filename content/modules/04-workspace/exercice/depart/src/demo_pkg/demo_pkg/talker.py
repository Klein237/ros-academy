import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class Talker(Node):
    """Publie un message sur /bavardage chaque seconde."""

    def __init__(self):
        super().__init__('talker')
        self.pub = self.create_publisher(String, 'bavardage', 10)
        self.count = 0
        self.create_timer(1.0, self.parler)

    def parler(self):
        self.count += 1
        msg = String(data=f'Bonjour ROS 2 ! ({self.count})')
        self.pub.publish(msg)
        self.get_logger().info(f'Publication : {msg.data}')


def main(args=None):
    rclpy.init(args=args)
    node = Talker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()

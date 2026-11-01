"""Lidar simulé du lab : une allée libre, une personne qui traverse de temps en temps, et des mesures invalides."""

import math
import random

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

N_RAYONS = 360


class LidarSimule(Node):

    def __init__(self):
        super().__init__('lidar_simule')
        self.scan = self.create_publisher(LaserScan, '/scan', 10)
        self.hasard = random.Random()
        self.i = 0
        self.create_timer(0.1, self.publier)

    def publier(self):
        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'laser'
        msg.angle_min, msg.angle_increment = -math.pi, 2 * math.pi / N_RAYONS
        msg.angle_max = math.pi - msg.angle_increment
        msg.scan_time, msg.range_min, msg.range_max = 0.1, 0.12, 12.0
        personne = self.i % 100 >= 80                       # 2 s toutes les 10 s
        distances = []
        for k in range(N_RAYONS):
            a = msg.angle_min + k * msg.angle_increment
            d = 1.0 / abs(math.sin(a)) if abs(math.sin(a)) > 1e-6 else math.inf
            if personne and abs(a) < math.radians(10):
                d = 0.3
            distances.append(d if d <= msg.range_max else math.inf)
        if not personne and self.hasard.random() < 0.3:
            for k in self.hasard.sample(range(N_RAYONS), 3):
                distances[k] = 0.0
        msg.ranges = distances
        self.scan.publish(msg)
        self.i += 1


def main():
    rclpy.init()
    noeud = LidarSimule()
    try:
        rclpy.spin(noeud)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        noeud.destroy_node()
        rclpy.try_shutdown()

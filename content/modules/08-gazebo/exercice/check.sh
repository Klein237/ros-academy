#!/usr/bin/env bash
# Vérifie dans Gazebo qu'une commande de rotation vers la gauche fait tourner le robot vers la gauche.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS et simulateur dédiés : la vérification ne voit pas ce que vous avez lancé.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
export GAZEBO_MASTER_URI=http://127.0.0.1:$((12000 + RANDOM % 2000))
setsid ros2 launch my_robot_description gazebo.launch.py > "$EXERCICE/check-gazebo.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; sleep 2; kill -KILL -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT

cat > "$EXERCICE/verif_rotation.py" <<'PY'
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

rclpy.init()
node = rclpy.create_node('verification_rotation')
poses = []
node.create_subscription(Odometry, 'odom', lambda m: poses.append(m.pose.pose), 10)
cmd = node.create_publisher(Twist, 'cmd_vel', 10)


def spin_for(seconds, twist=None):
    end = time.time() + seconds
    while time.time() < end:
        if twist is not None:
            cmd.publish(twist)
        rclpy.spin_once(node, timeout_sec=0.1)


def yaw(p):
    q = p.orientation
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))


deadline = time.time() + 120  # démarrage de Gazebo et apparition du robot
while not poses and time.time() < deadline:
    rclpy.spin_once(node, timeout_sec=0.5)
if not poses:
    print("Pas d'odométrie sur /odom : le robot n'est pas apparu dans Gazebo (journal : check-gazebo.log).")
    sys.exit(1)
spin_for(2.0)  # le robot se pose
depart = yaw(poses[-1])
gauche = Twist()
gauche.angular.z = 0.6
spin_for(4.0, gauche)
spin_for(1.5, Twist())  # arrêt
rotation = math.atan2(math.sin(yaw(poses[-1]) - depart), math.cos(yaw(poses[-1]) - depart))
print(f"Commande angular.z = +0.6 rad/s pendant 4 s : le robot a tourné de {rotation:+.2f} rad.")
if rotation < -0.3:
    print("Il tourne vers la droite (sens des aiguilles d'une montre) au lieu de la gauche.")
    sys.exit(1)
if rotation < 0.3:
    print("Il ne tourne presque pas : les roues reçoivent-elles des vitesses différentes ?")
    sys.exit(1)
print("Il tourne vers la gauche, comme demandé.")
PY
timeout 200 python3 "$EXERCICE/verif_rotation.py" 2>"$EXERCICE/verif_rotation.log"

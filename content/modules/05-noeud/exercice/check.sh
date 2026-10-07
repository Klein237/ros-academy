#!/usr/bin/env bash
# Vérifie que le robot avance quand on publie une commande sur /cmd_vel.
set +u
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install --packages-select my_pkg > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
# setsid : le nœud a son propre groupe de processus, arrêté en entier à la fin.
setsid ros2 run my_pkg diff_drive_node > "$EXERCICE/check-node.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT

python3 - <<'PY'
import sys, time
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

rclpy.init()
node = rclpy.create_node('verification')
pub = node.create_publisher(Twist, 'cmd_vel', 10)
last = {}
node.create_subscription(Odometry, 'odom', lambda m: last.update(x=m.pose.pose.position.x), 10)

deadline = time.time() + 15
while 'x' not in last and time.time() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
if 'x' not in last:
    print("Aucun message sur /odom : le nœud diff_drive_node ne publie pas sa position.")
    sys.exit(1)
start = last['x']
cmd = Twist()
cmd.linear.x = 0.5
end = time.time() + 3
while time.time() < end:
    pub.publish(cmd)
    rclpy.spin_once(node, timeout_sec=0.1)
moved = last['x'] - start
if moved < 0.3:
    print(f"Le robot n'avance pas : x a changé de {moved:.2f} m en 3 s à 0,5 m/s sur /cmd_vel.")
    sys.exit(1)
print(f"Le robot avance : {moved:.2f} m parcourus en 3 s.")
PY

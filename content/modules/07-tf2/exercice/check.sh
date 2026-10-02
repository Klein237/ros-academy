#!/usr/bin/env bash
# Vérifie que la transformation odom → base_link a la pose du robot, et que l'obstacle est bien placé.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 launch my_pkg robot.launch.py > "$EXERCICE/check-launch.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT

# Le robot se tourne vers y croissant (yaw ≈ π/2) et avance de 1 m
out=$(timeout 90 ros2 action send_goal /goto my_interface/action/Goto "{target: {x: 0.0, y: 1.0}}" 2>&1)
if ! grep -q "Goal finished with status: SUCCEEDED" <<<"$out"; then
  echo "Le robot n'atteint pas la cible (0, 1) : $(tail -2 <<<"$out")"
  exit 1
fi

cat > "$EXERCICE/verif_tf.py" <<'PY'
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PointStamped
from my_interface.srv import GetPose
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

rclpy.init()
node = rclpy.create_node('verification_tf')
buf = Buffer()
TransformListener(buf, node)
obstacle = []
node.create_subscription(PointStamped, 'obstacle', lambda m: obstacle.append(m), 10)
client = node.create_client(GetPose, 'get_pose')
deadline = time.time() + 20
while time.time() < deadline and not (buf.can_transform('odom', 'base_link', Time()) and obstacle):
    rclpy.spin_once(node, timeout_sec=0.2)
if not buf.can_transform('odom', 'base_link', Time()):
    print("Aucune transformation odom → base_link n'est publiée sur /tf.")
    sys.exit(1)
if not client.wait_for_service(timeout_sec=10):
    print("Le service get_pose ne répond pas.")
    sys.exit(1)
future = client.call_async(GetPose.Request())
rclpy.spin_until_future_complete(node, future, timeout_sec=10)
pose = future.result()
t = buf.lookup_transform('odom', 'base_link', Time()).transform
q = t.rotation
yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))
ecart = abs(math.atan2(math.sin(yaw - pose.theta), math.cos(yaw - pose.theta)))
norme = math.sqrt(q.x ** 2 + q.y ** 2 + q.z ** 2 + q.w ** 2)
print(f"Pose du robot : x={pose.x:.2f} y={pose.y:.2f} theta={pose.theta:.2f} rad")
print(f"TF odom → base_link : x={t.translation.x:.2f} y={t.translation.y:.2f} yaw={yaw:.2f} rad")
if abs(t.translation.x - pose.x) > 0.05 or abs(t.translation.y - pose.y) > 0.05:
    print("La position publiée sur /tf ne correspond pas à celle du robot.")
    sys.exit(1)
if ecart > 0.05:
    print(f"L'orientation publiée sur /tf diffère de {ecart:.2f} rad de celle du robot.")
    sys.exit(1)
if not obstacle:
    print("obstacle_locator ne publie rien sur /obstacle.")
    sys.exit(1)
p = obstacle[-1].point
# laser à 0.15 m devant le robot, obstacle à 1 m devant le laser
ex, ey = pose.x + 1.15 * math.cos(pose.theta), pose.y + 1.15 * math.sin(pose.theta)
print(f"Obstacle dans odom : ({p.x:.2f}, {p.y:.2f}) ; attendu ({ex:.2f}, {ey:.2f})")
if math.hypot(p.x - ex, p.y - ey) > 0.05:
    print("L'obstacle n'est pas à 1 m devant le laser.")
    sys.exit(1)
PY
timeout 60 python3 "$EXERCICE/verif_tf.py" 2>"$EXERCICE/verif_tf.log"

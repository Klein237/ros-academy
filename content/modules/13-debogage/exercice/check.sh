#!/usr/bin/env bash
# Vérifie que la patrouille fait rouler le robot, sans changer le type de /cmd_vel attendu par le robot.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
LOG="$EXERCICE/check-launch.log"
setsid ros2 launch my_pkg patrouille.launch.py > "$LOG" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT

for _ in $(seq 1 20); do
  timeout 10 ros2 service call /get_pose my_interface/srv/GetPose > /dev/null 2>&1 && break
  sleep 1
done
sleep 4
for _ in $(seq 1 10); do  # la liste des topics peut être incomplète juste après le démarrage
  types=$(timeout 10 ros2 topic list -t 2>/dev/null | grep "^/cmd_vel ")
  [ "$types" = "/cmd_vel [geometry_msgs/msg/Twist]" ] && break
  sleep 1
done
if [ "$types" != "/cmd_vel [geometry_msgs/msg/Twist]" ]; then
  echo "Types : ${types:-aucun sur /cmd_vel}. Le robot et ses autres clients attendent geometry_msgs/msg/Twist."
  exit 1
fi
pose=$(timeout 10 ros2 service call /get_pose my_interface/srv/GetPose 2>/dev/null)
distance=$(python3 -c '
import re, sys
s = sys.argv[1]
m = [re.search(rf"\b{k}=([-0-9.e]+)", s) for k in ("x", "y")]
print("%.2f" % ((float(m[0].group(1)) ** 2 + float(m[1].group(1)) ** 2) ** 0.5) if all(m) else "")
' "$pose")
if [ -z "$distance" ]; then
  echo "Le robot ne répond pas au service /get_pose (journal : $LOG)."
  exit 1
fi
if python3 -c "import sys; sys.exit(float(sys.argv[1]) > 0.2)" "$distance"; then
  echo "Après 4 s de patrouille, le robot est à $distance m de son point de départ : il n'a pas bougé."
  exit 1
fi
echo "La patrouille fait rouler le robot : $distance m parcourus depuis le départ."

#!/usr/bin/env bash
# La couche de sécurité du cours limite la vitesse, arrête le robot sans commande (chien de garde)
# et bloque les commandes pendant l'arrêt d'urgence.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=90
setsid ros2 launch my_pkg robot_securise.launch.py > /tmp/launch.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null || true' EXIT
pose() {  # distance du robot à l'origine, en mètres
  timeout 10 ros2 service call /get_pose my_interface/srv/GetPose | python3 -c '
import re, sys
s = sys.stdin.read()
x, y = (float(re.search(rf"\b{k}=([-0-9.e]+)", s).group(1)) for k in ("x", "y"))
print("%.4f" % (x * x + y * y) ** 0.5)'
}
for _ in $(seq 1 20); do grep -q "garde_node prêt" /tmp/launch.log && pose > /dev/null 2>&1 && break; sleep 1; done
# 2 s de commandes à 1 m/s : la vitesse publiée est limitée à 0,3 m/s
timeout 15 ros2 topic echo /cmd_vel geometry_msgs/msg/Twist --field linear.x > /tmp/vitesses.log 2>&1 &
ECHO=$!
timeout 15 ros2 topic pub -r 10 -t 20 /cmd_vel_brut geometry_msgs/msg/Twist "{linear: {x: 1.0}}" > /dev/null
sleep 1.5
kill $ECHO 2>/dev/null || true
python3 - /tmp/vitesses.log <<'PY'
import sys
v = [float(l) for l in open(sys.argv[1]) if l.strip() and l.strip() != "---" and l.strip()[0] in "-0123456789"]
assert v and max(v) <= 0.3001 and max(v) > 0.25, f"vitesses publiées : max {max(v) if v else None}"
assert v[-1] == 0.0, f"dernière vitesse publiée : {v[-1]}"
PY
grep -q "Aucune commande depuis 0.5 s" /tmp/launch.log || { tail -20 /tmp/launch.log; exit 1; }
a=$(pose); sleep 1; b=$(pose)
python3 -c "import sys; a, b = map(float, sys.argv[1:]); assert a > 0.05 and abs(b - a) < 0.002, (a, b)" "$a" "$b"
# arrêt d'urgence : des commandes arrivent, le robot reste immobile
timeout 10 ros2 service call /arret_urgence std_srvs/srv/SetBool "{data: true}" | grep -q "success=True"
timeout 15 ros2 topic pub -r 10 /cmd_vel_brut geometry_msgs/msg/Twist "{linear: {x: 0.2}}" > /dev/null &
PUB=$!
sleep 2; c=$(pose); sleep 1; d=$(pose)
kill $PUB 2>/dev/null || true
python3 -c "import sys; c, d = map(float, sys.argv[1:]); assert abs(d - c) < 0.002, (c, d)" "$c" "$d"
echo "limites, chien de garde et arrêt d'urgence : OK"

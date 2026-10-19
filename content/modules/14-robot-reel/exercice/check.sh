#!/usr/bin/env bash
# Vérifie que garde_node laisse passer les commandes, puis arrête le robot quand elles cessent.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
LOG="$EXERCICE/check-launch.log"
setsid ros2 launch my_pkg robot_securise.launch.py > "$LOG" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT

distance() {  # distance du robot à son point de départ, en mètres (vide si pas de réponse)
  timeout 10 ros2 service call /get_pose my_interface/srv/GetPose 2>/dev/null | python3 -c '
import re, sys
s = sys.stdin.read()
m = [re.search(rf"\b{k}=([-0-9.e]+)", s) for k in ("x", "y")]
print("%.3f" % ((float(m[0].group(1)) ** 2 + float(m[1].group(1)) ** 2) ** 0.5) if all(m) else "")'
}
for _ in $(seq 1 20); do [ -n "$(distance)" ] && break; sleep 1; done
if [ -z "$(distance)" ]; then
  echo "Le robot ne répond pas au service /get_pose (journal : $LOG)."
  exit 1
fi
avance() {  # vrai si la distance $1 dépasse 5 cm
  python3 -c "import sys; sys.exit(not float(sys.argv[1] or 0) > 0.05)" "$1"
}
# Commandes à 10 Hz jusqu'à ce que le robot ait avancé (10 s au plus), puis plus rien. En continu
# plutôt qu'une rafale de 2 s : sur une machine chargée, les premiers messages peuvent se perdre.
setsid ros2 topic pub -r 10 /cmd_vel_brut geometry_msgs/msg/Twist "{linear: {x: 0.2}}" > /dev/null 2>&1 &
PUB=$!
trap 'kill -TERM -- -$PUB 2>/dev/null; kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT
a=""
for _ in $(seq 1 10); do
  sleep 1
  a=$(distance)
  avance "$a" && break
done
kill -TERM -- -$PUB 2>/dev/null; wait $PUB 2>/dev/null
if ! avance "$a"; then
  echo "Le robot n'a pas avancé pendant 10 s de commandes (${a:-?} m) : garde_node doit laisser passer les commandes."
  exit 1
fi
sleep 1.5
a=$(distance); sleep 2; b=$(distance)
if python3 -c "import sys; a, b = map(float, sys.argv[1:]); sys.exit(b - a < 0.01)" "$a" "$b"; then
  echo "Les commandes ont cessé depuis plus de 1,5 s, mais le robot roule encore : $a m, puis $b m deux secondes plus tard."
  exit 1
fi
echo "Le robot a avancé de $a m, puis s'est arrêté quand les commandes ont cessé."

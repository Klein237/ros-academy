#!/usr/bin/env bash
# Vérifie que le superviseur reçoit les mesures du pilote de batterie, resté en BEST_EFFORT.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
LOG="$EXERCICE/check-launch.log"
setsid ros2 launch my_pkg supervision.launch.py > "$LOG" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT

for _ in $(seq 1 20); do
  grep -q "Batterie : " "$LOG" && break
  sleep 1
done
for _ in $(seq 1 10); do  # juste après le démarrage, l'éditeur peut ne pas encore être visible
  fiabilite=$(timeout 10 ros2 topic info -v /battery_state 2>/dev/null \
    | awk '/Endpoint type: PUBLISHER/ {p=1} p && /Reliability:/ {print $2; exit}')
  [ -n "$fiabilite" ] && break
  sleep 1
done
if [ "$fiabilite" != "BEST_EFFORT" ]; then
  echo "Le pilote de batterie ne publie plus en BEST_EFFORT (${fiabilite:-introuvable}) : c'est le code du fabricant, ne le modifiez pas."
  exit 1
fi
if ! grep -q "Batterie : " "$LOG"; then
  echo "Le superviseur ne reçoit toujours aucune mesure de batterie (journal : $LOG)."
  exit 1
fi
echo "Le superviseur reçoit la batterie : $(grep -o 'Batterie : [0-9]* %' "$LOG" | tail -1)."

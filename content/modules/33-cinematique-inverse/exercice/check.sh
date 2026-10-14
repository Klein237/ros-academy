#!/usr/bin/env bash
# Vérifie que la pince arrive sur la cible publiée sur /cible.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 launch bras_description display.launch.py jsp:=false > "$EXERCICE/check-launch.log" 2>&1 &
DESCRIPTION=$!
setsid ros2 run bras_controle cinematique_inverse > "$EXERCICE/check-noeud.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$DESCRIPTION -$NODE 2>/dev/null; wait 2>/dev/null' EXIT
if ! timeout 60 python3 "$EXERCICE/comparer.py" cible 0.30 0.10 0.15 2> "$EXERCICE/comparer.log"; then
  grep -m1 "ignorée" "$EXERCICE/check-noeud.log"
  exit 1
fi

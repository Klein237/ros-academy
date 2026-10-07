#!/usr/bin/env bash
# Vérifie que le fichier launch applique les paramètres de config/robot.yaml au nœud.
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

valeur() {  # valeur d'un paramètre du nœud (attend qu'il soit prêt)
  for _ in $(seq 1 20); do
    out=$(timeout 10 ros2 param get /diff_drive_node "$1" 2>/dev/null) && { awk '{print $NF}' <<<"$out"; return; }
    sleep 1
  done
}
v=$(valeur max_linear_speed)
if [ -z "$v" ]; then
  echo "Le nœud /diff_drive_node n'a pas démarré avec robot.launch.py (journal : $EXERCICE/check-launch.log)."
  exit 1
fi
t=$(valeur goal_tolerance)
if [ "$v" != "0.15" ] || [ "$t" != "0.02" ]; then
  echo "Paramètres du nœud : max_linear_speed=$v, goal_tolerance=$t ; config/robot.yaml demande 0.15 et 0.02."
  echo "Les valeurs du fichier ne sont pas appliquées au nœud."
  exit 1
fi
echo "Le nœud applique config/robot.yaml : max_linear_speed=$v, goal_tolerance=$t."

#!/usr/bin/env bash
# Vérifie la description du bras : URDF valide, puis pince au bon endroit pour une pose donnée.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
X=src/bras_description/urdf/bras.urdf.xacro
if ! xacro "$X" > "$EXERCICE/bras.urdf" 2> "$EXERCICE/xacro.log"; then
  echo "xacro échoue : $(head -3 "$EXERCICE/xacro.log")"
  exit 1
fi
if ! check_urdf "$EXERCICE/bras.urdf" > "$EXERCICE/check_urdf.log" 2>&1; then
  echo "check_urdf refuse la description :"
  grep -i "error" "$EXERCICE/check_urdf.log" | head -3
  exit 1
fi
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 launch bras_description display.launch.py jsp:=false > "$EXERCICE/check-launch.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT
# tourelle 0,3 rad, épaule 0,5, coude 0,8, poignet -0,4 : la pince doit être là où le calcul l'attend
timeout 60 python3 "$EXERCICE/comparer.py" tf 0.3 0.5 0.8 -0.4 2> "$EXERCICE/comparer.log"

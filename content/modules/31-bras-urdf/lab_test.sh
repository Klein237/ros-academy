#!/usr/bin/env bash
# La description écrite dans le cours est valide, et la pince est là où le calcul l'attend.
set -e
source install/setup.bash
SHARE=$(ros2 pkg prefix bras_description)/share/bras_description
xacro "$SHARE/urdf/bras.urdf.xacro" > /tmp/bras.urdf
check_urdf /tmp/bras.urdf | grep -q "root Link: base_link"
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 launch bras_description display.launch.py jsp:=false > /tmp/launch.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null || true' EXIT
timeout 60 python3 "$(dirname "$0")/exercice/comparer.py" tf -0.5 0.9 0.6 0.3

#!/usr/bin/env bash
# La description du bras est valide et, tous les angles à 0, la pince est à 0,75 m au-dessus du socle.
set -e
source install/setup.bash
SHARE=$(ros2 pkg prefix bras_description)/share/bras_description
xacro "$SHARE/urdf/bras.urdf.xacro" > /tmp/bras.urdf
check_urdf /tmp/bras.urdf | grep -q "root Link: base_link"
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 launch bras_description display.launch.py > /tmp/launch.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null || true' EXIT
ligne=$(timeout 20 ros2 run tf2_ros tf2_echo base_link tool0 2>&1 | grep -m1 "Translation")
echo "base_link → tool0 $ligne"
python3 - "$ligne" <<'PY'
import re
import sys
x, y, z = map(float, re.findall(r"-?\d+\.\d+", sys.argv[1])[:3])
sys.exit(0 if abs(x) < 0.005 and abs(y) < 0.005 and abs(z - 0.75) < 0.005 else 1)
PY

#!/usr/bin/env bash
# La mission, publiée avant l'arrivée du moniteur, lui parvient (TRANSIENT_LOCAL) ; il suit /odom en BEST_EFFORT.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=88
setsid ros2 launch my_pkg robot.launch.py > /tmp/launch.log 2>&1 &
ROBOT=$!
setsid ros2 run my_pkg mission_node > /tmp/mission.log 2>&1 &
MISSION=$!
MONITEUR=$MISSION
trap 'kill -TERM -- -$ROBOT -$MISSION -$MONITEUR 2>/dev/null; wait 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do grep -q "Mission publiée" /tmp/mission.log && break; sleep 1; done
sleep 2
setsid ros2 run my_pkg moniteur_node > /tmp/moniteur.log 2>&1 &
MONITEUR=$!
for _ in $(seq 1 20); do grep -q "Robot en x=" /tmp/moniteur.log && break; sleep 1; done
grep -q "Mission reçue : livrer le colis 42" /tmp/moniteur.log || { cat /tmp/mission.log /tmp/moniteur.log; exit 1; }
grep -q "Robot en x=" /tmp/moniteur.log || { cat /tmp/moniteur.log /tmp/launch.log | tail -20; exit 1; }
# un abonné volatile, arrivé après la publication, ne reçoit pas la mission
if timeout 5 ros2 topic echo --once --qos-durability volatile /mission std_msgs/msg/String > /tmp/volatile.log 2>&1; then
  echo "un abonné volatile a reçu la mission"; cat /tmp/volatile.log; exit 1
fi
echo "mission reçue en TRANSIENT_LOCAL, odométrie en BEST_EFFORT : OK"

#!/usr/bin/env bash
# Rejoue les commandes du cours : enregistrer le lidar simulé, inspecter, tester l'enregistrement, rejouer.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
BAG=src/arret_urgence/test/donnees/couloir
rm -rf "$BAG" && mkdir -p "$(dirname "$BAG")"
setsid ros2 run arret_urgence lidar_simule > /tmp/lidar.log 2>&1 &
LIDAR=$!
arreter() { kill -INT -- -"$1" 2>/dev/null || true; wait "$1" 2>/dev/null || true; }
trap 'arreter $LIDAR' EXIT
sleep 2
timeout -s INT 5 ros2 bag record -o "$BAG" /scan > /tmp/record.log 2>&1 || true
arreter $LIDAR
ros2 bag info "$BAG" | tee /tmp/info.txt | grep -q "sensor_msgs/msg/LaserScan" || { cat /tmp/record.log /tmp/info.txt; exit 1; }
(cd src/arret_urgence && python3 -m pytest -q -p no:cacheprovider test)
setsid ros2 run arret_urgence arret_urgence > /tmp/noeud.log 2>&1 &
NOEUD=$!
trap 'arreter $NOEUD' EXIT
sleep 2
ros2 bag play "$BAG" > /tmp/play.log 2>&1 &
timeout 20 ros2 topic echo --once /arret std_msgs/msg/Bool > /tmp/arret.txt
grep -q "data:" /tmp/arret.txt
echo "enregistrement, inspection, test et rejeu : ok"

#!/usr/bin/env bash
# Rejoue les commandes du cours : création d'un package, compilation, lancement.
set -e
mkdir -p src
(cd src && ros2 pkg create mon_premier_pkg --build-type ament_python --node-name mon_noeud > /dev/null)
colcon build --symlink-install > /dev/null
source install/setup.bash
ros2 pkg executables mon_premier_pkg | grep -qx "mon_premier_pkg mon_noeud"
timeout 20 ros2 run mon_premier_pkg mon_noeud | grep -q "Hi from mon_premier_pkg"
echo "mon_premier_pkg : créé, compilé, lancé"

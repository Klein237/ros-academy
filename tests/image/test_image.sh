#!/usr/bin/env bash
set -euo pipefail
IMG="${IMG:-ros-lab:0.1.0}"

run() { docker run --rm "$IMG" bash -lc "$1"; }
fail() { echo "FAIL: $1"; exit 1; }

[ "$(run 'whoami')" = "etudiant" ] || fail "l'utilisateur n'est pas etudiant"
[ "$(run 'id -u')" = "1000" ] || fail "uid différent de 1000"
if run 'command -v sudo' >/dev/null; then fail "sudo est présent"; fi
[ "$(run 'echo $ROS_LOCALHOST_ONLY')" = "1" ] || fail "ROS_LOCALHOST_ONLY absent"
[ "$(run 'echo $ROS_DISTRO')" = "humble" ] || fail "ROS non sourcé"
grep -qx rclpy <<<"$(run 'ros2 pkg list')" || fail "rclpy manquant"
grep -qx rclcpp <<<"$(run 'ros2 pkg list')" || fail "rclcpp manquant"
grep -qx rosbridge_server <<<"$(run 'ros2 pkg list')" || fail "rosbridge_server manquant"
run 'command -v colcon' >/dev/null || fail "colcon manquant"
grep -q '^5\.2\.1' <<<"$(run 'jupyterhub-singleuser --version')" || fail "jupyterhub-singleuser 5.2.1 manquant"
run 'python3 -c "import jupyter_server_proxy"' || fail "jupyter-server-proxy manquant"
run 'cd /tmp && mkdir -p ws/src && cd ws/src \
     && ros2 pkg create --build-type ament_python py_pkg >/dev/null \
     && ros2 pkg create --build-type ament_cmake cpp_pkg >/dev/null \
     && cd .. && colcon build >/dev/null' || fail "colcon build Python + C++ échoue"
for pkg in xacro joint_state_publisher robot_state_publisher tf2_tools action_tutorials_py demo_nodes_py; do
  grep -qx "$pkg" <<<"$(run 'ros2 pkg list')" || fail "$pkg manquant"
done
run 'command -v check_urdf' >/dev/null || fail "check_urdf manquant"
run 'command -v academy-diffbot' >/dev/null || fail "academy-diffbot manquant"
# le robot simulé avance quand il reçoit une commande
odom_x=$(run 'academy-diffbot >/dev/null 2>&1 & sleep 3
  ros2 topic pub -r 10 -t 20 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.5}}" >/dev/null &
  sleep 1.5; ros2 topic echo --once /odom | awk "/position:/ {p=1} p && /x:/ {print \$2; exit}"')
awk -v x="$odom_x" 'BEGIN { exit !(x > 0.1) }' || fail "academy-diffbot n'avance pas (x=$odom_x)"
# bureau graphique : RViz2 et Gazebo installés, écran virtuel démarré comme dans un lab
# (racine en lecture seule, /tmp en tmpfs, dossier personnel inscriptible comme le volume
# de l'étudiant), fenêtre RViz créée avec le rendu logiciel
for pkg in rviz2 gazebo_ros joint_state_publisher_gui; do
  grep -qx "$pkg" <<<"$(run 'ros2 pkg list')" || fail "$pkg manquant"
done
for cmd in academy-bureau Xvnc websockify openbox gzserver; do
  run "command -v $cmd" >/dev/null || fail "$cmd manquant"
done
bureau=$(docker run --rm --read-only --tmpfs /tmp:size=512m --tmpfs /home/etudiant:uid=1000,gid=1000 "$IMG" bash -lc '
  academy-bureau 6080 >/tmp/bureau.log 2>&1 &
  for _ in $(seq 1 50); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.2; done
  xdpyinfo >/dev/null 2>&1 && echo ECRAN-OK
  rviz2 >/tmp/rviz.log 2>&1 &
  RVIZ=$!
  for _ in $(seq 1 60); do xwininfo -root -tree | grep -qi rviz && break; sleep 1; done
  sleep 5
  xwininfo -root -tree | grep -qi rviz && kill -0 $RVIZ 2>/dev/null && echo RVIZ-OK || tail -20 /tmp/rviz.log
  timeout 25 gzserver --verbose >/tmp/gz.log 2>&1 & GZ=$!
  sleep 15; kill -0 $GZ 2>/dev/null && echo GZSERVER-OK || tail -20 /tmp/gz.log
  kill $GZ $RVIZ 2>/dev/null || true')
grep -q ECRAN-OK <<<"$bureau" || fail "écran virtuel non démarré : $bureau"
grep -q RVIZ-OK <<<"$bureau" || fail "RViz2 ne s'ouvre pas sur le bureau : $bureau"
grep -q GZSERVER-OK <<<"$bureau" || fail "gzserver ne démarre pas : $bureau"
echo "ALL IMAGE TESTS PASSED"

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
echo "ALL IMAGE TESTS PASSED"

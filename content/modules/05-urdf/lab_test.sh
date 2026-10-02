#!/usr/bin/env bash
# La description est valide et robot_state_publisher publie les TF du robot.
set -e
source install/setup.bash
SHARE=$(ros2 pkg prefix my_robot_description)/share/my_robot_description
xacro "$SHARE/urdf/my_robot.urdf.xacro" > /tmp/my_robot.urdf
check_urdf /tmp/my_robot.urdf | grep -q "root Link: base_link"
export ROS_DOMAIN_ID=91
if ros2 pkg prefix joint_state_publisher > /dev/null 2>&1; then
  setsid ros2 launch my_robot_description display.launch.py > /tmp/launch.log 2>&1 &
else  # image sans joint_state_publisher : robot_state_publisher seul (joints fixes)
  setsid ros2 run robot_state_publisher robot_state_publisher /tmp/my_robot.urdf > /tmp/launch.log 2>&1 &
fi
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null || true' EXIT
timeout 20 ros2 run tf2_ros tf2_echo base_link caster_wheel 2>&1 | grep -m1 -q "Translation"
echo "TF base_link → caster_wheel publiée"

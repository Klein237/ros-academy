cmake_minimum_required(VERSION 3.8)
project(my_interface)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/GetPose.srv"
  "action/Goto.action"
  DEPENDENCIES geometry_msgs
)

ament_package()

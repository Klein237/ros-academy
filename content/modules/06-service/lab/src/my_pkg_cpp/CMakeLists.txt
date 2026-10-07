cmake_minimum_required(VERSION 3.8)
project(my_pkg_cpp)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)

add_executable(diff_drive_node src/diff_drive_node.cpp)
ament_target_dependencies(diff_drive_node rclcpp geometry_msgs nav_msgs)

install(TARGETS diff_drive_node DESTINATION lib/${PROJECT_NAME})

ament_package()

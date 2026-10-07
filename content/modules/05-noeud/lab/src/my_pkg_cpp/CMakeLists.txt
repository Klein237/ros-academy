cmake_minimum_required(VERSION 3.8)
project(my_pkg_cpp)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)

ament_package()

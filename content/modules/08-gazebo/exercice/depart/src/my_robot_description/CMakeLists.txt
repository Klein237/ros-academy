cmake_minimum_required(VERSION 3.8)
project(my_robot_description)

find_package(ament_cmake REQUIRED)

# Installe la description, les fichiers de lancement, les mondes et le pont dans share/my_robot_description
install(DIRECTORY urdf launch worlds config DESTINATION share/${PROJECT_NAME})

ament_package()

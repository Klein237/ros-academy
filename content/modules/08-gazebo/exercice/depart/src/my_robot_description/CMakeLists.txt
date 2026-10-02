cmake_minimum_required(VERSION 3.8)
project(my_robot_description)

find_package(ament_cmake REQUIRED)

# Installe la description, les fichiers de lancement et les mondes dans share/my_robot_description
install(DIRECTORY urdf launch worlds DESTINATION share/${PROJECT_NAME})

ament_package()

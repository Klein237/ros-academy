cmake_minimum_required(VERSION 3.8)
project(bras_description)

find_package(ament_cmake REQUIRED)

# Installe la description et le fichier de lancement dans share/bras_description
install(DIRECTORY urdf launch DESTINATION share/${PROJECT_NAME})

ament_package()

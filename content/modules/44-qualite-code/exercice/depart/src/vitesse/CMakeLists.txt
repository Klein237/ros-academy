cmake_minimum_required(VERSION 3.8)
project(vitesse)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

add_library(borner src/borner.cpp)
target_include_directories(borner PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)

install(DIRECTORY include/ DESTINATION include)
install(TARGETS borner EXPORT export_vitesse
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib)

if(BUILD_TESTING)
  # les tests de qualité : style, copyright, analyse statique (ament_lint_common)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
  # les tests unitaires en C++
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_borner test/test_borner.cpp)
  target_link_libraries(test_borner borner)
endif()

ament_export_targets(export_vitesse)
ament_package()

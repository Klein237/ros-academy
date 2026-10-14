# syntax=docker/dockerfile:1
# Image du robot de livraison, en deux étapes : on compile dans une image complète,
# puis on ne garde que le résultat dans une image d'exécution plus petite.

# --- Étape 1 : compilation
FROM ros:jazzy-ros-base AS build
WORKDIR /ws
# Les dépendances d'abord : cette couche reste en cache tant que package.xml ne change pas
COPY src/livraison_bringup/package.xml src/livraison_bringup/package.xml
RUN apt-get update \
 && rosdep install --from-paths src --ignore-src -y \
 && rm -rf /var/lib/apt/lists/*
# Puis le code, qui change souvent
COPY src src
RUN . /opt/ros/$ROS_DISTRO/setup.sh && colcon build

# --- Étape 2 : exécution, sans les outils de compilation
FROM ros:jazzy-ros-core AS robot
COPY --from=build /ws/install /ws/install
COPY --chmod=755 docker/ros_entrypoint.sh /ros_entrypoint.sh
RUN useradd --create-home robot
USER robot
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["ros2", "launch", "livraison_bringup", "robot.launch.py"]

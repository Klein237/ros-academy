#!/bin/bash
# Point d'entrée du conteneur : prépare l'environnement ROS, puis lance la commande (CMD).
set -e
source "/opt/ros/$ROS_DISTRO/setup.bash"
exec "$@"

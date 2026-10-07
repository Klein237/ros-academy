#!/usr/bin/env bash
# Démarre le robot de livraison avec sa configuration (config/robot.env).
cd "$(dirname "$0")"
if [ ! -f config/robot.env ]; then
  echo "Erreur : config/robot.env introuvable." >&2
  echo "Créez-le à partir de config/robot.env.exemple, puis adaptez-le." >&2
  exit 1
fi
source config/robot.env
if [ -z "${ROBOT_NOM:-}" ] || [ "$ROBOT_NOM" = "a-changer" ]; then
  echo "Erreur : indiquez le nom du robot dans config/robot.env (ligne ROBOT_NOM=...)." >&2
  exit 1
fi
echo "Robot $ROBOT_NOM prêt (domaine ROS ${ROS_DOMAIN_ID:-0})."

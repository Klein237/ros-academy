#!/usr/bin/env bash
# Code de sortie 0 = exercice réussi. Le texte affiché est montré à l'étudiant.
# Pour lancer des nœuds : setsid ros2 run … &, et un ROS_DOMAIN_ID dédié.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if [ "$(cat etat.txt)" != "corrigé" ]; then
  echo "Le problème est toujours là."
  exit 1
fi
echo "Bravo, c'est corrigé."

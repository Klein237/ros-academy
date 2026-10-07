#!/usr/bin/env bash
# Vérifie que ./demarrer_robot.sh démarre le robot livreur-01, sans que le script ait été modifié.
cd "$WS" || { echo "Dossier introuvable : $WS"; exit 1; }
if [ ! -f demarrer_robot.sh ]; then
  echo "demarrer_robot.sh a disparu de $WS : relancez « Commencer l'exercice »."
  exit 1
fi
if ! cmp -s demarrer_robot.sh "$EXERCICE/depart/demarrer_robot.sh"; then
  echo "demarrer_robot.sh a été modifié : la panne n'est pas dans le script. Remettez-le d'origine (« Commencer l'exercice »)."
  exit 1
fi
if [ ! -x demarrer_robot.sh ]; then
  echo "./demarrer_robot.sh : Permission denied. Le script n'a pas le droit d'exécution (regardez ls -l)."
  exit 1
fi
out=$(timeout 10 ./demarrer_robot.sh 2>&1)
code=$?
echo "$out"
if [ "$code" -ne 0 ] || ! grep -q "^Robot livreur-01 prêt" <<<"$out"; then
  echo "Le script ne démarre pas encore le robot livreur-01."
  exit 1
fi
echo "Le robot livreur-01 démarre."

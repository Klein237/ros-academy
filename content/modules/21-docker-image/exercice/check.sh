#!/usr/bin/env bash
# Simule « docker run livraison:dev » : le point d'entrée et la commande de l'image, dans un
# environnement neuf (le lab n'a pas Docker ; voir simuler_conteneur.py).
cd "$WS" || { echo "Dossier introuvable : $WS"; exit 1; }
for f in Dockerfile docker/ros_entrypoint.sh src/livraison_bringup/package.xml; do
  if [ ! -f "$f" ]; then
    echo "$f a disparu de $WS : relancez « Commencer l'exercice »."
    exit 1
  fi
done
# l'étape « build » de l'image : colcon build dans le workspace
if ! colcon build > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation du workspace échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
python3 "$EXERCICE/simuler_conteneur.py" "$WS"

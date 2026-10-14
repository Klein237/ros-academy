#!/usr/bin/env bash
# Simule « docker compose up » : chaque service lancé avec sa commande et ses variables
# (le lab n'a pas Docker ; voir simuler_compose.py).
cd "$WS" || { echo "Dossier introuvable : $WS"; exit 1; }
for f in compose.yaml src/livraison_bringup/package.xml; do
  if [ ! -f "$f" ]; then
    echo "$f a disparu de $WS : relancez « Commencer l'exercice »."
    exit 1
  fi
done
if [ ! -f install/setup.bash ] && ! colcon build > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation du workspace échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
python3 "$EXERCICE/simuler_compose.py" "$WS"

#!/usr/bin/env bash
# 1. Votre detection.py, rejouée sur l'enregistrement de l'allée 3 : arrêt pendant que la personne
#    traverse (de 4 à 6 s), et seulement à ce moment-là.
# 2. Vos tests : ils passent sur votre correction, et échouent sur la version d'origine de detection.py
#    (un test de non-régression empêche le bug de revenir).
# L'enregistrement est refabriqué ici, identique à celui de l'exercice : seul votre code est évalué.
PKG="$WS/src/arret_urgence"
ORIGINE="$EXERCICE/depart/src/arret_urgence/arret_urgence/detection.py"
[ -f "$PKG/arret_urgence/detection.py" ] || { echo "Fichier introuvable : $PKG/arret_urgence/detection.py"; exit 1; }
[ -d "$PKG/test" ] || { echo "Dossier de tests introuvable : $PKG/test"; exit 1; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
if ! python3 "$EXERCICE/fabriquer_bag.py" "$TMP/allee3" > "$TMP/bag.txt" 2>&1; then
  echo "Impossible de fabriquer l'enregistrement :"; tail -n 10 "$TMP/bag.txt"; exit 1
fi

if ! python3 - "$PKG/arret_urgence/detection.py" "$TMP/allee3" <<'PY'
import importlib.util
import math
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan

spec = importlib.util.spec_from_file_location("detection", sys.argv[1])
detection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detection)
lecteur = rosbag2_py.SequentialReader()
lecteur.open(rosbag2_py.StorageOptions(uri=sys.argv[2]), rosbag2_py.ConverterOptions("cdr", "cdr"))
i, erreurs = 0, []
while lecteur.has_next():
    _, donnees, _ = lecteur.read_next()
    scan = deserialize_message(donnees, LaserScan)
    attendu = 40 <= i < 60
    obtenu = bool(detection.obstacle_proche(scan.ranges, scan.range_min, scan.range_max, 0.5))
    if obtenu != attendu:
        proche = min(scan.ranges)
        detail = f"mesure la plus courte : {proche} m" if math.isfinite(proche) else "aucune mesure finie"
        erreurs.append(f"t = {i / 10:.1f} s : {'arrêt' if obtenu else 'aucun arrêt'} ({detail}, "
                       f"mesures valides entre {scan.range_min} et {scan.range_max} m)")
    i += 1
if erreurs:
    print(f"Rejouée sur l'allée 3, votre décision se trompe sur {len(erreurs)} scan(s) sur {i} :")
    for e in erreurs[:5]:
        print("  - " + e)
    if len(erreurs) > 5:
        print(f"  … et {len(erreurs) - 5} autre(s)")
    sys.exit(1)
print(f"Rejouée sur l'allée 3 : arrêt pendant que la personne traverse, et seulement là ({i} scans).")
PY
then exit 1; fi

lancer() {  # $1 : detection.py à tester ; code de pytest sur vos tests
  rm -rf "$TMP/pkg" && mkdir -p "$TMP/pkg/arret_urgence"
  cp "$1" "$TMP/pkg/arret_urgence/detection.py" && : > "$TMP/pkg/arret_urgence/__init__.py"
  cp -r "$PKG/test" "$TMP/pkg/test"
  rm -rf "$TMP/pkg/test/donnees/allee3" && mkdir -p "$TMP/pkg/test/donnees" && cp -r "$TMP/allee3" "$TMP/pkg/test/donnees/allee3"
  (cd "$TMP/pkg" && PYTHONPATH="$TMP/pkg:${PYTHONPATH:-}" timeout 120 python3 -m pytest -q -p no:cacheprovider test > "$TMP/sortie.txt" 2>&1)
}

if ! lancer "$PKG/arret_urgence/detection.py"; then
  echo "Vos tests échouent sur votre correction :"
  tail -n 25 "$TMP/sortie.txt"
  exit 1
fi
if lancer "$ORIGINE"; then
  echo "Vos tests passent aussi sur la version d'origine de detection.py, celle qui arrêtait le robot sans raison :"
  echo "ajoutez un test de non-régression qui échoue avec le bug, par exemple en rejouant l'allée 3."
  exit 1
fi
echo "Vos tests passent sur la correction et attrapent le bug d'origine : il ne reviendra pas."

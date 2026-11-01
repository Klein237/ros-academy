#!/usr/bin/env bash
# Vos tests d'intégration doivent passer sur le nœud correct, et échouer sur chacune de cinq versions
# buggées du nœud (des « mutants ») : c'est la preuve qu'ils attrapent les bugs. Le nœud utilisé est
# celui du départ de l'exercice : seuls vos tests sont évalués.
TESTS="$WS/src/limiteur/test"
REF="$EXERCICE/depart/src/limiteur"
[ -d "$TESTS" ] || { echo "Dossier de tests introuvable : $TESTS"; exit 1; }
mapfile -t FICHIERS < <(cd "$TESTS" && grep -l "generate_test_description" test_*.py 2>/dev/null)
if [ ${#FICHIERS[@]} -eq 0 ]; then
  echo "Aucun test launch_testing (avec generate_test_description) dans $TESTS."
  exit 1
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
mkdir -p "$TMP/ws/src"
cp -r "$REF" "$TMP/ws/src/limiteur"
rm -rf "$TMP/ws/src/limiteur/test"
cp -r "$TESTS" "$TMP/ws/src/limiteur/test"
NOEUD="$TMP/ws/src/limiteur/limiteur/noeud.py"

lancer() {  # $1 : noeud.py à tester ; code non nul si un test échoue
  cp "$1" "$NOEUD"
  (
    cd "$TMP/ws" || exit 2
    rm -rf build install log
    colcon build > "$TMP/build.txt" 2>&1 || { echo "La compilation échoue."; tail -n 20 "$TMP/build.txt"; exit 2; }
    source install/setup.bash
    for f in "${FICHIERS[@]}"; do
      timeout 120 launch_test "src/limiteur/test/$f" || exit 1
    done
  ) > "$TMP/sortie.txt" 2>&1
}

if ! lancer "$REF/limiteur/noeud.py"; then
  echo "Vos tests échouent sur le nœud correct : un test doit décrire le comportement attendu."
  grep -E "^(FAIL|ERROR|AssertionError|    self\.|.*Error:)" "$TMP/sortie.txt" | head -n 20
  tail -n 15 "$TMP/sortie.txt"
  exit 1
fi

python3 - "$REF/limiteur/noeud.py" "$TMP" <<'PY'
import sys
ref, tmp = sys.argv[1], sys.argv[2]
src = open(ref, encoding="utf-8").read()
MUTANTS = {
    "topic": ("publie sur /cmd_vel_limite au lieu de /cmd_vel",
              [("create_publisher(Twist, '/cmd_vel', 10)", "create_publisher(Twist, '/cmd_vel_limite', 10)")]),
    "parametre": ("paramètre vitesse_max ignoré (toujours 0.5)",
                  [("self.vitesse_max = self.declare_parameter('vitesse_max', 0.5).value",
                    "self.declare_parameter('vitesse_max', 0.5)\n        self.vitesse_max = 0.5")]),
    "marche-arriere": ("marche arrière jamais bornée", [("return max(-maximum, min(valeur, maximum))", "return min(valeur, maximum)")]),
    "rotation": ("vitesse de rotation perdue", [("limite.angular.z = commande.angular.z", "limite.angular.z = 0.0")]),
    "arret": ("le nœud quitte avec le code 1 à l'arrêt",
              [("        rclpy.try_shutdown()\n", "        rclpy.try_shutdown()\n        raise SystemExit(1)\n")]),
}
with open(f"{tmp}/mutants.txt", "w", encoding="utf-8") as liste:
    for nom, (description, remplacements) in MUTANTS.items():
        m = src
        for avant, apres in remplacements:
            assert avant in m, f"mutant {nom} : motif introuvable"
            m = m.replace(avant, apres, 1)
        open(f"{tmp}/{nom}.py", "w", encoding="utf-8").write(m)
        liste.write(f"{nom}\t{description}\n")
PY

survivants=()
total=0
while IFS=$'\t' read -r nom description; do
  total=$((total + 1))
  if lancer "$TMP/$nom.py"; then survivants+=("$description"); fi
done < "$TMP/mutants.txt"

attrapes=$((total - ${#survivants[@]}))
if [ ${#survivants[@]} -gt 0 ]; then
  echo "Vos tests passent sur le nœud correct et attrapent $attrapes bug(s) sur $total."
  echo "Ces versions buggées du nœud passent encore tous vos tests :"
  for s in "${survivants[@]}"; do echo "  - $s"; done
  exit 1
fi
echo "Vos tests passent sur le nœud correct et attrapent les $total versions buggées du nœud."

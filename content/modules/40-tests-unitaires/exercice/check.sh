#!/usr/bin/env bash
# Vos tests doivent passer sur le calcul correct, et échouer sur chacune de six versions buggées
# (des « mutants ») : c'est la preuve qu'ils attrapent les bugs. Le calcul utilisé est celui du
# départ de l'exercice : seuls vos tests sont évalués.
TESTS="$WS/src/odometrie/test"
REF="$EXERCICE/depart/src/odometrie/odometrie/calcul.py"
[ -d "$TESTS" ] || { echo "Dossier de tests introuvable : $TESTS"; exit 1; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

lancer() {  # $1 : calcul.py à tester ; code de pytest
  rm -rf "$TMP/pkg" && mkdir -p "$TMP/pkg/odometrie"
  cp "$1" "$TMP/pkg/odometrie/calcul.py" && : > "$TMP/pkg/odometrie/__init__.py"
  cp -r "$TESTS" "$TMP/pkg/test"
  (cd "$TMP/pkg" && PYTHONPATH="$TMP/pkg" timeout 60 python3 -m pytest -q -p no:cacheprovider test > "$TMP/sortie.txt" 2>&1)
}

if ! lancer "$REF"; then
  echo "Vos tests échouent sur le calcul correct : un test doit décrire le comportement attendu."
  tail -n 25 "$TMP/sortie.txt"
  exit 1
fi
n=$(grep -o "[0-9]* passed" "$TMP/sortie.txt" | grep -o "[0-9]*")

python3 - "$REF" "$TMP" <<'PY'
import sys
ref, tmp = sys.argv[1], sys.argv[2]
src = open(ref, encoding="utf-8").read()
MUTANTS = {
    "cos-sin": ("cos et sin inversés dans integrer",
                [("x += v * math.cos(theta) * dt", "x += v * math.sin(theta) * dt"),
                 ("y += v * math.sin(theta) * dt", "y += v * math.cos(theta) * dt")]),
    "dt": ("dt oublié pour l'angle", [("normaliser(theta + w * dt)", "normaliser(theta + w)")]),
    "normalisation": ("angle jamais normalisé", [("theta = normaliser(theta + w * dt)", "theta = theta + w * dt")]),
    "borne": ("normaliser renvoie -pi au lieu de pi", [("if angle <= 0:", "if angle < 0:")]),
    "roues": ("roues gauche et droite inversées",
              [("return (v - w * entraxe / 2, v + w * entraxe / 2)", "return (v + w * entraxe / 2, v - w * entraxe / 2)")]),
    "entraxe": ("entraxe entier au lieu de sa moitié",
                [("return (v - w * entraxe / 2, v + w * entraxe / 2)", "return (v - w * entraxe, v + w * entraxe)")]),
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
  echo "Vos $n test(s) passent sur le calcul correct et attrapent $attrapes bug(s) sur $total."
  echo "Ces versions buggées passent encore tous vos tests :"
  for s in "${survivants[@]}"; do echo "  - $s"; done
  exit 1
fi
echo "Vos $n tests passent sur le calcul correct et attrapent les $total versions buggées."

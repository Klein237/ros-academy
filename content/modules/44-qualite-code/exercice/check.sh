#!/usr/bin/env bash
# colcon test doit être vert sur le package vitesse, avec tous ses tests :
#   - les tests de qualité d'ament_lint_common (cpplint, uncrustify, copyright, lint_cmake, xmllint…) ;
#   - le test unitaire test_borner, avec ses trois cas, sans test retiré.
# Désactiver un linter ou un test ne compte pas : la vérification s'assure qu'ils ont tous tourné.
PKG="$WS/src/vitesse"
[ -f "$PKG/CMakeLists.txt" ] || { echo "Package introuvable : $PKG"; exit 1; }
if ! grep -q "ament_lint_auto_find_test_dependencies" "$PKG/CMakeLists.txt"; then
  echo "CMakeLists.txt n'appelle plus ament_lint_auto_find_test_dependencies() : les tests de qualité ne tournent plus."
  exit 1
fi
if grep -nE "_FOUND[[:space:]]+TRUE|AMENT_LINT_AUTO_EXCLUDE|AMENT_LINT_AUTO_FILE_EXCLUDE|ADDITIONAL_EXCLUDE" "$PKG/CMakeLists.txt"; then
  echo "CMakeLists.txt désactive ou contourne un linter (ligne ci-dessus) : corrigez le code plutôt que le linter."
  exit 1
fi
if grep -rnE "NOLINT|INDENT-OFF|\*INDENT-OFF\*" "$PKG/src" "$PKG/include" "$PKG/test" 2>/dev/null; then
  echo "Le code fait taire un linter (ligne ci-dessus) : corrigez plutôt ce qu'il signale."
  exit 1
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/ws/src"
cp -r "$PKG" "$TMP/ws/src/vitesse"
cd "$TMP/ws"
if ! colcon build > "$TMP/build.txt" 2>&1; then
  echo "La compilation échoue :"; grep -E "error|Error" "$TMP/build.txt" | head -n 15; exit 1
fi
colcon test --packages-select vitesse > "$TMP/test.txt" 2>&1 || true
RES="$TMP/ws/build/vitesse/test_results/vitesse"
manquants=()
for nom in cpplint uncrustify copyright lint_cmake xmllint cppcheck test_borner; do
  ls "$RES"/"$nom".*xml > /dev/null 2>&1 || manquants+=("$nom")
done
if [ ${#manquants[@]} -gt 0 ]; then
  echo "Ces tests n'ont pas tourné : ${manquants[*]}. Ils doivent tous rester actifs."
  exit 1
fi
for cas in SousLaLimite MarcheAvant MarcheArriere; do
  if ! grep -q "name=\"$cas\"" "$RES"/test_borner.*xml; then
    echo "Le cas $cas de test_borner a disparu : un test qui dérange se corrige, il ne se supprime pas."
    exit 1
  fi
done
if ! colcon test-result --test-result-base build/vitesse > "$TMP/resultat.txt" 2>&1; then
  echo "colcon test est encore rouge :"
  colcon test-result --test-result-base build/vitesse --verbose 2>&1 | grep -vE "^$" | head -n 40
  exit 1
fi
echo "colcon test est vert : $(tail -n 1 "$TMP/resultat.txt")"
echo "Style, copyright, CMake, XML et test unitaire : la pull request peut passer en revue."

#!/usr/bin/env bash
# Rejoue le cours : colcon test est vert avec les linters et gtest, ament_uncrustify --reformat corrige le style.
set -e
colcon test --packages-select vitesse --event-handlers console_direct- > /dev/null
colcon test-result --test-result-base build/vitesse --verbose | tail -n 3
colcon test-result --test-result-base build/vitesse > /dev/null       # code non nul si un test a échoué
for nom in cpplint uncrustify copyright lint_cmake xmllint test_borner; do
  ls build/vitesse/test_results/vitesse/"$nom".*xml > /dev/null
done
ESSAI=src/vitesse/src/essai.cpp
{ sed -n 1,13p src/vitesse/src/borner.cpp; printf '\nint essai(int a,int b){ if(a>b){return a;} return b; }\n'; } > "$ESSAI"
if ament_uncrustify "$ESSAI" > /dev/null 2>&1; then echo "uncrustify accepte un fichier mal formaté"; exit 1; fi
ament_uncrustify --reformat "$ESSAI" > /dev/null 2>&1 || true
ament_uncrustify "$ESSAI" > /dev/null
rm "$ESSAI"
ament_cpplint src/vitesse > /dev/null
echo "linters, gtest et reformatage automatique : ok"

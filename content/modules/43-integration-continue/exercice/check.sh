#!/usr/bin/env bash
# Votre workflow .github/workflows/ci.yml :
#   1. se déclenche à chaque push sur main et à chaque pull request, et récupère le code ;
#   2. ses étapes « run », exécutées ici dans l'ordre, réussissent sur le code actuel ;
#   3. et échouent quand un test du package échoue : une CI verte doit vouloir dire « tests réussis ».
# Les étapes qui installent des dépendances (apt, rosdep) sont sautées : le lab n'a pas Internet,
# et tout est déjà installé.
WF="$WS/.github/workflows/ci.yml"
[ -f "$WF" ] || { echo "Workflow introuvable : $WF"; exit 1; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

python3 - "$WF" "$TMP" <<'PY' || exit 1
import sys
from pathlib import Path

import yaml

chemin, tmp = sys.argv[1], Path(sys.argv[2])
try:
    wf = yaml.safe_load(open(chemin, encoding="utf-8"))
except yaml.YAMLError as exc:
    print(f"ci.yml n'est pas un YAML valide : {exc}")
    sys.exit(1)
if not isinstance(wf, dict):
    print("ci.yml doit décrire un workflow : name, on, jobs.")
    sys.exit(1)
# PyYAML lit la clé « on » comme le booléen True (YAML 1.1)
declencheurs = wf.get("on", wf.get(True))
if isinstance(declencheurs, str):
    declencheurs = [declencheurs]
noms = set(declencheurs or [])
erreurs = []
if "pull_request" not in noms:
    erreurs.append("le workflow ne se déclenche pas sur les pull requests : une erreur n'est vue qu'une fois fusionnée dans main")
if "push" not in noms:
    erreurs.append("le workflow ne se déclenche plus sur les push")
jobs = wf.get("jobs") or {}
if not isinstance(jobs, dict) or not jobs:
    erreurs.append("aucun job dans jobs:")
etapes = []
for nom, job in (jobs.items() if isinstance(jobs, dict) else []):
    steps = (job or {}).get("steps") or []
    if not any(str(s.get("uses", "")).startswith("actions/checkout") for s in steps if isinstance(s, dict)):
        erreurs.append(f"le job {nom} ne récupère pas le code (actions/checkout) : il compilerait un dossier vide")
    etapes += [s for s in steps if isinstance(s, dict) and s.get("run")]
if erreurs:
    print("Le workflow a encore des défauts :")
    for e in erreurs:
        print("  - " + e)
    sys.exit(1)
gardees = []
for i, s in enumerate(etapes):
    script = str(s["run"])
    if any(mot in script for mot in ("apt-get", "apt ", "rosdep")):
        continue
    (tmp / f"etape-{len(gardees)}.sh").write_text(script, encoding="utf-8")
    gardees.append(s.get("name") or f"étape {i + 1}")
(tmp / "etapes.txt").write_text("\n".join(gardees) + "\n", encoding="utf-8")
if not gardees:
    print("Aucune étape « run » à exécuter en dehors des dépendances : le workflow ne compile ni ne teste rien.")
    sys.exit(1)
PY

executer() {  # $1 : copie du dépôt ; code non nul dès qu'une étape échoue (comme GitHub Actions)
  local i=0 nom
  while IFS= read -r nom; do
    if ! (cd "$1" && timeout 300 bash -e "$TMP/etape-$i.sh") > "$TMP/journal-$i.txt" 2>&1; then
      echo "$nom"
      return 1
    fi
    i=$((i + 1))
  done < "$TMP/etapes.txt"
}

copier() {  # copie propre du dépôt, sans les produits de compilation
  rm -rf "$1" && mkdir -p "$1"
  (cd "$WS" && tar --exclude=./build --exclude=./install --exclude=./log -cf - .) | (cd "$1" && tar -xf -)
}

copier "$TMP/sain"
if echec=$(executer "$TMP/sain"); then :; else
  echo "Sur le code actuel, dont tous les tests passent, l'étape « $echec » échoue :"
  i=$(grep -nxF "$echec" "$TMP/etapes.txt" | head -1 | cut -d: -f1)
  tail -n 15 "$TMP/journal-$((i - 1)).txt"
  exit 1
fi

copier "$TMP/casse"
PKG_TEST=$(find "$TMP/casse/src" -path "*/test" -type d | head -1)
[ -n "$PKG_TEST" ] || { echo "Aucun dossier test/ dans src/ : le package odometrie a-t-il été déplacé ?"; exit 1; }
cat > "$PKG_TEST/test_casse_par_la_verification.py" <<'PY'
def test_ce_test_echoue_expres():
    assert 1 + 1 == 3, "test cassé exprès par la vérification"
PY
if echec=$(executer "$TMP/casse"); then
  echo "Avec un test qui échoue dans le package, toutes les étapes de votre workflow réussissent :"
  echo "la CI serait verte alors qu'un test est rouge. Quelle commande fait échouer l'étape quand un test échoue ?"
  exit 1
fi
echo "Le workflow se déclenche sur les push et les pull requests, réussit sur le code actuel,"
echo "et échoue à l'étape « $echec » quand un test échoue : une CI verte veut dire « tests réussis »."

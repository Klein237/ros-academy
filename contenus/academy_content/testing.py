"""Tests d'un module dans un conteneur ros-lab jetable, sans réseau.

Étapes (celles de la spec) :
  1. setup.sh installe le workspace de l'exercice, avec le bug ;
  2. check.sh doit ÉCHOUER (le bug est bien là) ;
  3. solution/ est copiée par-dessus le workspace de l'exercice ;
  4. check.sh doit RÉUSSIR ;
  5. le lab guidé (lab/ + fichiers complets du cours) compile avec colcon,
     puis lab_test.sh (facultatif) vérifie que les nœuds démarrent.

Le module est copié dans le conteneur par une archive (pas de montage) :
cela marche aussi quand ce code tourne lui-même dans un conteneur.
"""

import io
import re
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

from .render import code_files

STEP_RE = re.compile(r"^::etape:: (\S+) (ok|echec)(?: (.*))?$")
STEP_LABELS = {
    "setup": "setup.sh installe l'exercice",
    "bug": "check.sh échoue tant que le bug est présent",
    "solution": "check.sh réussit avec solution/",
    "lab": "le lab guidé compile avec colcon",
    "lab_test": "les nœuds du lab guidé démarrent (lab_test.sh)",
}

# Exécuté par « bash -l » (environnement ROS chargé) en tant qu'etudiant.
SCRIPT = r"""
set -u
ID="$1"
M=/tmp/module
export EXERCICE="$HOME/.academy/$ID" WS="$HOME/ws/$ID-exercice" LAB="$HOME/ws/$ID"
ok() { echo "::etape:: $1 ok"; }
ko() { echo "::etape:: $1 echec ${2:-}"; exit 1; }
run() { (cd "$HOME" && timeout "${2:-300}" bash "$EXERCICE/$1"); }

mkdir -p "$EXERCICE"
cp -r "$M/exercice/." "$EXERCICE/"
rm -rf "$EXERCICE/solution" "$EXERCICE/explication.md"

echo "--- setup.sh"
run setup.sh 600 || ko setup "setup.sh a échoué"
ok setup

echo "--- check.sh (bug présent)"
if run check.sh; then ko bug "check.sh réussit alors que le bug est présent"; fi
ok bug

echo "--- check.sh (avec solution/)"
cp -r "$M/exercice/solution/." "$WS/"
run check.sh || ko solution "check.sh échoue avec la solution"
ok solution

echo "--- lab guidé"
mkdir -p "$LAB"
cp -r "$M/lab/." "$LAB/"
if [ -d "$M/.cours" ]; then cp -r "$M/.cours/." "$LAB/"; fi
if [ -d "$LAB/src" ]; then
  (cd "$LAB" && timeout 900 colcon build --event-handlers console_direct-) || ko lab "colcon build échoue"
fi
ok lab
if [ -f "$M/lab_test.sh" ]; then
  (cd "$LAB" && timeout 300 bash "$M/lab_test.sh") || ko lab_test "lab_test.sh échoue"
  ok lab_test
fi
echo "::fin::"
"""


@dataclass
class Etape:
    nom: str
    ok: bool
    detail: str = ""

    @property
    def libelle(self):
        return STEP_LABELS.get(self.nom, self.nom)


@dataclass
class Rapport:
    module: str
    ok: bool
    etapes: list[Etape] = field(default_factory=list)
    journal: str = ""

    def resume(self):
        lignes = [f"{'✔' if e.ok else '✘'} {e.libelle}" + (f" — {e.detail}" if e.detail else "") for e in self.etapes]
        if not self.ok and (not self.etapes or self.etapes[-1].ok):
            lignes.append("✘ tests interrompus (voir le journal)")
        return "\n".join(lignes)


def parse_output(module_id, output, exit_code):
    etapes = []
    for line in output.splitlines():
        m = STEP_RE.match(line.strip())
        if m:
            etapes.append(Etape(m.group(1), m.group(2) == "ok", (m.group(3) or "").strip()))
    finished = "::fin::" in output
    ok = exit_code == 0 and finished and all(e.ok for e in etapes)
    return Rapport(module=module_id, ok=ok, etapes=etapes, journal=output)


def module_archive(module_dir):
    """Archive tar du module sous tmp/module/, propriété d'etudiant (uid 1000).

    Les fichiers complets du cours (blocs ```lang fichier=…```) vont dans .cours/.
    """
    module_dir = Path(module_dir)
    buf = io.BytesIO()

    def add(name, data, mode=0o644):
        info = tarfile.TarInfo(f"tmp/module/{name}")
        info.size, info.mode, info.uid, info.gid = len(data), mode, 1000, 1000
        info.uname = info.gname = "etudiant"
        tar.addfile(info, io.BytesIO(data))

    with tarfile.open(fileobj=buf, mode="w") as tar:
        for path in sorted(module_dir.rglob("*")):
            if path.is_file() and not path.is_symlink():
                rel = path.relative_to(module_dir).as_posix()
                add(rel, path.read_bytes(), 0o755 if rel.endswith(".sh") else 0o644)
        index = module_dir / "index.md"
        if index.is_file():
            for rel, content in code_files(index.read_text(encoding="utf-8")).items():
                add(f".cours/{rel}", content.encode())
    buf.seek(0)
    return buf.getvalue()


def run_module_tests(module_dir, image="ros-lab:0.1.0", client=None, timeout=1200):
    """Lance les tests d'un module ; ne lève pas d'exception pour un échec de test."""
    import docker  # importé ici : inutile pour le site et les tests unitaires

    module_dir = Path(module_dir)
    module_id = module_dir.name
    client = client or docker.from_env()
    container = client.containers.create(
        image,
        command=["bash", "-lc", SCRIPT, "module-test", module_id],
        user="etudiant",
        network_mode="none",
        mem_limit="2g",
        nano_cpus=2_000_000_000,
        pids_limit=512,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        environment={"ROS_AUTOMATIC_DISCOVERY_RANGE": "LOCALHOST"},
    )
    try:
        container.put_archive("/", module_archive(module_dir))
        container.start()
        try:
            exit_code = container.wait(timeout=timeout)["StatusCode"]
        except Exception:  # noqa: BLE001 - délai dépassé ou démon injoignable
            container.kill()
            exit_code = -1
        output = container.logs(stdout=True, stderr=True).decode("utf-8", "replace")
    finally:
        container.remove(force=True)
    rapport = parse_output(module_id, output, exit_code)
    if exit_code == -1:
        rapport.journal += f"\n[délai de {timeout} s dépassé]"
    return rapport

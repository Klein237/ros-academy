"""Vérification d'un exercice hors du conteneur de l'étudiant.

Le check.sh officiel (version publiée du module) tourne dans un conteneur ros-lab
neuf, sans réseau, sur une copie du workspace de l'étudiant lue dans son volume
monté en lecture seule. L'étudiant ne contrôle ni le script ni l'environnement :
seul son workspace (sa solution) est évalué.
"""

import io
import re
import tarfile
import threading
from dataclasses import dataclass
from pathlib import Path

STUDENT_RE = re.compile(r"^u\d{1,12}$")
WORKSPACE_RE = re.compile(r"^ws/(?:[a-z0-9][a-z0-9-]{0,63}/)?[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
HIDDEN = ("solution/", "indices.md", "explication.md")
MAX_WORKSPACE_MB = 200
CHECK_TIMEOUT = 300
CODE_RE = re.compile(r"^::code:: (\d+)$", re.M)

# Exécuté par « bash -l » (environnement ROS chargé) en tant qu'etudiant.
SCRIPT = r"""
set -u
ID="$1"
# $4 : dossier du lab guidé (ws/<parcours>/<module>) ; avant le rangement par parcours, ws/<module>
SRC="/eleve/$4-exercice"
[ -d "$SRC" ] || SRC="/eleve/ws/$ID-exercice"
export EXERCICE="$HOME/.academy/$ID" WS="$HOME/$4-exercice"
if [ ! -d "$SRC" ]; then echo "::absent::"; exit 3; fi
SIZE=$(du -sm --exclude=build --exclude=install --exclude=log "$SRC" | cut -f1)
if [ "$SIZE" -gt "$2" ]; then echo "::trop-gros:: $SIZE"; exit 4; fi
mkdir -p "$EXERCICE" "$WS"
cp -r /tmp/exercice/. "$EXERCICE/"
# copie sans les produits de compilation : tout est recompilé depuis les sources
(cd "$SRC" && tar --exclude=./build --exclude=./install --exclude=./log -cf - .) | (cd "$WS" && tar -xf -)
cd "$HOME"
timeout "$3" bash "$EXERCICE/check.sh"
CODE=$?
echo "::code:: $CODE"
exit $CODE
"""


class InvalidStudent(ValueError):
    pass


class Busy(Exception):
    """Trop de vérifications en cours : réessayer dans un instant."""


@dataclass
class Resultat:
    ok: bool
    code: int
    journal: str

    def as_dict(self):
        return {"ok": self.ok, "code": self.code, "journal": self.journal}


def volume_name(student, parcours=""):
    """Volume personnel créé par le Hub : « ros-lab-home-<nom> », ou « …--<parcours> » pour le dossier
    d'un parcours (hub/rosacademy_hub/spawner.py)."""
    if not STUDENT_RE.fullmatch(student or ""):
        raise InvalidStudent(student)
    return f"ros-lab-home-{student}--{parcours}" if parcours else f"ros-lab-home-{student}"


def parcours_of(workspace):
    """ws/<parcours>/<module> → <parcours> ; "" pour un module rangé à l'ancienne (ws/<module>)."""
    parts = workspace.split("/")
    return parts[1] if len(parts) == 3 else ""


def exercise_archive(module_dir):
    """Fichiers publiés de l'exercice sous tmp/exercice/, sans solution, indices ni explication."""
    base = Path(module_dir) / "exercice"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(base).as_posix()
            if not path.is_file() or path.is_symlink() or rel.startswith(HIDDEN) or rel in HIDDEN:
                continue
            data = path.read_bytes()
            info = tarfile.TarInfo(f"tmp/exercice/{rel}")
            info.size, info.uid, info.gid = len(data), 1000, 1000
            info.mode = 0o755 if rel.endswith(".sh") else 0o644
            info.uname = info.gname = "etudiant"
            tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.getvalue()


def _journal(output, code):
    if "::absent::" in output:
        return "Aucun workspace d'exercice : cliquez d'abord sur « Commencer l'exercice »."
    if "::trop-gros::" in output:
        return f"Le workspace de l'exercice dépasse {MAX_WORKSPACE_MB} Mo : supprimez les gros fichiers inutiles."
    text = CODE_RE.sub("", output).strip()
    if code == 124:
        text += f"\n\nLa vérification a dépassé {CHECK_TIMEOUT // 60} minutes."
    return text[-4000:]


def verify_exercise(module_dir, module_id, student, image, client=None, slots=None, wait=60, timeout=420,
                    homes_dir=None, workspace=None):
    """Lance check.sh sur le workspace de l'étudiant ; ne lève que pour un nom invalide ou une surcharge.

    homes_dir : dossiers des étudiants à quota (LAB_HOMES_DIR, monté au même chemin dans Contenus) ;
    sinon, le volume Docker de l'étudiant.
    """
    workspace = workspace or f"ws/{module_id}"
    if not WORKSPACE_RE.fullmatch(workspace):
        raise ValueError(f"dossier de lab invalide : {workspace!r}")
    import docker  # importé ici : inutile pour le site et les tests unitaires

    client = client or docker.from_env()
    volume = _student_home(client, docker.errors.NotFound, student, parcours_of(workspace), homes_dir)
    if volume is None:
        return Resultat(False, 3, _journal("::absent::", 3))
    if slots is not None and not slots.acquire(timeout=wait):
        raise Busy()
    try:
        container = client.containers.create(
            image,
            command=["bash", "-lc", SCRIPT, "verification", module_id, str(MAX_WORKSPACE_MB), str(CHECK_TIMEOUT),
                     workspace],
            user="etudiant",
            network_mode="none",
            mem_limit="2g",
            nano_cpus=1_000_000_000,
            pids_limit=256,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            environment={"ROS_AUTOMATIC_DISCOVERY_RANGE": "LOCALHOST"},
            volumes={volume: {"bind": "/eleve", "mode": "ro"}},
            labels={"ros-academy.role": "verification", "ros-academy.etudiant": student},
        )
        try:
            container.put_archive("/", exercise_archive(module_dir))
            container.start()
            try:
                code = container.wait(timeout=timeout)["StatusCode"]
            except Exception:  # noqa: BLE001 - délai dépassé ou démon injoignable
                container.kill()
                code = 124
            output = container.logs(stdout=True, stderr=True).decode("utf-8", "replace")
        finally:
            container.remove(force=True, v=True)
    finally:
        if slots is not None:
            slots.release()
    return Resultat(code == 0 and "::code:: 0" in output, code, _journal(output, code))


def _student_home(client, not_found, student, parcours, homes_dir):
    """Dossier à monter : celui du parcours s'il existe, sinon l'ancien dossier commun (parcours pas
    encore rouvert depuis la séparation) ; None si rien n'existe (Docker créerait un dossier vide)."""
    if homes_dir:
        home = Path(homes_dir) / student
        candidates = ([home / ".parcours" / parcours] if parcours else []) + [home]
        for path in candidates:
            if path.is_dir() and not path.is_symlink() and not home.is_symlink():
                return str(path)
        return None
    for name in ([volume_name(student, parcours)] if parcours else []) + [volume_name(student)]:
        try:
            client.volumes.get(name)
            return name
        except not_found:
            continue
    return None


def make_slots(n):
    return threading.BoundedSemaphore(max(1, n))

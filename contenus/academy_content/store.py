"""Dépôt Git du contenu : l'administrateur édite `brouillon`, les étudiants voient `publie`.

    <racine>/depot    copie de travail de la branche brouillon (éditée par l'admin)
    <racine>/publie   copie de travail de la branche publie (lue par le site)

Chaque enregistrement est un commit sur `brouillon`. « Publier » valide le format,
teste les modules modifiés, puis avance `publie` jusqu'au commit testé.

La branche `plateforme` garde les versions successives des formations livrées avec le code (voir
sync_seed) : une mise à jour de la plateforme arrive dans le brouillon par une fusion Git.
"""

import io
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .model import MAX_FILE_BYTES, MODULE_ID_RE, PARCOURS_ID_RE, list_module_ids, validate_tree
from .render import safe_rel_path

log = logging.getLogger("contenus")
DRAFT, PUBLISHED = "brouillon", "publie"
# Formations livrées avec la plateforme (dossier content/ du dépôt), version après version : au démarrage,
# une nouvelle version est fusionnée dans le brouillon, sans écraser les modifications de l'administrateur.
PLATFORM = "plateforme"


class StoreError(Exception):
    """Erreur présentable à l'administrateur."""


@dataclass
class Commit:
    sha: str
    date: str
    message: str


@dataclass
class Publication:
    etat: str = "aucune"  # aucune | en_cours | ok | echec
    commit: str = ""
    debut: float = 0.0
    fin: float = 0.0
    erreurs: list = field(default_factory=list)  # erreurs de format
    rapports: list = field(default_factory=list)  # Rapport par module testé
    module_en_cours: str = ""


class ContentStore:
    def __init__(self, root, seed=None, remote=None, author_name="Administrateur", author_email="admin@ros-academy.local"):
        self.root = Path(root)
        self.draft_dir = self.root / "depot"
        self.published_dir = self.root / "publie"
        self.remote = remote
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": author_name, "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name, "GIT_COMMITTER_EMAIL": author_email,
        }
        self._lock = threading.RLock()
        self.publication = Publication()
        self.mise_a_jour = ""  # résultat de la dernière synchronisation avec les formations de la plateforme
        self._init(seed)
        try:
            self.sync_seed(seed)
        except (StoreError, subprocess.CalledProcessError) as exc:  # le site démarre quand même
            log.warning("Mise à jour des formations de la plateforme impossible : %s", exc)
            self.mise_a_jour = "erreur"

    # --- Git

    def _git(self, *args, cwd=None, check=True):
        r = subprocess.run(["git", *args], cwd=cwd or self.draft_dir, env=self.env,
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise StoreError(f"git {args[0]} : {r.stderr.strip() or r.stdout.strip()}")
        return r.stdout.strip()

    def _init(self, seed):
        if (self.draft_dir / ".git").exists():
            if not self.published_dir.exists():
                self._git("worktree", "add", str(self.published_dir), PUBLISHED)
            return
        self.root.mkdir(parents=True, exist_ok=True)
        if self.remote and self._remote_has_draft():
            self._git("clone", "--branch", DRAFT, self.remote, str(self.draft_dir), cwd=self.root)
            self._git("fetch", "origin", f"{PUBLISHED}:{PUBLISHED}", check=False)
            if not self._git("branch", "--list", PUBLISHED):
                self._git("branch", PUBLISHED)
        else:
            self.draft_dir.mkdir(parents=True)
            self._git("init", "--initial-branch", DRAFT)
            if seed and Path(seed).is_dir():
                shutil.copytree(seed, self.draft_dir, dirs_exist_ok=True)
            self._git("add", "-A")
            self._git("commit", "--allow-empty", "-m", "Contenu initial")
            self._git("branch", PUBLISHED)
            if self.remote:
                self._git("remote", "add", "origin", self.remote)
        self._git("config", "core.symlinks", "false")
        self._git("worktree", "add", str(self.published_dir), PUBLISHED)

    # --- Formations livrées avec la plateforme

    def _tree_of(self, folder):
        """Arbre Git du dossier `folder` (index temporaire : le brouillon n'est pas touché)."""
        with tempfile.TemporaryDirectory(prefix="index-") as tmp:
            env = {**self.env, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            subprocess.run(["git", "--work-tree", str(Path(folder).resolve()), "add", "-A", "."], cwd=self.draft_dir, env=env,
                           capture_output=True, check=True)
            return subprocess.run(["git", "write-tree"], cwd=self.draft_dir, env=env, capture_output=True,
                                  text=True, check=True).stdout.strip()

    def sync_seed(self, seed):
        """Fusionne dans le brouillon la version des formations livrée avec la plateforme, si elle a changé.

        Les fichiers que l'administrateur n'a pas touchés sont mis à jour ; ses modifications sont gardées.
        Si les deux ont modifié les mêmes lignes, rien n'est changé et `mise_a_jour` le signale. Quand le
        brouillon était publié tel quel, la nouvelle version est publiée aussi (elle est testée par la CI).
        """
        if not seed or not Path(seed).is_dir():
            return
        with self._lock:
            if not self._git("branch", "--list", PLATFORM):
                # Magasins créés avant cette branche : le premier commit est la copie initiale des formations
                root = self._git("rev-list", "--max-parents=0", DRAFT).splitlines()[-1]
                self._git("branch", PLATFORM, root)
            tree = self._tree_of(seed)
            if tree == self._git("rev-parse", f"{PLATFORM}^{{tree}}"):
                return
            commit = self._git("commit-tree", tree, "-p", PLATFORM, "-m", "Nouvelle version des formations de la plateforme")
            self._git("update-ref", f"refs/heads/{PLATFORM}", commit)
            if self._git("status", "--porcelain"):
                self.mise_a_jour = "conflit"
                return
            was_published = self.head(DRAFT) == self.head(PUBLISHED)
            merge = subprocess.run(["git", "merge", "--no-edit", "-m", "Intègre la nouvelle version des formations "
                                    "de la plateforme", PLATFORM], cwd=self.draft_dir, env=self.env,
                                   capture_output=True, text=True)
            if merge.returncode != 0:
                self._git("merge", "--abort", check=False)
                self.mise_a_jour = "conflit"
                return
            self.mise_a_jour = "a_publier"
            if was_published and not validate_tree(self.draft_dir):
                self._git("merge", "--ff-only", DRAFT, cwd=self.published_dir)
                self.mise_a_jour = "publiee"
            if self.remote:
                self._git("push", "origin", f"{DRAFT}:{DRAFT}", f"{PUBLISHED}:{PUBLISHED}", check=False)

    def _remote_has_draft(self):
        r = subprocess.run(["git", "ls-remote", "--heads", self.remote, DRAFT], env=self.env,
                           capture_output=True, text=True)
        return r.returncode == 0 and DRAFT in r.stdout

    def head(self, branch=DRAFT):
        return self._git("rev-parse", branch)

    # --- Chemins

    def module_dir(self, module_id, published=False):
        if not MODULE_ID_RE.fullmatch(module_id or ""):
            raise StoreError("identifiant de module invalide")
        return (self.published_dir if published else self.draft_dir) / "modules" / module_id

    def _module_path(self, module_id, rel):
        base = self.module_dir(module_id)
        rel = safe_rel_path(rel)
        if not rel:
            raise StoreError("chemin de fichier invalide")
        path = base / rel
        # Aucun composant ne doit être un lien symbolique (ni sortir du module).
        cur = base
        for part in Path(rel).parts:
            cur = cur / part
            if cur.is_symlink():
                raise StoreError("chemin de fichier invalide")
        if not path.resolve().is_relative_to(base.resolve()):
            raise StoreError("chemin de fichier invalide")
        return path

    # --- Lecture

    def module_ids(self):
        return list_module_ids(self.draft_dir)

    def list_files(self, module_id):
        base = self.module_dir(module_id)
        if not base.is_dir():
            raise StoreError("module introuvable")
        return sorted(
            p.relative_to(base).as_posix()
            for p in base.rglob("*")
            if p.is_file() and not p.is_symlink() and ".git" not in p.parts
        )

    def read_file(self, module_id, rel):
        path = self._module_path(module_id, rel)
        if not path.is_file():
            raise StoreError("fichier introuvable")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise StoreError("fichier de plus de 1 Mo")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise StoreError("fichier binaire : non modifiable dans l'éditeur") from None

    # --- Écriture (un commit par enregistrement)

    def _commit(self, message):
        self._git("add", "-A")
        if not self._git("status", "--porcelain"):
            return self.head()
        self._git("commit", "-m", message)
        return self.head()

    def write_file(self, module_id, rel, content):
        if not isinstance(content, str):
            raise StoreError("contenu texte attendu")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise StoreError("fichier de plus de 1 Mo")
        with self._lock:
            if not self.module_dir(module_id).is_dir():
                raise StoreError("module introuvable")
            path = self._module_path(module_id, rel)
            if path.is_dir():
                raise StoreError("un dossier porte ce nom")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return self._commit(f"Modifie modules/{module_id}/{rel}")

    def delete_file(self, module_id, rel):
        with self._lock:
            path = self._module_path(module_id, rel)
            if not path.is_file():
                raise StoreError("fichier introuvable")
            path.unlink()
            # remonte les dossiers devenus vides
            parent = path.parent
            base = self.module_dir(module_id)
            while parent != base and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
            return self._commit(f"Supprime modules/{module_id}/{rel}")

    def create_module(self, module_id, titre, template_dir):
        with self._lock:
            target = self.module_dir(module_id)
            if target.exists():
                raise StoreError("un module porte déjà cet identifiant")
            shutil.copytree(template_dir, target)
            index = target / "index.md"
            text = index.read_text(encoding="utf-8")
            index.write_text(text.replace("Nouveau module", titre.replace("\n", " ").strip() or "Nouveau module", 1),
                             encoding="utf-8")
            return self._commit(f"Crée le module {module_id}")

    def delete_module(self, module_id):
        with self._lock:
            target = self.module_dir(module_id)
            if not target.is_dir():
                raise StoreError("module introuvable")
            for pid in self.parcours_ids():
                data = self.read_parcours(pid)
                if any(m.get("id") == module_id for m in data.get("modules", [])):
                    raise StoreError(f"retirez d'abord le module du parcours « {data.get('titre', pid)} »")
            shutil.rmtree(target)
            return self._commit(f"Supprime le module {module_id}")

    def parcours_ids(self):
        d = self.draft_dir / "parcours"
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    def read_parcours(self, parcours_id):
        if not PARCOURS_ID_RE.fullmatch(parcours_id or ""):
            raise StoreError("identifiant de parcours invalide")
        path = self.draft_dir / "parcours" / parcours_id / "parcours.yaml"
        if not path.is_file():
            raise StoreError("parcours introuvable")
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def write_parcours(self, parcours_id, data):
        if not PARCOURS_ID_RE.fullmatch(parcours_id or ""):
            raise StoreError("identifiant de parcours invalide")
        with self._lock:
            path = self.draft_dir / "parcours" / parcours_id / "parcours.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            return self._commit(f"Modifie le parcours {parcours_id}")

    # --- Historique

    def history(self, limit=30):
        out = self._git("log", f"-{limit}", "--format=%H%x1f%cI%x1f%s", DRAFT)
        commits = []
        for line in out.splitlines():
            sha, date, message = line.split("\x1f", 2)
            commits.append(Commit(sha, date, message))
        return commits

    def restore(self, sha):
        """Remet le brouillon dans l'état d'un commit (nouveau commit, l'historique est conservé)."""
        with self._lock:
            if not all(c in "0123456789abcdef" for c in sha) or not 7 <= len(sha) <= 40:
                raise StoreError("version invalide")
            known = subprocess.run(["git", "merge-base", "--is-ancestor", sha, DRAFT],
                                   cwd=self.draft_dir, env=self.env, capture_output=True)
            if known.returncode != 0:
                raise StoreError("version inconnue")
            self._git("rm", "-r", "-q", "--ignore-unmatch", ".")
            self._git("checkout", sha, "--", ".")
            date = self._git("show", "-s", "--format=%cI", sha)
            return self._commit(f"Restaure la version du {date[:16].replace('T', ' ')}")

    def has_unpublished_changes(self):
        return self.head(DRAFT) != self.head(PUBLISHED)

    # --- Publication

    def publish(self, runner):
        """Valide, teste les modules modifiés puis avance `publie`. Bloquant (quelques minutes)."""
        with self._lock:
            if self.publication.etat == "en_cours":
                raise StoreError("une publication est déjà en cours")
            pub = Publication(etat="en_cours", commit=self.head(DRAFT), debut=time.time())
            self.publication = pub
        return self._run_publication(pub, runner)

    def publish_in_background(self, runner):
        """Lance la publication dans un thread ; l'état se lit dans self.publication."""
        with self._lock:
            if self.publication.etat == "en_cours":
                raise StoreError("une publication est déjà en cours")
            if not self.has_unpublished_changes():
                raise StoreError("rien à publier : le brouillon est identique à la version publiée")
            pub = Publication(etat="en_cours", commit=self.head(DRAFT), debut=time.time())
            self.publication = pub

        def run():
            try:
                self._run_publication(pub, runner)
            except Exception as exc:  # noqa: BLE001 - affiché à l'admin
                pub.erreurs.append(str(exc))
                self._finish(pub, ok=False)

        threading.Thread(target=run, daemon=True).start()
        return pub

    def changed_modules(self, sha=DRAFT):
        """Modules modifiés entre la version publiée et `sha`."""
        names = self._git("diff", "--name-only", PUBLISHED, sha)
        return sorted({n.split("/")[1] for n in names.splitlines() if n.startswith("modules/") and n.count("/") >= 2})

    def _snapshot(self, sha, dest):
        """Extrait le commit `sha` dans `dest` : les tests portent sur ce commit exact."""
        archive = subprocess.run(["git", "archive", "--format=tar", sha], cwd=self.draft_dir,
                                 env=self.env, capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(dest, filter="data")

    def _run_publication(self, pub, runner):
        with tempfile.TemporaryDirectory(prefix="publication-") as tmp:
            self._snapshot(pub.commit, tmp)
            pub.erreurs = [str(e) for e in validate_tree(tmp)]
            if pub.erreurs:
                return self._finish(pub, ok=False)
            existing = set(list_module_ids(tmp))
            for module_id in self.changed_modules(pub.commit):
                if module_id not in existing:
                    continue  # module supprimé : rien à tester
                pub.module_en_cours = module_id
                rapport = runner(Path(tmp) / "modules" / module_id)
                pub.rapports.append(rapport)
                if not rapport.ok:
                    return self._finish(pub, ok=False)
        with self._lock:
            self._git("merge", "--ff-only", pub.commit, cwd=self.published_dir)
            if self.remote:
                self._git("push", "origin", f"{DRAFT}:{DRAFT}", f"{PUBLISHED}:{PUBLISHED}", check=False)
        return self._finish(pub, ok=True)

    def _finish(self, pub, ok):
        pub.etat = "ok" if ok else "echec"
        pub.fin = time.time()
        pub.module_en_cours = ""
        return pub

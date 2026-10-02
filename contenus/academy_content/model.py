"""Format des formations : parcours, modules, QCM, exercices.

Arborescence d'un dépôt de contenu :

    parcours/<id>/parcours.yaml
    modules/<id>/index.md            en-tête YAML (titre, resume, duree) + cours
    modules/<id>/lab/                workspace de départ du lab guidé
    modules/<id>/qcm.yaml
    modules/<id>/exercice/{enonce.md, setup.sh, check.sh, indices.md, explication.md, depart/, solution/}
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

MODULE_ID_RE = re.compile(r"^[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
PARCOURS_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_FILE_BYTES = 1024 * 1024

REQUIRED_FILES = (
    "index.md",
    "qcm.yaml",
    "exercice/enonce.md",
    "exercice/setup.sh",
    "exercice/check.sh",
    "exercice/indices.md",
    "exercice/explication.md",
)
REQUIRED_DIRS = ("lab", "exercice/solution")


@dataclass(frozen=True)
class Erreur:
    fichier: str
    message: str

    def __str__(self):
        return f"{self.fichier} : {self.message}"


class ContentError(Exception):
    def __init__(self, erreurs):
        self.erreurs = list(erreurs)
        super().__init__("; ".join(str(e) for e in self.erreurs))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Choix(_Strict):
    texte: str = Field(min_length=1, max_length=500)
    correct: bool = False


class Question(_Strict):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    question: str = Field(min_length=1, max_length=1000)
    choix: list[Choix] = Field(min_length=2, max_length=6)
    explication: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _au_moins_une_bonne(self):
        if not any(c.correct for c in self.choix):
            raise ValueError("au moins un choix doit être correct")
        return self

    @property
    def bonnes(self):
        return {i for i, c in enumerate(self.choix) if c.correct}


class Qcm(_Strict):
    questions: list[Question] = Field(min_length=1, max_length=20)

    @field_validator("questions")
    @classmethod
    def _ids_uniques(cls, questions):
        ids = [q.id for q in questions]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError(f"identifiants de question en double : {', '.join(doublons)}")
        return questions


class EnTete(_Strict):
    titre: str = Field(min_length=1, max_length=120)
    resume: str = Field(default="", max_length=400)
    duree: str = Field(default="", max_length=40)


class ModuleRef(_Strict):
    id: str
    coef: float = Field(default=1.0, gt=0, le=10)


class ParcoursDef(_Strict):
    titre: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    modules: list[ModuleRef] = Field(min_length=1)

    @field_validator("modules")
    @classmethod
    def _modules_uniques(cls, modules):
        ids = [m.id for m in modules]
        if len(ids) != len(set(ids)):
            raise ValueError("un module apparaît deux fois dans le parcours")
        return modules


@dataclass
class Exercice:
    enonce: str
    indices: list[str]
    explication: str


@dataclass
class Module:
    id: str
    en_tete: EnTete
    cours: str
    qcm: Qcm
    exercice: Exercice
    lab_files: list[str] = field(default_factory=list)


@dataclass
class Parcours:
    id: str
    titre: str
    description: str
    modules: list[ModuleRef]


def _pydantic_errors(fichier, exc):
    out = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        out.append(Erreur(fichier, f"{where} : {msg}" if where else msg))
    return out


def parse_front_matter(text):
    """Sépare l'en-tête YAML (entre deux lignes « --- ») du corps Markdown."""
    if not text.startswith("---\n"):
        raise ValueError("en-tête YAML absent (le fichier doit commencer par ---)")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("en-tête YAML non terminé (ligne --- manquante)")
    meta = yaml.safe_load(text[4:end]) or {}
    if not isinstance(meta, dict):
        raise ValueError("l'en-tête YAML doit être un dictionnaire")
    return meta, text[end + 5:]


def parse_indices(text):
    """Trois indices, chacun sous un titre « ## Indice n »."""
    parts = re.split(r"^##[^\n]*\n", text, flags=re.M)
    indices = [p.strip() for p in parts[1:]]
    if len(indices) != 3 or not all(indices):
        raise ValueError("il faut exactement 3 indices, chacun sous un titre « ## Indice n »")
    return indices


def _read_text(path, rel, erreurs):
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            erreurs.append(Erreur(rel, "fichier de plus de 1 Mo"))
            return None
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        erreurs.append(Erreur(rel, "le fichier doit être du texte UTF-8"))
    except OSError as exc:
        erreurs.append(Erreur(rel, f"illisible ({exc.strerror})"))
    return None


def _read_yaml(path, rel, erreurs):
    text = _read_text(path, rel, erreurs)
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        ligne = f" (ligne {mark.line + 1})" if mark else ""
        erreurs.append(Erreur(rel, f"YAML invalide{ligne}"))
        return None


def module_files(module_dir):
    """Fichiers du module, chemins relatifs triés (sans dossiers cachés)."""
    return sorted(
        str(p.relative_to(module_dir))
        for p in module_dir.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(module_dir).parts)
    )


def load_module(root, module_id):
    """Charge et valide un module ; lève ContentError avec toutes les erreurs trouvées."""
    root = Path(root)
    base = f"modules/{module_id}"
    if not MODULE_ID_RE.fullmatch(module_id or ""):
        raise ContentError([Erreur(base, "identifiant invalide (ex. 03-service : deux chiffres, tiret, minuscules)")])
    module_dir = root / "modules" / module_id
    if not module_dir.is_dir():
        raise ContentError([Erreur(base, "module introuvable")])

    erreurs = []
    for p in module_dir.rglob("*"):
        if p.is_symlink():
            erreurs.append(Erreur(f"{base}/{p.relative_to(module_dir)}", "les liens symboliques sont interdits"))
    for rel in REQUIRED_FILES:
        if not (module_dir / rel).is_file():
            erreurs.append(Erreur(f"{base}/{rel}", "fichier obligatoire manquant"))
    for rel in REQUIRED_DIRS:
        d = module_dir / rel
        if not d.is_dir() or not any(f.is_file() for f in d.rglob("*")):
            erreurs.append(Erreur(f"{base}/{rel}/", "dossier obligatoire manquant ou vide"))
    if erreurs:
        raise ContentError(erreurs)

    en_tete, cours = None, ""
    text = _read_text(module_dir / "index.md", f"{base}/index.md", erreurs)
    if text is not None:
        try:
            meta, cours = parse_front_matter(text)
            en_tete = EnTete.model_validate(meta)
        except ValueError as exc:
            if isinstance(exc, ValidationError):
                erreurs += _pydantic_errors(f"{base}/index.md", exc)
            else:
                erreurs.append(Erreur(f"{base}/index.md", str(exc)))

    qcm = None
    avant = len(erreurs)
    data = _read_yaml(module_dir / "qcm.yaml", f"{base}/qcm.yaml", erreurs)
    if len(erreurs) == avant:
        try:
            qcm = Qcm.model_validate(data)
        except ValidationError as exc:
            erreurs += _pydantic_errors(f"{base}/qcm.yaml", exc)

    indices = []
    text = _read_text(module_dir / "exercice/indices.md", f"{base}/exercice/indices.md", erreurs)
    if text is not None:
        try:
            indices = parse_indices(text)
        except ValueError as exc:
            erreurs.append(Erreur(f"{base}/exercice/indices.md", str(exc)))

    enonce = _read_text(module_dir / "exercice/enonce.md", f"{base}/exercice/enonce.md", erreurs)
    explication = _read_text(module_dir / "exercice/explication.md", f"{base}/exercice/explication.md", erreurs)
    for script in ("setup.sh", "check.sh"):
        body = _read_text(module_dir / "exercice" / script, f"{base}/exercice/{script}", erreurs)
        if body is not None and not body.startswith("#!"):
            erreurs.append(Erreur(f"{base}/exercice/{script}", "le script doit commencer par #!/usr/bin/env bash"))

    if erreurs:
        raise ContentError(erreurs)
    lab_files = [f.removeprefix("lab/") for f in module_files(module_dir) if f.startswith("lab/")]
    return Module(
        id=module_id,
        en_tete=en_tete,
        cours=cours,
        qcm=qcm,
        exercice=Exercice(enonce=enonce, indices=indices, explication=explication),
        lab_files=lab_files,
    )


def load_parcours(root, parcours_id):
    root = Path(root)
    rel = f"parcours/{parcours_id}/parcours.yaml"
    if not PARCOURS_ID_RE.fullmatch(parcours_id or ""):
        raise ContentError([Erreur(f"parcours/{parcours_id}", "identifiant invalide")])
    erreurs = []
    path = root / rel
    if not path.is_file():
        raise ContentError([Erreur(rel, "fichier manquant")])
    data = _read_yaml(path, rel, erreurs)
    if erreurs:
        raise ContentError(erreurs)
    try:
        d = ParcoursDef.model_validate(data)
    except ValidationError as exc:
        raise ContentError(_pydantic_errors(rel, exc)) from None
    return Parcours(id=parcours_id, titre=d.titre, description=d.description, modules=d.modules)


def list_module_ids(root):
    d = Path(root) / "modules"
    return sorted(p.name for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")) if d.is_dir() else []


def list_parcours_ids(root):
    d = Path(root) / "parcours"
    return sorted(p.name for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")) if d.is_dir() else []


def validate_tree(root):
    """Toutes les erreurs du dépôt de contenu ; liste vide = publiable (hors tests des modules)."""
    erreurs = []
    modules_ok = set()
    for module_id in list_module_ids(root):
        try:
            load_module(root, module_id)
            modules_ok.add(module_id)
        except ContentError as exc:
            erreurs += exc.erreurs
    known = set(list_module_ids(root))
    for parcours_id in list_parcours_ids(root):
        try:
            parcours = load_parcours(root, parcours_id)
        except ContentError as exc:
            erreurs += exc.erreurs
            continue
        for ref in parcours.modules:
            if ref.id not in known:
                erreurs.append(Erreur(f"parcours/{parcours_id}/parcours.yaml", f"module inconnu : {ref.id}"))
    return erreurs

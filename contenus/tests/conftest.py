import shutil
from pathlib import Path

import pytest

REPO_CONTENT = Path(__file__).resolve().parents[2] / "content"

QCM = """\
questions:
  - id: q1
    question: Quelle commande compile un workspace ?
    choix:
      - texte: colcon build
        correct: true
      - texte: catkin_make
    explication: colcon est l'outil de construction de ROS 2.
  - id: q2
    question: Quels éléments sont des moyens de communication ?
    choix:
      - texte: topic
        correct: true
      - texte: service
        correct: true
      - texte: package
"""

INDICES = "## Indice 1\nRegardez setup.py.\n\n## Indice 2\nentry_points.\n\n## Indice 3\nAjoutez la ligne.\n"


def make_module(root, module_id="01-demo", **overrides):
    files = {
        "index.md": "---\ntitre: Démo\nresume: Un module de test\nduree: 10 min\n---\n# Cours\n\nTexte.\n",
        "qcm.yaml": QCM,
        "lab/README.md": "Workspace de départ\n",
        "exercice/enonce.md": "Le nœud ne démarre pas.\n",
        "exercice/setup.sh": "#!/usr/bin/env bash\nexit 0\n",
        "exercice/check.sh": "#!/usr/bin/env bash\ntest -f \"$WS/ok\"\n",
        "exercice/indices.md": INDICES,
        "exercice/explication.md": "Il manquait le fichier ok.\n",
        "exercice/solution/ok": "1\n",
    }
    files.update(overrides)
    base = Path(root) / "modules" / module_id
    for rel, content in files.items():
        if content is None:
            continue
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return base


def make_parcours(root, parcours_id="demo", modules=("01-demo",)):
    p = Path(root) / "parcours" / parcours_id / "parcours.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["titre: Parcours démo", "description: Pour les tests", "modules:"]
    lines += [f"  - id: {m}\n    coef: 1" for m in modules]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def content(tmp_path):
    make_module(tmp_path)
    make_parcours(tmp_path)
    return tmp_path


@pytest.fixture
def real_content(tmp_path):
    dest = tmp_path / "content"
    shutil.copytree(REPO_CONTENT, dest)
    return dest

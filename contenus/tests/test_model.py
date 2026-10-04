import os

import pytest

from academy_content.model import (
    ContentError,
    load_module,
    load_parcours,
    parse_front_matter,
    parse_indices,
    validate_tree,
)
from conftest import make_module, make_parcours


def messages(exc_info):
    return [str(e) for e in exc_info.value.erreurs]


def test_valid_module_loads(content):
    m = load_module(content, "01-demo")
    assert m.en_tete.titre == "Démo"
    assert m.cours.startswith("# Cours")
    assert [q.id for q in m.qcm.questions] == ["q1", "q2"]
    assert m.qcm.questions[1].bonnes == {0, 1}
    assert len(m.exercice.indices) == 3
    assert m.lab_files == ["README.md"]
    assert validate_tree(content) == []


def test_parcours_loads(content):
    p = load_parcours(content, "demo")
    assert p.titre == "Parcours démo"
    assert [(r.id, r.coef) for r in p.modules] == [("01-demo", 1.0)]


@pytest.mark.parametrize("module_id", ["demo", "1-demo", "01_demo", "01-Demo", "../01-demo", ""])
def test_invalid_module_id(content, module_id):
    with pytest.raises(ContentError) as e:
        load_module(content, module_id)
    assert "identifiant invalide" in messages(e)[0]


@pytest.mark.parametrize("missing", ["index.md", "qcm.yaml", "exercice/check.sh", "exercice/indices.md"])
def test_missing_file_is_reported(tmp_path, missing):
    make_module(tmp_path, **{missing: None})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert f"modules/01-demo/{missing} : fichier obligatoire manquant" in messages(e)


def test_missing_solution_is_reported(tmp_path):
    make_module(tmp_path, **{"exercice/solution/ok": None})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert any("exercice/solution/" in m for m in messages(e))


def test_front_matter_errors(tmp_path):
    make_module(tmp_path, **{"index.md": "# Pas d'en-tête\n"})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert "en-tête YAML absent" in messages(e)[0]


def test_front_matter_unknown_key(tmp_path):
    make_module(tmp_path, **{"index.md": "---\ntitre: X\nauteur: moi\n---\nTexte\n"})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert any("auteur" in m for m in messages(e))


@pytest.mark.parametrize("qcm, expected", [
    ("questions: []\n", "questions"),
    ("questions:\n  - id: q1\n    question: quoi\n    choix:\n      - texte: a\n      - texte: b\n", "au moins un choix doit être correct"),
    ("questions:\n  - id: q1\n    question: quoi\n    choix:\n      - texte: a\n        correct: true\n", "choix"),
    ("questions:\n  - id: q1\n    question: a\n    choix: [{texte: a, correct: true}, {texte: b}]\n"
     "  - id: q1\n    question: b\n    choix: [{texte: a, correct: true}, {texte: b}]\n", "en double"),
    ("questions: [\n", "YAML invalide"),
])
def test_qcm_errors(tmp_path, qcm, expected):
    make_module(tmp_path, **{"qcm.yaml": qcm})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert any(expected in m for m in messages(e)), messages(e)


def test_indices_must_be_three(tmp_path):
    make_module(tmp_path, **{"exercice/indices.md": "## Indice 1\na\n## Indice 2\nb\n"})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert "exactement 3 indices" in messages(e)[0]


def test_script_needs_shebang(tmp_path):
    make_module(tmp_path, **{"exercice/check.sh": "exit 0\n"})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert "#!/usr/bin/env bash" in messages(e)[0]


def test_symlinks_are_refused(content):
    os.symlink("/etc/passwd", content / "modules/01-demo/lab/passwd")
    with pytest.raises(ContentError) as e:
        load_module(content, "01-demo")
    assert "liens symboliques" in messages(e)[0]


def test_parcours_with_unknown_module(tmp_path):
    make_module(tmp_path)
    make_parcours(tmp_path, modules=("01-demo", "02-absent"))
    assert [str(e) for e in validate_tree(tmp_path)] == [
        "parcours/demo/parcours.yaml : module inconnu : 02-absent"
    ]


def test_parse_helpers():
    meta, body = parse_front_matter("---\ntitre: A\n---\nCorps\n")
    assert meta == {"titre": "A"} and body == "Corps\n"
    assert parse_indices("intro\n## Indice 1\na\n## Indice 2\nb\n## Indice 3\nc\n") == ["a", "b", "c"]


def test_upcoming_parcours_needs_no_module(tmp_path):
    p = tmp_path / "parcours" / "nav2" / "parcours.yaml"
    p.parent.mkdir(parents=True)
    p.write_text("titre: Nav2\nstatut: bientot\nniveau: intermediaire\nprerequis: [ROS 2 Fondamentaux]\n", encoding="utf-8")
    parcours = load_parcours(tmp_path, "nav2")
    assert (parcours.statut, parcours.niveau, parcours.modules, parcours.prerequis) == ("bientot", "intermediaire", [], ["ROS 2 Fondamentaux"])
    p.write_text("titre: Nav2\n", encoding="utf-8")  # disponible par défaut : il faut des modules
    with pytest.raises(ContentError) as e:
        load_parcours(tmp_path, "nav2")
    assert "au moins un module" in messages(e)[0]
    p.write_text("titre: Nav2\nstatut: bientot\nniveau: expert\n", encoding="utf-8")
    with pytest.raises(ContentError):
        load_parcours(tmp_path, "nav2")


def test_repo_content_is_valid(real_content):
    assert validate_tree(real_content) == []
    assert load_parcours(real_content, "nav2").statut == "bientot"

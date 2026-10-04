import os
import time

import pytest

from academy_content.store import ContentStore, StoreError
from academy_content.testing import Rapport
from conftest import make_module, make_parcours


@pytest.fixture
def seed(tmp_path):
    root = tmp_path / "seed"
    make_module(root)
    make_parcours(root)
    return root


@pytest.fixture
def store(tmp_path, seed):
    return ContentStore(tmp_path / "store", seed=seed)


class FakeRunner:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def __call__(self, module_dir):
        self.calls.append((module_dir.name, (module_dir / "index.md").read_text()))
        return Rapport(module=module_dir.name, ok=self.ok)


def published_index(store):
    return (store.published_dir / "modules/01-demo/index.md").read_text()


def test_init_seeds_draft_and_published(store):
    assert store.module_ids() == ["01-demo"]
    assert published_index(store).startswith("---\ntitre: Démo")
    assert not store.has_unpublished_changes()
    # réouverture : rien n'est recréé
    again = ContentStore(store.root)
    assert again.head() == store.head()


def test_each_save_is_a_commit(store):
    before = len(store.history())
    store.write_file("01-demo", "index.md", "---\ntitre: Nouveau titre\n---\nTexte\n")
    assert len(store.history()) == before + 1
    assert store.history()[0].message == "Modifie modules/01-demo/index.md"
    assert store.changed_modules() == ["01-demo"]
    assert "Nouveau titre" not in published_index(store)  # pas encore publié


def test_publish_tests_changed_modules_then_advances_published(store):
    store.write_file("01-demo", "index.md", "---\ntitre: Nouveau titre\n---\nTexte\n")
    runner = FakeRunner(ok=True)
    pub = store.publish(runner)
    assert pub.etat == "ok", pub.erreurs
    assert [c[0] for c in runner.calls] == ["01-demo"]
    assert "Nouveau titre" in runner.calls[0][1]  # le commit testé est celui publié
    assert "Nouveau titre" in published_index(store)
    assert not store.has_unpublished_changes()


def test_failed_tests_leave_published_untouched(store):
    old = published_index(store)
    store.write_file("01-demo", "index.md", "---\ntitre: Cassé\n---\nTexte\n")
    pub = store.publish(FakeRunner(ok=False))
    assert pub.etat == "echec"
    assert published_index(store) == old
    assert store.has_unpublished_changes()


def test_invalid_format_is_not_published_nor_tested(store):
    store.write_file("01-demo", "qcm.yaml", "questions: []\n")
    runner = FakeRunner()
    pub = store.publish(runner)
    assert pub.etat == "echec" and runner.calls == []
    assert any("qcm.yaml" in e for e in pub.erreurs)


def test_publish_in_background_tests_a_snapshot(store):
    store.write_file("01-demo", "index.md", "---\ntitre: Version A\n---\nTexte\n")

    class SlowRunner(FakeRunner):
        def __call__(self, module_dir):
            # l'admin continue d'éditer pendant les tests
            store.write_file("01-demo", "index.md", "---\ntitre: Version B\n---\nTexte\n")
            return super().__call__(module_dir)

    runner = SlowRunner()
    pub = store.publish_in_background(runner)
    deadline = time.time() + 10
    while pub.etat == "en_cours" and time.time() < deadline:
        time.sleep(0.05)
    assert pub.etat == "ok"
    assert "Version A" in runner.calls[0][1]
    assert "Version A" in published_index(store)  # la version testée, pas la suivante
    assert store.has_unpublished_changes()


def test_nothing_to_publish(store):
    with pytest.raises(StoreError, match="rien à publier"):
        store.publish_in_background(FakeRunner())


@pytest.mark.parametrize("rel", ["../01-autre/index.md", "/etc/passwd", "lab/../../x", "", ".", "a//b", "lab/./x"])
def test_dangerous_paths_are_refused(store, rel):
    with pytest.raises(StoreError, match="chemin"):
        store.write_file("01-demo", rel, "x")


def test_symlink_inside_module_is_refused(store):
    os.symlink("/etc", store.module_dir("01-demo") / "lien")
    with pytest.raises(StoreError, match="chemin"):
        store.write_file("01-demo", "lien/passwd", "x")
    with pytest.raises(StoreError, match="chemin"):
        store.read_file("01-demo", "lien/passwd")


@pytest.mark.parametrize("module_id", ["../x", "01_demo", "x"])
def test_invalid_module_id_is_refused(store, module_id):
    with pytest.raises(StoreError, match="identifiant"):
        store.write_file(module_id, "index.md", "x")


def test_huge_file_is_refused(store):
    with pytest.raises(StoreError, match="1 Mo"):
        store.write_file("01-demo", "lab/gros.txt", "x" * (1024 * 1024 + 1))


def test_delete_file_and_empty_dirs(store):
    store.write_file("01-demo", "lab/src/a/b.py", "print(1)\n")
    store.delete_file("01-demo", "lab/src/a/b.py")
    assert not (store.module_dir("01-demo") / "lab/src").exists()
    assert "lab/README.md" in store.list_files("01-demo")


def test_restore_previous_version(store):
    original = store.read_file("01-demo", "index.md")
    first = store.history()[0].sha
    store.write_file("01-demo", "index.md", "---\ntitre: Raté\n---\n")
    store.restore(first)
    assert store.read_file("01-demo", "index.md") == original
    assert store.history()[0].message.startswith("Restaure la version du")
    with pytest.raises(StoreError):
        store.restore("deadbeef")


def test_create_and_delete_module(store, tmp_path):
    template = tmp_path / "tpl"
    make_module(tmp_path / "tplroot", "00-modele", **{"index.md": "---\ntitre: Nouveau module\n---\n"})
    template = tmp_path / "tplroot/modules/00-modele"
    store.create_module("02-suite", "La suite", template)
    assert store.read_file("02-suite", "index.md").startswith("---\ntitre: La suite")
    with pytest.raises(StoreError, match="déjà"):
        store.create_module("02-suite", "x", template)
    with pytest.raises(StoreError, match="retirez"):
        store.delete_module("01-demo")  # utilisé par un parcours
    store.delete_module("02-suite")
    assert store.module_ids() == ["01-demo"]


def test_parcours_roundtrip(store):
    data = store.read_parcours("demo")
    data["titre"] = "Renommé"
    store.write_parcours("demo", data)
    assert store.read_parcours("demo")["titre"] == "Renommé"


# --- Nouvelle version des formations livrées avec la plateforme

def new_seed_version(seed, text="Nouveau cours\n"):
    index = seed / "modules/01-demo/index.md"
    index.write_text(index.read_text().replace("# Cours", f"# Cours\n\n{text}"), encoding="utf-8")


def test_platform_update_reaches_untouched_store(store, seed):
    new_seed_version(seed)
    again = ContentStore(store.root, seed=seed)  # redémarrage du service avec le nouveau code
    assert again.mise_a_jour == "publiee"
    assert "Nouveau cours" in published_index(again) and not again.has_unpublished_changes()
    head = again.head()
    assert ContentStore(store.root, seed=seed).head() == head  # rien de neuf : rien ne bouge


def test_platform_update_keeps_admin_edits(store, seed):
    store.write_file("01-demo", "notes.md", "Mes notes\n")  # modification de l'administrateur, non publiée
    new_seed_version(seed)
    again = ContentStore(store.root, seed=seed)
    assert again.mise_a_jour == "a_publier"
    assert again.read_file("01-demo", "notes.md") == "Mes notes\n"
    assert "Nouveau cours" in again.read_file("01-demo", "index.md")
    assert "Nouveau cours" not in published_index(again)  # publiée avec les tests, par l'administrateur


def test_platform_update_conflict_changes_nothing(store, seed):
    text = store.read_file("01-demo", "index.md").replace("# Cours", "# Cours\n\nVersion de l'admin")
    store.write_file("01-demo", "index.md", text)
    head = store.head()
    new_seed_version(seed, "Version de la plateforme\n")
    again = ContentStore(store.root, seed=seed)
    assert again.mise_a_jour == "conflit" and again.head() == head
    assert "Version de l'admin" in again.read_file("01-demo", "index.md")


def test_store_created_before_platform_branch(store, seed):
    store._git("branch", "-D", "plateforme")
    new_seed_version(seed)
    assert "Nouveau cours" in published_index(ContentStore(store.root, seed=seed))

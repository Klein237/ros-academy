import time

import jwt
import pytest
from fastapi.testclient import TestClient

from academy_content.app import create_app
from academy_content.store import ContentStore
from academy_content.testing import Rapport
from conftest import make_module, make_parcours

SECRET = "s" * 40
HOST = "testserver"
ORIGIN = {"Origin": f"http://{HOST}"}


def token(role="admin", aud="ros-academy-admin", ttl=300, secret=SECRET):
    now = int(time.time())
    claims = {"sub": "klein", "aud": aud, "iat": now, "exp": now + ttl}
    if role:
        claims["role"] = role
    return jwt.encode(claims, secret, algorithm="HS256")


class Runner:
    def __init__(self, ok=True):
        self.ok = ok

    def __call__(self, module_dir):
        return Rapport(module=module_dir.name, ok=self.ok, journal="::fin::")


@pytest.fixture
def store(tmp_path):
    seed = tmp_path / "seed"
    make_module(seed, **{"index.md": "---\ntitre: Démo\nresume: R\nduree: 10 min\n---\n# Cours\n\n"
                                     "```python fichier=src/p/p/n.py\nprint(1)\n```\n\n```cpp\nint main(){}\n```\n"})
    make_parcours(seed)
    return ContentStore(tmp_path / "store", seed=seed)


@pytest.fixture
def client(store):
    return TestClient(create_app(store, Runner(), SECRET, cookie_secure=False))


@pytest.fixture
def admin(client):
    r = client.get("/admin/login", params={"token": token()}, follow_redirects=False)
    assert r.status_code == 303
    return client


# --- Site public

def test_public_pages(client):
    for path in ("/", "/parcours/demo/", "/modules/01-demo/"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    page = client.get("/modules/01-demo/").text
    assert "Ouvrir dans le lab" in page
    assert "/lab/?module=01-demo&amp;open=ws/01-demo/src/p/p/n.py" in page
    assert 'class="code-tabs"' in page  # python + cpp consécutifs
    assert "Quelle commande compile un workspace ?" in page


def test_answers_never_reach_the_browser(client):
    import re
    page = client.get("/modules/01-demo/").text
    # Les choix d'une question sont rendus à l'identique, au texte près : rien ne trahit la bonne.
    labels = re.findall(r'<label><input type="radio" name="q1"[^>]*> ([^<]*)</label>', page)
    assert labels == ["colcon build", "catkin_make"]
    shapes = {re.sub(r'value="\d+"', "", m) for m in re.findall(r'<label><input type="radio" name="q1"[^>]*>', page)}
    assert len(shapes) == 1
    assert "colcon est l'outil" not in page  # explication absente
    api = client.get("/api/contenus/modules/01-demo/qcm").json()
    assert api["questions"][0] == {"id": "q1", "question": "Quelle commande compile un workspace ?",
                                   "multiple": False, "choix": ["colcon build", "catkin_make"]}
    assert "correct" not in str(api) and "explication" not in str(api)
    assert api["questions"][1]["multiple"] is True


def test_qcm_correction(client):
    url = "/api/contenus/modules/01-demo/qcm"
    full = client.post(url, json={"reponses": {"q1": [0], "q2": [0, 1]}}).json()
    assert full["note"] == 20 and full["justes"] == 2
    assert full["questions"][0]["explication"].startswith("colcon")
    part = client.post(url, json={"reponses": {"q1": [1], "q2": [0]}}).json()
    assert part["note"] == 0
    assert part["questions"][0] == {"id": "q1", "juste": False, "explication": ""}
    assert client.post(url, json={"reponses": {"q1": [0]}}).json()["note"] == 10
    assert client.post(url, json={"reponses": {"q1": ["x"]}}).status_code == 422


def test_exercise_api_hides_solution_and_explanation(client):
    data = client.get("/api/contenus/modules/01-demo/exercice").json()
    paths = [f["path"] for f in data["files"]]
    assert "setup.sh" in paths and "check.sh" in paths
    assert not [p for p in paths if p.startswith("solution") or "explication" in p or "indices" in p]
    assert data["indices"] == 3
    assert "Regardez setup.py" in client.get("/api/contenus/modules/01-demo/indices/1").json()["html"]
    assert client.get("/api/contenus/modules/01-demo/indices/4").status_code == 404
    assert client.get("/api/contenus/modules/01-demo/lab").json()["files"][0]["path"] == "README.md"
    files = client.get("/api/contenus/modules/01-demo/cours-fichiers").json()["files"]
    assert files == [{"path": "src/p/p/n.py", "content": "print(1)\n"}]


def test_unknown_and_draft_only_modules_are_404(client, store, tmp_path):
    assert client.get("/modules/99-absent/").status_code == 404
    assert client.get("/api/contenus/modules/../etc").status_code == 404
    tpl = make_module(tmp_path / "tpl", "00-modele")
    store.create_module("02-brouillon", "Pas encore publié", tpl)
    assert client.get("/modules/02-brouillon/").status_code == 404
    assert client.get("/api/contenus/modules/02-brouillon/lab").status_code == 404


# --- Administration : accès

def test_admin_requires_login(client):
    assert client.get("/admin/").status_code == 401
    assert client.get("/admin/api/etat").json() == {"erreur": "Connexion requise"}


@pytest.mark.parametrize("bad", [
    token(role=None), token(role="etudiant"), token(aud="ros-lab"), token(ttl=-100),
    token(secret="x" * 40), token(ttl=7200), "pas-un-jwt", "",
])
def test_admin_login_refuses_bad_tokens(client, bad):
    r = client.get("/admin/login", params={"token": bad}, follow_redirects=False)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers


def test_admin_cookie_is_scoped_and_strict(client):
    r = client.get("/admin/login", params={"token": token()}, follow_redirects=False)
    cookie = r.headers["set-cookie"]
    assert "Path=/admin" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie


def test_admin_cookie_is_secure_by_default(store):
    c = TestClient(create_app(store, Runner(), SECRET))
    r = c.get("/admin/login", params={"token": token()}, follow_redirects=False)
    assert "Secure" in r.headers["set-cookie"]


def test_admin_writes_need_same_origin(admin):
    url = "/admin/api/modules/01-demo/fichier?chemin=index.md"
    body = {"content": "---\ntitre: X\n---\n"}
    assert admin.put(url, json=body).status_code == 403
    assert admin.put(url, json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    assert admin.put(url, json=body, headers=ORIGIN).status_code == 200


def test_forged_session_cookie_is_refused(client):
    client.cookies.set("academy_admin", "faux", path="/admin")
    assert client.get("/admin/api/etat").status_code == 401


# --- Administration : édition et publication

def test_edit_preview_and_publish(admin):
    page = admin.get("/admin/modules/01-demo/")
    assert page.status_code == 200
    files = admin.get("/admin/api/modules/01-demo/fichiers").json()
    assert "exercice/solution/ok" in files["fichiers"] and files["erreurs"] == []
    r = admin.put("/admin/api/modules/01-demo/fichier?chemin=index.md", headers=ORIGIN,
                  json={"content": "---\ntitre: Titre modifié\n---\n# Nouveau cours\n"})
    assert r.json()["erreurs"] == []
    assert "Titre modifié" in admin.get("/admin/apercu/modules/01-demo/").text
    assert "Titre modifié" not in admin.get("/modules/01-demo/").text  # pas encore publié
    etat = admin.get("/admin/api/etat").json()
    assert etat["a_publier"] and etat["modules"][0]["modifie"]
    assert admin.post("/admin/api/publication", headers=ORIGIN).json()["etat"] == "en_cours"
    deadline = time.time() + 10
    while admin.get("/admin/api/publication").json()["etat"] == "en_cours" and time.time() < deadline:
        time.sleep(0.05)
    assert admin.get("/admin/api/publication").json()["etat"] == "ok"
    assert "Titre modifié" in admin.get("/modules/01-demo/").text


def test_failed_publication_keeps_students_on_old_version(store):
    c = TestClient(create_app(store, Runner(ok=False), SECRET, cookie_secure=False))
    c.get("/admin/login", params={"token": token()})
    c.put("/admin/api/modules/01-demo/fichier?chemin=index.md", headers=ORIGIN,
          json={"content": "---\ntitre: Cassé\n---\n"})
    c.post("/admin/api/publication", headers=ORIGIN)
    deadline = time.time() + 10
    while c.get("/admin/api/publication").json()["etat"] == "en_cours" and time.time() < deadline:
        time.sleep(0.05)
    pub = c.get("/admin/api/publication").json()
    assert pub["etat"] == "echec" and pub["rapports"][0]["ok"] is False
    assert "Cassé" not in c.get("/modules/01-demo/").text


def test_invalid_content_is_saved_but_flagged(admin):
    r = admin.put("/admin/api/modules/01-demo/fichier?chemin=qcm.yaml", headers=ORIGIN, json={"content": "questions: [\n"})
    assert r.status_code == 200
    assert any("qcm.yaml" in e for e in r.json()["erreurs"])


def test_qcm_form_roundtrip_and_validation(admin):
    data = admin.get("/admin/api/modules/01-demo/qcm").json()
    data["questions"][0]["question"] = "Nouvelle question ?"
    assert admin.put("/admin/api/modules/01-demo/qcm", headers=ORIGIN, json=data).status_code == 200
    assert admin.get("/admin/api/modules/01-demo/qcm").json()["questions"][0]["question"] == "Nouvelle question ?"
    data["questions"][0]["choix"] = [{"texte": "a", "correct": False}, {"texte": "b", "correct": False}]
    r = admin.put("/admin/api/modules/01-demo/qcm", headers=ORIGIN, json=data)
    assert r.status_code == 400 and "au moins un choix" in r.json()["erreur"]


def test_dangerous_paths_from_editor(admin):
    for chemin in ("../02-autre/index.md", "/etc/passwd", "lab/../../x"):
        r = admin.put("/admin/api/modules/01-demo/fichier", params={"chemin": chemin}, headers=ORIGIN, json={"content": "x"})
        assert r.status_code == 400, chemin


def test_create_module_from_template(admin):
    r = admin.post("/admin/api/modules", headers=ORIGIN, json={"id": "02-parametres", "titre": "Les paramètres"})
    assert r.status_code == 200
    files = admin.get("/admin/api/modules/02-parametres/fichiers").json()
    assert files["erreurs"] == [] and "exercice/check.sh" in files["fichiers"]
    assert admin.get("/admin/api/modules/02-parametres/fichier", params={"chemin": "index.md"}).json()["contenu"].startswith("---\ntitre: Les paramètres")
    assert admin.post("/admin/api/modules", headers=ORIGIN, json={"id": "parametres", "titre": "x"}).status_code == 400


def test_parcours_edit_validates_modules(admin):
    ok = {"titre": "Parcours", "description": "", "modules": [{"id": "01-demo", "coef": 2}]}
    assert admin.put("/admin/api/parcours/demo", headers=ORIGIN, json=ok).status_code == 200
    bad = {**ok, "modules": [{"id": "09-inconnu", "coef": 1}]}
    assert "module inconnu" in admin.put("/admin/api/parcours/demo", headers=ORIGIN, json=bad).json()["erreur"]


def test_history_and_restore(admin):
    admin.put("/admin/api/modules/01-demo/fichier?chemin=index.md", headers=ORIGIN, json={"content": "---\ntitre: V2\n---\n"})
    commits = admin.get("/admin/api/historique").json()["commits"]
    assert commits[0]["message"] == "Modifie modules/01-demo/index.md"
    assert commits[1]["publie"] is True
    admin.post("/admin/api/historique/restaurer", headers=ORIGIN, json={"sha": commits[1]["sha"]})
    assert "Démo" in admin.get("/admin/api/modules/01-demo/fichier?chemin=index.md").json()["contenu"]


def test_author_guide(admin, client):
    r = admin.get("/admin/guide/")
    assert r.status_code == 200 and "Guide de rédaction des formations" in r.text

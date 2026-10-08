import hashlib
import hmac
import time
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from fastapi.testclient import TestClient

from academy_content.app import create_app, duree_minutes, format_minutes
from academy_content.store import ContentStore
from academy_content.model import ContentError, load_module
from academy_content.testing import Rapport
from conftest import COURS_SEUL, make_module, make_parcours

SECRET = "s" * 40
HOST = "testserver"
ORIGIN = {"Origin": f"http://{HOST}"}
ETUDIANT = {"X-Academy-Etudiant": "1"}  # posé par Caddy quand Comptes reconnaît la session
INTERNE = {"X-Academy-Interne": hmac.new(SECRET.encode(), b"contenus-interne", hashlib.sha256).hexdigest()}


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
def anonyme(store):
    return TestClient(create_app(store, Runner(), SECRET, cookie_secure=False))


@pytest.fixture
def client(anonyme):
    """Étudiant connecté."""
    anonyme.headers.update(ETUDIANT)
    return anonyme


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
    assert "/compte/lab?suite=/lab/%3Fmodule%3D01-demo%26open%3Dws/01-demo/src/p/p/n.py" in page
    assert 'href="/compte/lab?suite=/lab/%3Fmodule%3D01-demo%26exercice%3D1"' in page
    assert 'href="/connexion"' in page and 'href="/compte/apprentissage"' in page  # en-tête : connexion, « Mon apprentissage »
    assert 'class="code-tabs"' in page  # python + cpp consécutifs
    assert "Quelle commande compile un workspace ?" in page
    assert 'aria-label="Étapes du module"' in page and 'href="/parcours/demo/"' in page
    assert page.count("<h1>") == 1  # plus de titre en double


def test_course_is_reserved_to_connected_students(anonyme):
    for path in ("/", "/catalogue/", "/decouvrir/", "/parcours/demo/", "/api/contenus/parcours"):
        assert anonyme.get(path).status_code == 200, path
    assert "Démo" in anonyme.get("/parcours/demo/").text  # titres des modules : publics
    for headers in ({}, {"X-Academy-Etudiant": "0"}, {"X-Academy-Etudiant": "oui"}):
        page = anonyme.get("/modules/01-demo/", headers=headers)
        assert page.status_code == 200
        assert "Cours réservé aux inscrits" in page.text and "<h1>Démo</h1>" in page.text
        assert 'href="/connexion?suite=/modules/01-demo/"' in page.text
        assert "print(1)" not in page.text and "Quelle commande" not in page.text and "Le nœud ne démarre" not in page.text
        assert page.headers["Cache-Control"] == "private, no-cache"
        for suffix in ("", "/lab", "/cours-fichiers", "/exercice", "/qcm"):
            r = anonyme.get(f"/api/contenus/modules/01-demo{suffix}", headers=headers)
            assert r.status_code == 401, (suffix, headers)
            assert "print(1)" not in r.text and "README" not in r.text
    # connecté : le cours ; le service Comptes (secret interne) lit aussi l'exercice
    page = anonyme.get("/modules/01-demo/", headers=ETUDIANT).text
    assert "print(1)" in page and "Cours réservé" not in page
    assert anonyme.get("/api/contenus/modules/01-demo/exercice", headers=INTERNE).status_code == 200
    assert anonyme.get("/modules/99-absent/").status_code == 404


def test_answers_never_reach_the_browser(client):
    import re
    page = client.get("/modules/01-demo/").text
    # Les choix d'une question sont rendus à l'identique, au texte près : rien ne trahit la bonne.
    choix = re.findall(r'<label><input type="radio" name="q1" value="(\d+)"> ([^<]*)</label>', page)
    # l'ordre affiché est mélangé ; chaque choix garde sa valeur d'origine (son rang dans qcm.yaml)
    assert sorted(choix) == [("0", "colcon build"), ("1", "catkin_make")]
    shapes = {re.sub(r'value="\d+"', "", m) for m in re.findall(r'<label><input type="radio" name="q1"[^>]*>', page)}
    assert len(shapes) == 1
    assert "colcon est l'outil" not in page  # explication absente
    api = client.get("/api/contenus/modules/01-demo/qcm").json()
    q1 = api["questions"][0]
    assert {k: q1[k] for k in ("id", "question", "multiple")} == {
        "id": "q1", "question": "Quelle commande compile un workspace ?", "multiple": False}
    assert [(str(v), c) for v, c in zip(q1["valeurs"], q1["choix"])] == choix  # même ordre que la page
    assert "correct" not in str(api) and "explication" not in str(api)
    assert api["questions"][1]["multiple"] is True


def test_qcm_order_does_not_give_away_the_answer():
    # Les auteurs écrivent souvent la bonne réponse en premier : l'ordre affiché la déplace.
    from pathlib import Path
    from academy_content.app import _public_qcm
    from academy_content.model import list_module_ids, load_module
    root = Path(__file__).resolve().parents[2] / "content"
    premiers = total = 0
    for module_id in list_module_ids(root):
        module = load_module(root, module_id)
        for q, public in zip(module.qcm.questions, _public_qcm(module)):
            assert sorted(public["valeurs"]) == list(range(len(q.choix)))
            assert public["choix"] == [q.choix[v].texte for v in public["valeurs"]]
            assert public == _public_qcm(module)[module.qcm.questions.index(q)]  # stable d'un affichage à l'autre
            total += 1
            premiers += q.choix[public["valeurs"][0]].correct
    assert total > 50 and premiers < total / 2


def test_qcm_correction(client):
    url = "/api/contenus/modules/01-demo/qcm"
    client.headers.update(INTERNE)
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
    hint = "/api/contenus/modules/01-demo/indices/1"
    assert "Regardez setup.py" in client.get(hint, headers=INTERNE).json()["html"]
    assert client.get("/api/contenus/modules/01-demo/indices/4", headers=INTERNE).status_code == 404
    assert client.get("/api/contenus/modules/01-demo/lab").json()["files"][0]["path"] == "README.md"
    files = client.get("/api/contenus/modules/01-demo/cours-fichiers").json()["files"]
    assert files == [{"path": "src/p/p/n.py", "content": "print(1)\n"}]


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/contenus/modules/01-demo/qcm"),
    ("GET", "/api/contenus/modules/01-demo/indices/1"),
    ("GET", "/api/contenus/modules/01-demo/explication"),
])
def test_internal_routes_require_the_shared_secret(client, method, path):
    body = {"json": {"reponses": {"q1": [0]}}} if method == "POST" else {}
    for headers in ({}, {"X-Academy-Interne": "faux"}, {"X-Academy-Interne": INTERNE["X-Academy-Interne"][:-1]}):
        r = client.request(method, path, headers=headers, **body)
        assert r.status_code == 403, headers
        assert "Regardez" not in r.text and "colcon" not in r.text and "manquait" not in r.text
    assert client.request(method, path, headers=INTERNE, **body).status_code == 200


def test_course_only_module_parts_and_bonus(tmp_path):
    seed = tmp_path / "seed"
    make_module(seed)
    make_module(seed, "02-cours", **{**COURS_SEUL, "index.md": "---\ntitre: Notions\nresume: R\nduree: 30 min\n---\n## A\n\nTexte.\n"})
    make_module(seed, "03-bonus", **{"index.md": "---\ntitre: En plus\nresume: R\nduree: 2 h\n---\nTexte.\n"})
    make_parcours(seed, modules=("01-demo", "02-cours", "03-bonus"),
                  extra={"01-demo": ["partie: Les bases"], "02-cours": ["partie: Les bases"],
                         "03-bonus": ["partie: Bonus", "bonus: true"]})
    client = TestClient(create_app(ContentStore(tmp_path / "store", seed=seed), Runner(), SECRET, cookie_secure=False))
    client.headers.update(ETUDIANT)
    mods = client.get("/api/contenus/parcours").json()["parcours"][0]["modules"]
    assert [(m["id"], m["exercice"], m["bonus"], m["partie"]) for m in mods] == [
        ("01-demo", True, False, "Les bases"), ("02-cours", False, False, "Les bases"), ("03-bonus", True, True, "Bonus")]
    # module de cours : pas d'étape Exercice, le QCM fait la note
    page = client.get("/modules/02-cours/").text
    assert 'id="exercice"' not in page and 'data-etape="exercice"' not in page and "exercice=1" not in page
    assert "ce module de cours n'a pas d'exercice" in page and 'href="#qcm" data-suivante' in page
    assert client.get("/api/contenus/modules/02-cours/exercice").status_code == 404
    assert client.get("/api/contenus/modules/02-cours/indices/1", headers=INTERNE).status_code == 404
    assert client.get("/api/contenus/modules/02-cours/lab").json() == {"files": []}
    # parcours : parties regroupées, bonus signalé et hors durée totale
    parcours = client.get("/parcours/demo/").text
    assert parcours.count('class="partie"') == 2 and "Les bases" in parcours
    assert 'class="bonus"' in parcours and "Bonus</strong>" in parcours
    assert "un module de cours, sans exercice, est noté sur son QCM" in parcours
    assert "Les modules bonus ne comptent pas dans la note finale" in parcours
    assert "40 min" in parcours  # 10 min + 30 min, sans les 2 h du bonus


def test_catalogue_announces_upcoming_parcours(store, client):
    store.write_parcours("nav2", {"titre": "Navigation avec Nav2", "description": "Aller au but",
                                  "statut": "bientot", "niveau": "intermediaire", "ordre": 20})
    store.publish(Runner())
    for path in ("/", "/catalogue/"):
        page = client.get(path).text
        assert "Navigation avec Nav2" in page and "Bientôt · Intermédiaire" in page, path
        assert 'href="/parcours/demo/"' in page and "/parcours/nav2/" not in page, path
    assert client.get("/parcours/nav2/").status_code == 404  # annoncé, pas encore ouvert
    assert [p["id"] for p in client.get("/api/contenus/parcours").json()["parcours"]] == ["demo"]


def test_parcours_page_and_discover_page(client):
    page = client.get("/parcours/demo/").text
    assert "Programme" in page and 'href="/modules/01-demo/"' in page and 'href="/decouvrir/"' in page
    assert "1 module · 10 min" in page
    assert "coefficient" not in page
    page = client.get("/decouvrir/").text
    assert "ROS 2, le langage commun des robots" in page and "https://docs.ros.org/en/jazzy/" in page
    assert 'href="/parcours/demo/"' in page


def test_durations():
    assert [duree_minutes(d) for d in ("1 h 30", "2 h", "45 min", "1h15", "", "bientôt")] == [90, 120, 45, 75, 0, 0]
    assert [format_minutes(m) for m in (690, 120, 45)] == ["11 h 30", "2 h", "45 min"]


def test_parcours_api_lists_modules_and_coefficients(client):
    data = client.get("/api/contenus/parcours").json()["parcours"]
    assert data[0]["id"] == "demo"
    assert [(m["id"], m["coef"]) for m in data[0]["modules"]] == [("01-demo", 1)]


def test_unknown_and_draft_only_modules_are_404(client, store, tmp_path):
    assert client.get("/modules/99-absent/").status_code == 404
    assert client.get("/api/contenus/modules/../etc").status_code == 404
    tpl = make_module(tmp_path / "tpl", "00-modele")
    store.create_module("02-brouillon", "Pas encore publié", tpl)
    assert client.get("/modules/02-brouillon/").status_code == 404
    assert client.get("/api/contenus/modules/02-brouillon/lab").status_code == 404


# --- Administration : accès

def test_admin_requires_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/compte/admin"  # connexion via Comptes
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


def test_verify_endpoint_for_the_logs_proxy(client):
    r = client.get("/admin/api/verifier", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/compte/admin"
    assert "x-academy-admin" not in r.headers
    client.cookies.set("academy_admin", "faux", path="/admin")
    assert client.get("/admin/api/verifier", follow_redirects=False).status_code == 302
    client.cookies.clear()
    client.get("/admin/login", params={"token": token()}, follow_redirects=False)
    r = client.get("/admin/api/verifier", follow_redirects=False)
    assert r.status_code == 204 and r.headers["x-academy-admin"] == "klein"
    assert 'href="/admin/journaux/"' in client.get("/admin/").text


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
    # Les champs que l'ancien formulaire n'envoie pas sont conservés
    assert admin.put("/admin/api/parcours/demo", headers=ORIGIN, json={**ok, "niveau": "avance"}).status_code == 200
    assert admin.put("/admin/api/parcours/demo", headers=ORIGIN, json=ok).status_code == 200
    assert admin.get("/admin/api/parcours/demo").json()["niveau"] == "avance"
    vide = {**ok, "modules": []}
    assert "au moins un module" in admin.put("/admin/api/parcours/demo", headers=ORIGIN, json=vide).json()["erreur"]
    assert admin.put("/admin/api/parcours/demo", headers=ORIGIN, json={**vide, "statut": "bientot"}).status_code == 200
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


SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>\n'


def test_course_images(tmp_path):
    seed = tmp_path / "seed"
    make_module(seed, **{"index.md": "---\ntitre: Démo\n---\n## A\n\n![Le graphe du robot](images/graphe.svg)\n",
                         "images/graphe.svg": SVG})
    make_parcours(seed)
    store = ContentStore(tmp_path / "store", seed=seed)
    anonyme = TestClient(create_app(store, Runner(), SECRET, cookie_secure=False))
    page = anonyme.get("/modules/01-demo/", headers=ETUDIANT).text
    assert '<img class="schema" src="/modules/01-demo/images/graphe.svg" alt="Le graphe du robot"' in page
    r = anonyme.get("/modules/01-demo/images/graphe.svg", headers=ETUDIANT)
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in r.headers["Content-Security-Policy"] and "script-src" not in r.headers["Content-Security-Policy"]
    # réservé comme le cours ; seuls les fichiers images/ autorisés
    assert anonyme.get("/modules/01-demo/images/graphe.svg").status_code == 404
    for name in ("absent.svg", "graphe.svg.exe", "..%2Findex.md", "Graphe.svg"):
        assert anonyme.get(f"/modules/01-demo/images/{name}", headers=ETUDIANT).status_code == 404, name
    # aperçu de l'administrateur : images du brouillon
    anonyme.get("/admin/login", params={"token": token()})
    assert anonyme.get("/admin/apercu/modules/01-demo/images/graphe.svg").status_code == 200
    html = anonyme.post("/admin/api/apercu", json={"module": "01-demo", "markdown": "![x](images/graphe.svg)"},
                        headers=ORIGIN).json()["html"]
    assert 'src="/admin/apercu/modules/01-demo/images/graphe.svg"' in html


@pytest.mark.parametrize("markdown, message", [
    ("![Le graphe](images/absent.svg)", "introuvable dans le module"),
    ("![](images/graphe.svg)", "décrivez-la entre les crochets"),
    ("![Ailleurs](https://exemple.fr/x.png)", "seules les images du dossier images/"),
])
def test_course_images_are_checked(tmp_path, markdown, message):
    make_module(tmp_path, **{"index.md": f"---\ntitre: Démo\n---\n{markdown}\n", "images/graphe.svg": SVG})
    with pytest.raises(ContentError) as e:
        load_module(tmp_path, "01-demo")
    assert message in str(e.value)

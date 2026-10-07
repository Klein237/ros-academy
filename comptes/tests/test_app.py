import re
from datetime import timedelta
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

import academy_comptes.app as appmod
from academy_comptes.clients import UpstreamError
from academy_comptes.db import LoginToken, UsageTick, User, utcnow
from academy_comptes.quotas import record_minute
from academy_comptes.settings import Settings

SECRET = "s" * 40
BASE = "https://testserver"
ORIGIN = {"Origin": BASE}


class FakeHub:
    def __init__(self):
        self.servers = {}
        self.stopped = []

    def running_servers(self):
        return dict(self.servers)

    def stop(self, name):
        self.stopped.append(name)
        self.servers.pop(name, None)

    deleted = None
    fail_delete = False

    def delete_user(self, name):
        if self.fail_delete:
            raise UpstreamError(502)
        self.deleted = (self.deleted or []) + [name]
        self.servers.pop(name, None)


class FakeContenus:
    QCM = {"q1": [0], "q2": [1]}

    def correct_qcm(self, module, reponses):
        if module == "99-absent":
            raise UpstreamError(404)
        justes = sum(1 for q, good in self.QCM.items() if reponses.get(q) == good)
        return {"note": 10.0 * justes, "sur": 20, "justes": justes, "total": 2, "questions": []}

    def hint(self, module, n):
        return {"n": n, "html": f"<p>indice {n} de {module}</p>"}

    def explanation(self, module):
        return {"html": "<p>la cause</p>"}

    # verify : résultat du check.sh officiel, par (module, étudiant) ; échec par défaut
    verdicts = {}
    verified = []

    def verify(self, module, student):
        self.verified.append((module, student))
        verdict = self.verdicts.get((module, student), {"ok": False, "code": 1, "journal": "Le robot n'avance pas."})
        if isinstance(verdict, Exception):
            raise verdict
        return verdict

    def parcours(self):
        return [{"id": "ros2", "titre": "ROS 2 Fondamentaux", "modules": [
            {"id": "01-a", "titre": "Module A", "coef": 1}, {"id": "02-b", "titre": "Module B", "coef": 3}]}]


def oauth_transport(github_verified=True, google_verified=True, email="eleve@exemple.fr"):
    def handler(request):
        url = str(request.url)
        if url.startswith("https://github.com/login/oauth/access_token"):
            return httpx.Response(200, json={"access_token": "gh"})
        if url == "https://api.github.com/user":
            return httpx.Response(200, json={"id": 42, "login": "eleve", "name": "Élève GitHub"})
        if url == "https://api.github.com/user/emails":
            return httpx.Response(200, json=[{"email": email, "primary": True, "verified": github_verified}])
        if url.startswith("https://oauth2.googleapis.com/token"):
            return httpx.Response(200, json={"access_token": "go"})
        if url.startswith("https://openidconnect.googleapis.com/v1/userinfo"):
            return httpx.Response(200, json={"sub": "g-7", "email": email, "email_verified": google_verified,
                                             "name": "Élève Google"})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


@pytest.fixture
def env(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(appmod, "send_account_mail", lambda settings, email, sorte, link: sent.append((email, link, sorte)))
    settings = Settings(jwt_secret=SECRET, public_url=BASE, database_url=f"sqlite:///{tmp_path}/c.db",
                        github_client_id="id", github_client_secret="sec", google_client_id="gid",
                        google_client_secret="gsec", admin_emails=frozenset({"admin@exemple.fr"}),
                        active_server_limit=2)
    hub, contenus = FakeHub(), FakeContenus()
    contenus.verdicts, contenus.verified = {}, []

    def make(transport=None):
        app = appmod.create_app(settings, hub=hub, contenus=contenus,
                                http=httpx.Client(transport=transport or oauth_transport()), background=False)
        return TestClient(app, base_url=BASE)

    return {"settings": settings, "hub": hub, "contenus": contenus, "sent": sent, "make": make}


@pytest.fixture
def client(env):
    return env["make"]()


PASSWORD = "un-mot-de-passe-solide"


def login(client, env, email="eleve@exemple.fr", suite="/", password=PASSWORD):
    """Connexion par mot de passe ; à la première fois, création du compte et lien de confirmation."""
    r = client.post("/connexion", data={"email": email, "mot_de_passe": password, "suite": suite}, headers=ORIGIN,
                    follow_redirects=False)
    if r.status_code == 303:
        return r
    r = client.post("/connexion/inscription", data={"email": email, "mot_de_passe": password, "suite": suite},
                    headers=ORIGIN)
    assert r.status_code == 200, r.text
    email_sent, link, sorte = env["sent"][-1]
    assert sorte == "confirmation"
    return client.get(urlsplit(link).path, follow_redirects=False)


def db(client):
    return client.app.state.session_factory()


# --- Inscription, confirmation de l'adresse, mot de passe

def signup(client, email="eleve@exemple.fr", password=PASSWORD, suite="/", nom="Élève Test"):
    return client.post("/connexion/inscription", data={"nom": nom, "email": email, "mot_de_passe": password,
                                                         "suite": suite}, headers=ORIGIN)


def test_signup_confirm_then_password_login(client, env):
    r = signup(client, "Eleve@Exemple.FR", suite="/modules/02-noeud/")
    assert r.status_code == 200 and "Vérifiez votre boîte de réception" in r.text
    email, link, sorte = env["sent"][-1]
    assert (email, sorte) == ("eleve@exemple.fr", "confirmation") and link not in r.text  # pas de lien à l'écran
    # pas de connexion avant la confirmation : un nouvel e-mail de confirmation est proposé
    r = client.post("/connexion", data={"email": "eleve@exemple.fr", "mot_de_passe": PASSWORD}, headers=ORIGIN)
    assert "abord votre adresse" in r.text and client.get("/api/comptes/moi").status_code == 401
    r = client.get(urlsplit(link).path, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/modules/02-noeud/"
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    assert client.get("/api/comptes/moi").json()["nom"] == "Élève Test"
    assert client.get(urlsplit(link).path, follow_redirects=False).status_code == 400  # usage unique
    client.post("/deconnexion", headers=ORIGIN)
    r = client.post("/connexion", data={"email": "ELEVE@exemple.fr", "mot_de_passe": PASSWORD, "suite": "/compte/"},
                    headers=ORIGIN, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/compte/"
    with db(client) as s:
        stored = s.query(User).one().mot_de_passe
    assert stored.startswith("scrypt$") and PASSWORD not in stored


def test_wrong_password_same_message_and_limited(client, env):
    login(client, env)
    client.post("/deconnexion", headers=ORIGIN)
    bad = client.post("/connexion", data={"email": "eleve@exemple.fr", "mot_de_passe": "faux-mot-de-passe"}, headers=ORIGIN)
    unknown = client.post("/connexion", data={"email": "personne@exemple.fr", "mot_de_passe": "faux-mot-de-passe"},
                          headers=ORIGIN)
    assert bad.status_code == unknown.status_code == 400
    assert "Adresse e-mail ou mot de passe incorrect" in bad.text and "Adresse e-mail ou mot de passe incorrect" in unknown.text
    for _ in range(9):
        client.post("/connexion", data={"email": "eleve@exemple.fr", "mot_de_passe": "faux"}, headers=ORIGIN)
    r = client.post("/connexion", data={"email": "eleve@exemple.fr", "mot_de_passe": PASSWORD}, headers=ORIGIN)
    assert "essais pour cette adresse" in r.text  # même le bon mot de passe attend la fin du délai


def test_one_link_at_a_time_and_resend_delay(client, env):
    signup(client)
    first = env["sent"][-1][1]
    r = client.post("/connexion/renvoyer", data={"email": "eleve@exemple.fr"}, headers=ORIGIN)
    assert "patientez une minute" in r.text and len(env["sent"]) == 1
    with db(client) as s:
        for t in s.query(LoginToken):
            t.cree_le = utcnow() - timedelta(minutes=2)
        s.commit()
    r = client.post("/connexion/renvoyer", data={"email": "eleve@exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 200 and len(env["sent"]) == 2
    assert client.get(urlsplit(first).path, follow_redirects=False).status_code == 400  # annulé par le nouveau
    assert client.get(urlsplit(env["sent"][-1][1]).path, follow_redirects=False).status_code == 303


def test_signup_on_existing_account_reveals_nothing(client, env):
    login(client, env)
    client.post("/deconnexion", headers=ORIGIN)
    r = signup(client, password="un-autre-mot-de-passe")
    assert r.status_code == 200 and "Vérifiez votre boîte de réception" in r.text
    assert env["sent"][-1][2] == "compte_existant"  # l'e-mail propose de choisir un nouveau mot de passe
    r = client.post("/connexion", data={"email": "eleve@exemple.fr", "mot_de_passe": PASSWORD}, headers=ORIGIN,
                    follow_redirects=False)
    assert r.status_code == 303  # l'ancien mot de passe n'a pas changé


def test_password_reset(client, env):
    login(client, env)
    other = env["make"]()
    login(other, env)  # une deuxième session, déconnectée par la réinitialisation
    client.post("/deconnexion", headers=ORIGIN)
    r = client.post("/connexion/oubli", data={"email": "personne@exemple.fr"}, headers=ORIGIN)
    assert "Si un compte existe" in r.text and len([x for x in env["sent"] if x[2] == "reinitialisation"]) == 0
    r = client.post("/connexion/oubli", data={"email": "eleve@exemple.fr", "suite": "/compte/"}, headers=ORIGIN)
    assert "Si un compte existe" in r.text
    link = urlsplit(env["sent"][-1][1]).path
    assert env["sent"][-1][2] == "reinitialisation" and "Choisissez un nouveau mot de passe" in client.get(link).text
    assert "au moins 10 caractères" in client.post(link, data={"mot_de_passe": "court"}, headers=ORIGIN).text
    r = client.post(link, data={"mot_de_passe": "nouveau-mot-de-passe"}, headers=ORIGIN, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/compte/"
    assert other.get("/api/comptes/moi").status_code == 401
    assert client.get(link).status_code == 400  # usage unique
    client.post("/deconnexion", headers=ORIGIN)
    assert login(client, env, password="nouveau-mot-de-passe").status_code == 303


def test_legacy_account_sets_password_by_reset(client, env):
    """Compte ouvert avant les mots de passe (lien par e-mail) : « Mot de passe oublié » lui en donne un."""
    with db(client) as s:
        s.add(User(email="ancien@exemple.fr", email_verifie_le=utcnow()))
        s.commit()
    r = client.post("/connexion", data={"email": "ancien@exemple.fr", "mot_de_passe": PASSWORD}, headers=ORIGIN)
    assert r.status_code == 400
    client.post("/connexion/oubli", data={"email": "ancien@exemple.fr"}, headers=ORIGIN)
    link = urlsplit(env["sent"][-1][1]).path
    client.post(link, data={"mot_de_passe": PASSWORD}, headers=ORIGIN)
    assert client.get("/api/comptes/moi").json()["email"] == "ancien@exemple.fr"


def test_change_password_from_account(client, env):
    login(client, env)
    r = client.post("/compte/mot-de-passe", data={"actuel": "faux", "nouveau": "nouveau-mot-de-passe"}, headers=ORIGIN)
    assert r.status_code == 400 and "Mot de passe actuel incorrect" in r.text
    r = client.post("/compte/mot-de-passe", data={"actuel": PASSWORD, "nouveau": "nouveau-mot-de-passe"}, headers=ORIGIN)
    assert r.status_code == 200 and "Mot de passe enregistré" in r.text


def test_expired_link_is_refused(client, env):
    signup(client)
    with db(client) as s:
        for t in s.query(LoginToken):
            t.expire_le = utcnow() - timedelta(seconds=1)
        s.commit()
    r = client.get(urlsplit(env["sent"][-1][1]).path, follow_redirects=False)
    assert r.status_code == 400


def test_link_requests_are_rate_limited(client, env):
    login(client, env, "a@exemple.fr")  # 1 lien : la confirmation

    def older():  # passé le délai de renvoi (60 s), toujours dans l'heure
        with db(client) as s:
            for t in s.query(LoginToken):
                t.cree_le = utcnow() - timedelta(seconds=61)
            s.commit()

    for _ in range(4):
        older()
        assert "Si un compte existe" in client.post("/connexion/oubli", data={"email": "a@exemple.fr"}, headers=ORIGIN).text
    older()
    r = client.post("/connexion/oubli", data={"email": "a@exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 429 and "Trop de demandes" in r.text


def test_invalid_input_and_foreign_origin(client):
    assert "Adresse e-mail invalide" in signup(client, "pas-un-mail").text
    assert "au moins 10 caractères" in signup(client, password="court").text
    assert client.post("/connexion", data={"email": "a@exemple.fr", "mot_de_passe": "x"}).status_code == 403
    assert client.post("/connexion/inscription", data={"email": "a@exemple.fr", "mot_de_passe": PASSWORD},
                       headers={"Origin": "https://evil.example"}).status_code == 403


@pytest.mark.parametrize("suite", ["//evil.example/", "https://evil.example/", "/\\evil", "/\tx"])
def test_redirect_after_login_stays_local(client, env, suite):
    assert login(client, env, suite=suite).headers["location"] == "/"


def test_logout_revokes_session(client, env):
    login(client, env)
    assert client.post("/deconnexion", headers=ORIGIN, follow_redirects=False).status_code == 303
    assert client.get("/api/comptes/moi").status_code == 401
    assert client.get("/api/comptes/session").json() == {"connecte": False}


def test_caddy_asks_whether_the_course_may_be_shown(client, env):
    """forward_auth avant le cours d'un module : toujours 200, l'en-tête dit si la session est ouverte."""
    url = "/api/comptes/interne/session"
    r = client.get(url)
    assert r.status_code == 200 and r.headers["X-Academy-Etudiant"] == "0"
    client.cookies.set("academy_session", "faux")
    assert client.get(url).headers["X-Academy-Etudiant"] == "0"
    client.cookies.clear()
    login(client, env)
    assert client.get(url).headers["X-Academy-Etudiant"] == "1"
    client.post("/deconnexion", headers=ORIGIN)
    assert client.get(url).headers["X-Academy-Etudiant"] == "0"


def test_forged_cookie_is_refused(client):
    client.cookies.set("academy_session", "faux")
    assert client.get("/api/comptes/moi").status_code == 401


# --- OAuth

def start_oauth(client, provider):
    r = client.get(f"/connexion/{provider}?suite=/compte/", follow_redirects=False)
    assert r.status_code == 303
    return parse_qs(urlsplit(r.headers["location"]).query)["state"][0]


def test_github_login(client):
    state = start_oauth(client, "github")
    r = client.get(f"/connexion/github/retour?code=c&state={state}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/compte/"
    me = client.get("/api/comptes/moi").json()
    assert me["email"] == "eleve@exemple.fr" and me["nom"] == "Élève GitHub"


def test_oauth_state_must_match_this_browser(client, env):
    start_oauth(client, "github")
    r = client.get("/connexion/github/retour?code=c&state=autre", follow_redirects=False)
    assert r.status_code == 400
    other = env["make"]()  # autre navigateur, sans le cookie d'état
    state = start_oauth(client, "github")
    assert other.get(f"/connexion/github/retour?code=c&state={state}", follow_redirects=False).status_code == 400


@pytest.mark.parametrize("provider", ["github", "google"])
def test_unverified_email_is_refused(env, provider):
    client = env["make"](oauth_transport(github_verified=False, google_verified=False))
    state = start_oauth(client, provider)
    r = client.get(f"/connexion/{provider}/retour?code=c&state={state}", follow_redirects=False)
    assert r.status_code == 400 and "vérifiée" in r.text


def test_same_email_same_account_across_providers(client, env):
    login(client, env)
    first = client.get("/api/comptes/moi").json()["hub"]
    other = env["make"]()
    state = start_oauth(other, "google")
    other.get(f"/connexion/google/retour?code=c&state={state}", follow_redirects=False)
    assert other.get("/api/comptes/moi").json()["hub"] == first


def test_disabled_provider_is_404(env):
    env["settings"].github_client_id = ""
    client = env["make"]()
    assert client.get("/connexion/github", follow_redirects=False).status_code == 404
    assert "Continuer avec GitHub" not in client.get("/connexion").text


# --- Lab et quotas

def test_lab_requires_login_then_issues_short_jwt(client, env):
    r = client.get("/compte/lab?suite=/lab/%3Fmodule%3D02-noeud", follow_redirects=False)
    assert unquote(r.headers["location"]).startswith("/connexion?suite=/compte/lab")
    login(client, env)
    r = client.get("/compte/lab?suite=/lab/%3Fmodule%3D02-noeud", follow_redirects=False)
    loc = urlsplit(r.headers["location"])
    assert loc.path == "/hub/jwt_login"
    q = parse_qs(loc.query)
    assert q["next"] == ["/lab/?module=02-noeud"]
    claims = jwt.decode(q["token"][0], SECRET, algorithms=["HS256"], audience="ros-lab")
    assert claims["sub"] == "u1" and claims["plan"] == "free" and claims["exp"] - claims["iat"] == 300


@pytest.mark.parametrize("suite", ["/admin/", "//evil", "/labx", "https://evil/lab/"])
def test_lab_redirect_only_to_the_lab(client, env, suite):
    login(client, env)
    r = client.get("/compte/lab", params={"suite": suite}, follow_redirects=False)
    assert parse_qs(urlsplit(r.headers["location"]).query)["next"] == ["/lab/"]


def test_minutes_are_counted_once_per_minute_and_quota_stops_the_lab(client, env):
    login(client, env)
    hub, settings = env["hub"], env["settings"]
    hub.servers = {"u1": True, "u99": True, "autre": True, "u2": False}
    now = utcnow().replace(second=10)
    with db(client) as s:
        record_minute(s, hub, settings, now)
        record_minute(s, hub, settings, now.replace(second=50))  # même minute : rien de plus
        assert s.query(UsageTick).count() == 1
        # 598 minutes plus tôt dans le mois : il reste 1 minute
        start = now.replace(day=1, hour=0, minute=0)
        s.add_all([UsageTick(user_id=1, minute=start + timedelta(minutes=i)) for i in range(598)])
        s.commit()
    assert client.get("/api/comptes/moi").json()["minutes_restantes"] == 1
    assert hub.stopped == []
    with db(client) as s:
        record_minute(s, hub, settings, now + timedelta(minutes=1))
    assert hub.stopped == ["u1"]
    r = client.get("/compte/lab", follow_redirects=False)
    assert r.status_code == 403 and "Quota de lab épuisé" in r.text


def test_pro_plan_has_no_limit(client, env):
    login(client, env)
    with db(client) as s:
        s.get(User, 1).formule = "pro"
        s.commit()
    assert client.get("/api/comptes/moi").json()["minutes_restantes"] is None


# --- QCM, exercices, notes

def test_qcm_two_attempts_best_kept(client, env):
    assert client.post("/api/comptes/qcm/01-a", json={"reponses": {}}, headers=ORIGIN).status_code == 401
    login(client, env)
    assert client.post("/api/comptes/qcm/01-a", json={"reponses": {}}).status_code == 403  # sans Origin
    r1 = client.post("/api/comptes/qcm/01-a", json={"reponses": {"q1": [0], "q2": [1]}}, headers=ORIGIN).json()
    assert r1["note"] == 20 and r1["restantes"] == 1
    r2 = client.post("/api/comptes/qcm/01-a", json={"reponses": {"q1": [1]}}, headers=ORIGIN).json()
    assert r2["note"] == 0 and r2["meilleure"] == 20 and r2["restantes"] == 0
    r3 = client.post("/api/comptes/qcm/01-a", json={"reponses": {"q1": [0]}}, headers=ORIGIN)
    assert r3.status_code == 409
    assert client.get("/api/comptes/qcm/01-a").json() == {"tentatives": 2, "restantes": 0, "meilleure": 20.0}
    assert client.post("/api/comptes/qcm/99-absent", json={"reponses": {}}, headers=ORIGIN).status_code == 404
    assert client.post("/api/comptes/qcm/..%2Fx", json={"reponses": {}}, headers=ORIGIN).status_code == 404


def test_hints_are_counted_in_order(client, env):
    login(client, env)
    # écriture (pénalité) : pas de GET, et l'origine est vérifiée (lien ou formulaire d'un autre site)
    assert client.get("/api/comptes/exercices/01-a/indices/1").status_code == 405
    assert client.post("/api/comptes/exercices/01-a/indices/1").status_code == 403
    assert client.post("/api/comptes/exercices/01-a/indices/1", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/comptes/exercices/01-a/indices/2", headers=ORIGIN).status_code == 400
    assert client.post("/api/comptes/exercices/01-a/indices/1", headers=ORIGIN).json()["indices"] == 1
    assert client.post("/api/comptes/exercices/01-a/indices/1", headers=ORIGIN).json()["indices"] == 1  # relu : pas recompté
    assert client.post("/api/comptes/exercices/01-a/indices/2", headers=ORIGIN).json()["html"] == "<p>indice 2 de 01-a</p>"
    assert client.post("/api/comptes/exercices/01-a/indices/4", headers=ORIGIN).status_code == 400
    assert client.get("/api/comptes/exercices/01-a").json() == {"indices": 2, "reussi": False}


def succeed(env, module, student="u1"):
    env["contenus"].verdicts[(module, student)] = {"ok": True, "code": 0, "journal": "Le robot avance."}


def test_success_only_from_the_official_check(client, env):
    login(client, env)
    url = "/api/comptes/exercices/01-a/verification"
    # la réussite déclarée par le navigateur n'existe plus
    assert client.post("/api/comptes/exercices/01-a/reussite", headers=ORIGIN).status_code in (404, 405)
    assert client.post(url).status_code == 403  # sans Origin
    r = client.post(url, headers=ORIGIN).json()
    assert r == {"reussi": False, "verification": False, "journal": "Le robot n'avance pas.", "indices": 0}
    assert env["contenus"].verified == [("01-a", "u1")]  # vérifié pour le compte connecté, jamais un autre
    succeed(env, "01-a")
    assert client.post(url, headers=ORIGIN).json()["reussi"] is True
    # une vérification ratée plus tard ne retire pas une réussite enregistrée
    env["contenus"].verdicts.clear()
    assert client.post(url, headers=ORIGIN).json() == {
        "reussi": True, "verification": False, "journal": "Le robot n'avance pas.", "indices": 0}


def test_verification_errors(client, env):
    login(client, env)
    url = "/api/comptes/exercices/01-a/verification"
    env["contenus"].verdicts[("01-a", "u1")] = UpstreamError(429)
    assert client.post(url, headers=ORIGIN).status_code == 429
    env["contenus"].verdicts[("01-a", "u1")] = UpstreamError(500)
    assert client.post(url, headers=ORIGIN).status_code == 502
    env["contenus"].verdicts[("01-a", "u1")] = {"ok": "oui", "journal": "x"}  # réponse inattendue : pas une réussite
    assert client.post(url, headers=ORIGIN).json()["reussi"] is False
    assert client.post("/api/comptes/exercices/..%2Fx/verification", headers=ORIGIN).status_code == 404
    assert client.post(url, headers={"Origin": "https://evil.example"}).status_code == 403


def test_one_verification_at_a_time_per_student(client, env):
    import threading
    started, release = threading.Event(), threading.Event()

    def slow(module, student):
        started.set()
        release.wait(5)
        return {"ok": True, "code": 0, "journal": "ok"}

    login(client, env)
    env["contenus"].verify = slow
    url = "/api/comptes/exercices/01-a/verification"
    first = {}
    t = threading.Thread(target=lambda: first.update(r=client.post(url, headers=ORIGIN)))
    t.start()
    assert started.wait(5)
    assert client.post(url, headers=ORIGIN).status_code == 409
    release.set()
    t.join(5)
    assert first["r"].json()["reussi"] is True
    assert client.post(url, headers=ORIGIN).status_code == 200  # de nouveau possible


def test_explanation_only_after_success(client, env):
    login(client, env)
    assert client.get("/api/comptes/exercices/01-a/explication").status_code == 403
    succeed(env, "01-a")
    assert client.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN).json()["reussi"] is True
    assert client.get("/api/comptes/exercices/01-a/explication").json()["html"] == "<p>la cause</p>"
    # un indice lu après la réussite ne pénalise pas
    client.post("/api/comptes/exercices/01-a/indices/1", headers=ORIGIN)
    assert client.get("/api/comptes/exercices/01-a").json()["indices"] == 0


def test_results_page_and_final_grade(client, env):
    login(client, env)
    page = client.get("/compte/resultats").text
    assert "disponible quand les 2 modules seront terminés" in page
    client.post("/api/comptes/qcm/01-a", json={"reponses": {"q1": [0], "q2": [1]}}, headers=ORIGIN)  # 20
    succeed(env, "01-a")
    succeed(env, "02-b")
    client.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN)  # 20 → module 20
    client.post("/api/comptes/qcm/02-b", json={"reponses": {"q1": [0]}}, headers=ORIGIN)  # 10
    client.post("/api/comptes/exercices/02-b/indices/1", headers=ORIGIN)
    client.post("/api/comptes/exercices/02-b/verification", headers=ORIGIN)  # 17 → module 13.5
    page = client.get("/compte/resultats").text
    expected = (20 * 1 + 13.5 * 3) / 4  # 15.125 → 15,12 ou 15,13
    assert re.search(r"Note finale : <strong>15,1[23] / 20</strong>", page), expected


def test_course_module_and_bonus_in_final_grade(client, env, monkeypatch):
    """Module de cours noté sur son QCM ; module bonus suivi, mais hors note finale et hors progression."""
    modules = [{"id": "01-a", "titre": "Module A", "coef": 1},
               {"id": "03-c", "titre": "Notions", "coef": 1, "exercice": False},
               {"id": "04-d", "titre": "En plus", "coef": 1, "bonus": True}]
    monkeypatch.setattr(env["contenus"], "parcours", lambda: [{"id": "ros2", "titre": "ROS 2 Fondamentaux",
                                                               "modules": modules}])
    login(client, env)
    page = client.get("/compte/resultats").text
    assert "disponible quand les 2 modules seront terminés" in page
    assert "sans exercice" in page and ">bonus<" in page
    client.post("/api/comptes/qcm/01-a", json={"reponses": {"q1": [0], "q2": [1]}}, headers=ORIGIN)  # 20
    succeed(env, "01-a")
    client.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN)  # module 20
    client.post("/api/comptes/qcm/03-c", json={"reponses": {"q1": [0]}}, headers=ORIGIN)  # 10 : la note du module
    page = client.get("/compte/resultats").text
    assert "Note finale : <strong>15,00 / 20</strong>" in page  # (20 + 10) / 2, sans le bonus
    progression = client.get("/api/comptes/progression/ros2").json()
    assert progression["termines"] == 2 and progression["total"] == 2
    assert progression["prochain"] == "04-d"


def test_learning_dashboard_and_progress_api(client, env):
    assert client.get("/compte/apprentissage", follow_redirects=False).headers["location"].startswith("/connexion")
    assert client.get("/api/comptes/progression/ros2").json() == {"connecte": False}
    login(client, env)
    page = client.get("/compte/apprentissage").text
    assert "Votre premier module" in page and "Commencer" in page and 'href="/modules/01-a/"' in page
    client.post("/api/comptes/qcm/01-a", json={"reponses": {"q1": [0], "q2": [1]}}, headers=ORIGIN)  # 20
    succeed(env, "01-a")
    client.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN)  # module 01-a terminé, 20/20
    client.post("/api/comptes/qcm/02-b", json={"reponses": {"q1": [0]}}, headers=ORIGIN)  # 02-b commencé
    data = client.get("/api/comptes/progression/ros2").json()
    assert data["termines"] == 1 and data["total"] == 2 and data["prochain"] == "02-b"
    assert data["modules"]["01-a"] == {"etat": "termine", "note": 20.0}
    assert data["modules"]["02-b"] == {"etat": "en_cours", "note": None}
    page = client.get("/compte/apprentissage").text
    assert "Reprendre là où vous en étiez" in page and 'href="/modules/02-b/"' in page
    assert "20,0 / 20" in page  # moyenne des modules terminés
    assert client.get("/api/comptes/progression/inconnu").status_code == 404


# --- File d'attente

def test_queue_positions_and_ownership(client, env):
    env["hub"].servers = {"u50": True, "u51": True}  # limite 2 : plein
    login(client, env, "a@exemple.fr")
    a = client.post("/api/comptes/file", headers=ORIGIN).json()
    assert a["position"] == 1 and a["a_vous"] is False
    other = TestClient(client.app, base_url=BASE)  # même application, autre navigateur
    login(other, env, "b@exemple.fr")
    b = other.post("/api/comptes/file", headers=ORIGIN).json()
    assert b["position"] == 2
    assert other.post(f"/api/comptes/file/{a['ticket']}", headers=ORIGIN).status_code == 404  # pas son ticket
    env["hub"].servers = {"u50": True}  # une place se libère
    client.app.state.tick()
    assert client.post(f"/api/comptes/file/{a['ticket']}", headers=ORIGIN).json()["a_vous"] is True
    assert other.post(f"/api/comptes/file/{b['ticket']}", headers=ORIGIN).json()["a_vous"] is False
    client.delete(f"/api/comptes/file/{a['ticket']}", headers=ORIGIN)
    assert other.post(f"/api/comptes/file/{b['ticket']}", headers=ORIGIN).json() == {
        "ticket": b["ticket"], "position": 1, "a_vous": True}


# --- Administration

def test_admin_link_only_for_admin_emails(client, env):
    login(client, env, "eleve@exemple.fr")
    assert client.get("/compte/admin", follow_redirects=False).status_code == 403
    admin = env["make"]()
    login(admin, env, "admin@exemple.fr")
    loc = urlsplit(admin.get("/compte/admin", follow_redirects=False).headers["location"])
    assert loc.path == "/admin/login"
    claims = jwt.decode(parse_qs(loc.query)["token"][0], SECRET, algorithms=["HS256"], audience="ros-academy-admin")
    assert claims["role"] == "admin"


def test_pages_render(client, env):
    assert "Mot de passe oublié" in client.get("/connexion").text
    assert "Créer mon compte" in client.get("/connexion/inscription").text
    login(client, env)
    page = client.get("/compte/").text
    assert "600 min" in page and "Se déconnecter" in page
    assert "default-src 'self'" in client.get("/compte/").headers["content-security-policy"]


# --- Route interne du Hub (quota avant démarrage)

def test_hub_asks_quota_with_the_derived_secret(client, env):
    from academy_comptes.clients import comptes_token
    login(client, env)
    url = "/api/comptes/interne/lab/u1"
    for headers in ({}, {"X-Academy-Interne": "faux"}, {"X-Academy-Interne": comptes_token("autre" * 8)}):
        assert client.get(url, headers=headers).status_code == 403
    ok = {"X-Academy-Interne": comptes_token(SECRET)}
    assert client.get(url, headers=ok).json() == {"autorise": True}
    assert client.get("/api/comptes/interne/lab/u99", headers=ok).status_code == 404
    assert client.get("/api/comptes/interne/lab/admin", headers=ok).status_code == 404
    with db(client) as s:
        start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        s.add_all([UsageTick(user_id=1, minute=start + timedelta(minutes=i)) for i in range(600)])
        s.commit()
    assert client.get(url, headers=ok).json() == {"autorise": False}

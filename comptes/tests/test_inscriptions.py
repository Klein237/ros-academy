"""Inscriptions par vagues (places, liste d'attente, invitations) et équipe des formateurs."""

import re
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from academy_comptes.db import User
from test_app import BASE, ORIGIN, PASSWORD, client, db, env, login, signup  # noqa: F401 (fixtures)


def browser(client):
    return TestClient(client.app, base_url=BASE)


def admin(client, env):
    b = browser(client)
    login(b, env, "admin@exemple.fr")
    return b


def set_places(b, n):
    return b.post("/compte/formateur/inscriptions/places", data={"places": str(n)}, headers=ORIGIN)


def register(client, env, email):
    """Inscription puis clic sur le lien de confirmation, dans un navigateur neuf."""
    b = browser(client)
    signup(b, email)
    _, link, sorte = env["sent"][-1]
    assert sorte == "confirmation"
    return b, b.get(urlsplit(link).path, follow_redirects=False)


def statut(client, email):
    with db(client) as s:
        return s.query(User).filter_by(email=email).one().statut


def sorts(env, email):
    return [sorte for e, _, sorte in env["sent"] if e == email]


def test_without_limit_everyone_gets_in(client, env):
    b, r = register(client, env, "a@exemple.fr")
    assert r.status_code == 303 and b.get("/api/comptes/moi").status_code == 200
    assert statut(client, "a@exemple.fr") == "actif"


def test_full_wave_puts_new_accounts_on_the_waiting_list(client, env):
    adm = admin(client, env)
    assert set_places(adm, 1).status_code == 200
    first, r = register(client, env, "un@exemple.fr")
    assert r.status_code == 303 and first.get("/api/comptes/moi").status_code == 200
    # la page d'inscription prévient, puis l'adresse confirmée prend rang
    assert "liste d'attente" in browser(client).get("/connexion/inscription").text
    b, r = register(client, env, "deux@exemple.fr")
    assert r.status_code == 200 and "Vous êtes sur la liste d'attente" in r.text and "n° 1" in r.text
    assert "set-cookie" not in r.headers and b.get("/api/comptes/moi").status_code == 401
    assert sorts(env, "deux@exemple.fr") == ["confirmation", "attente"]
    _, r = register(client, env, "trois@exemple.fr")
    assert "n° 2" in r.text
    # connexion par mot de passe : toujours la liste d'attente, sans session ni nouvel e-mail
    r = b.post("/connexion", data={"email": "deux@exemple.fr", "mot_de_passe": PASSWORD}, headers=ORIGIN,
               follow_redirects=False)
    assert r.status_code == 200 and "n° 1" in r.text and "set-cookie" not in r.headers
    assert sorts(env, "deux@exemple.fr") == ["confirmation", "attente"]
    assert statut(client, "deux@exemple.fr") == "en_attente"


def test_oauth_signup_waits_too(env):
    from test_app import oauth_transport
    c = env["make"](oauth_transport(email="oauth@exemple.fr"))
    adm = admin(c, env)
    set_places(adm, 0)
    r = c.get("/connexion/github", follow_redirects=False)
    state = re.search(r"state=([^&]+)", r.headers["location"]).group(1)
    r = c.get(f"/connexion/github/retour?code=c&state={state}", follow_redirects=False)
    assert r.status_code == 200 and "liste d'attente" in r.text
    assert "academy_session=" not in r.headers.get("set-cookie", "")
    assert statut(c, "oauth@exemple.fr") == "en_attente"


def test_staff_never_waits_and_takes_no_seat(client, env):
    adm = admin(client, env)
    set_places(adm, 0)
    assert adm.get("/api/comptes/moi").status_code == 200
    r = adm.post("/compte/formateur/equipe", data={"email": "Collegue@Exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 200 and "a rejoint l&#39;équipe" in r.text
    assert sorts(env, "collegue@exemple.fr") == ["formateur"]
    col, r = register(client, env, "collegue@exemple.fr")
    assert r.status_code == 303 and col.get("/compte/formateur").status_code == 200
    page = adm.get("/compte/formateur/inscriptions").text
    assert "collegue@exemple.fr" not in page and "admin@exemple.fr" not in page


def test_invite_desinscrire_and_reactivate(client, env):
    adm = admin(client, env)
    set_places(adm, 0)
    b, _ = register(client, env, "eleve@exemple.fr")
    page = adm.get("/compte/formateur/inscriptions").text
    assert "en attente · n° 1" in page and "Inviter" in page
    uid = int(re.search(r"/compte/formateur/inscriptions/(\d+)/activer", page).group(1))
    r = adm.post(f"/compte/formateur/inscriptions/{uid}/activer", headers=ORIGIN)
    assert r.status_code == 200 and "1 compte activé" in r.text
    assert sorts(env, "eleve@exemple.fr")[-1] == "activation"
    r = b.post("/connexion", data={"email": "eleve@exemple.fr", "mot_de_passe": PASSWORD}, headers=ORIGIN,
               follow_redirects=False)
    assert r.status_code == 303 and b.get("/api/comptes/moi").status_code == 200
    # désinscription : la session tombe, le lab s'arrête, la connexion affiche « Inscription close »
    r = adm.post(f"/compte/formateur/inscriptions/{uid}/desinscrire", headers=ORIGIN, follow_redirects=False)
    assert r.status_code == 303 and f"u{uid}" in env["hub"].stopped
    assert b.get("/api/comptes/moi").status_code == 401
    r = b.post("/connexion", data={"email": "eleve@exemple.fr", "mot_de_passe": PASSWORD}, headers=ORIGIN)
    assert "Inscription close" in r.text
    # le lab refuse aussi un compte désinscrit
    from academy_comptes.clients import INTERNAL_HEADER, comptes_token
    from test_app import SECRET
    r = client.get(f"/api/comptes/interne/lab/u{uid}", headers={INTERNAL_HEADER: comptes_token(SECRET)})
    assert r.json() == {"autorise": False}
    # réactivation, même sans place libre
    r = adm.post(f"/compte/formateur/inscriptions/{uid}/activer", headers=ORIGIN)
    assert "1 compte activé" in r.text and statut(client, "eleve@exemple.fr") == "actif"


def test_open_wave_invites_in_order(client, env):
    adm = admin(client, env)
    set_places(adm, 1)
    register(client, env, "p1@exemple.fr")
    for e in ("w1@exemple.fr", "w2@exemple.fr", "w3@exemple.fr"):
        register(client, env, e)
    r = adm.post("/compte/formateur/inscriptions/vague", data={"places": "2"}, headers=ORIGIN)
    assert r.status_code == 200 and "2 comptes activés" in r.text
    assert [statut(client, e) for e in ("w1@exemple.fr", "w2@exemple.fr", "w3@exemple.fr")] == \
        ["actif", "actif", "en_attente"]
    assert sorts(env, "w1@exemple.fr")[-1] == "activation"
    # une place libérée par une désinscription : vague de 0 place supplémentaire
    with db(client) as s:
        uid = s.query(User).filter_by(email="p1@exemple.fr").one().id
    adm.post(f"/compte/formateur/inscriptions/{uid}/desinscrire", headers=ORIGIN)
    r = adm.post("/compte/formateur/inscriptions/vague", data={"places": "0"}, headers=ORIGIN)
    assert "1 compte activé" in r.text and statut(client, "w3@exemple.fr") == "actif"
    r = adm.post("/compte/formateur/inscriptions/vague", data={"places": "0"}, headers=ORIGIN)
    assert "Personne n&#39;était en attente" in r.text
    assert "places au total" in r.text and set_places(adm, -3).status_code == 400


def test_quit_waiting_list_deletes_the_account(client, env):
    adm = admin(client, env)
    set_places(adm, 0)
    b, r = register(client, env, "part@exemple.fr")
    jeton = re.search(r'name="jeton" value="([^"]+)"', r.text).group(1)
    assert b.post("/connexion/quitter", data={"jeton": "faux"}, headers=ORIGIN).status_code == 400
    r = b.post("/connexion/quitter", data={"jeton": jeton}, headers=ORIGIN)
    assert r.status_code == 200 and "Inscription supprimée" in r.text
    with db(client) as s:
        assert s.query(User).filter_by(email="part@exemple.fr").count() == 0


def test_quit_refused_for_active_account(client, env):
    adm = admin(client, env)
    set_places(adm, 0)
    _, r = register(client, env, "x@exemple.fr")
    jeton = re.search(r'name="jeton" value="([^"]+)"', r.text).group(1)
    with db(client) as s:
        uid = s.query(User).filter_by(email="x@exemple.fr").one().id
    adm.post(f"/compte/formateur/inscriptions/{uid}/activer", headers=ORIGIN)
    assert browser(client).post("/connexion/quitter", data={"jeton": jeton}, headers=ORIGIN).status_code == 400
    assert statut(client, "x@exemple.fr") == "actif"


def test_trainer_rights(client, env):
    adm = admin(client, env)
    adm.post("/compte/formateur/equipe", data={"email": "prof@exemple.fr"}, headers=ORIGIN)
    prof = browser(client)
    login(prof, env, "prof@exemple.fr")
    student = browser(client)
    login(student, env, "etudiant@exemple.fr")
    # même tableau de bord, inscriptions et accès offerts que l'administrateur…
    for path in ("/compte/formateur", "/compte/formateur/inscriptions", "/compte/formateur/acces"):
        assert prof.get(path).status_code == 200, path
        assert student.get(path).status_code == 403, path
    page = prof.get("/compte/formateur").text
    assert "etudiant@exemple.fr" in page and "prof@exemple.fr" not in page
    assert "Tableau de bord formateur" in prof.get("/compte/").text
    assert "Éditer les formations" not in prof.get("/compte/").text
    # …mais ni l'équipe ni l'éditeur des formations
    assert prof.get("/compte/formateur/equipe").status_code == 403
    assert prof.post("/compte/formateur/equipe", data={"email": "x@exemple.fr"}, headers=ORIGIN).status_code == 403
    assert prof.get("/compte/admin", follow_redirects=False).status_code == 403
    assert "Équipe" not in page and "Équipe" in adm.get("/compte/formateur").text
    # retrait : redevient un compte étudiant
    r = adm.post("/compte/formateur/equipe/retirer", data={"email": "prof@exemple.fr"}, headers=ORIGIN,
                 follow_redirects=False)
    assert r.status_code == 303 and prof.get("/compte/formateur").status_code == 403
    assert prof.get("/api/comptes/moi").status_code == 200
    assert adm.post("/compte/formateur/equipe/retirer", data={"email": "prof@exemple.fr"},
                    headers=ORIGIN).status_code == 404


def test_team_add_validation_and_waiting_trainer(client, env):
    adm = admin(client, env)
    set_places(adm, 0)
    _, r = register(client, env, "attend@exemple.fr")
    assert "liste d'attente" in r.text
    assert adm.post("/compte/formateur/equipe", data={"email": "pas-une-adresse"}, headers=ORIGIN).status_code == 400
    assert adm.post("/compte/formateur/equipe", data={"email": "admin@exemple.fr"}, headers=ORIGIN).status_code == 400
    adm.post("/compte/formateur/equipe", data={"email": "attend@exemple.fr"}, headers=ORIGIN)
    assert statut(client, "attend@exemple.fr") == "actif"
    r = adm.post("/compte/formateur/equipe", data={"email": "attend@exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 400 and "déjà partie" in r.text

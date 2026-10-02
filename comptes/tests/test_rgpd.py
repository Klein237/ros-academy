"""Droits des utilisateurs : export des données, suppression du compte, pages légales."""

import json
from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy import func, select

import academy_comptes.app as appmod
from academy_comptes.db import Certificate, Exercise, LoginToken, QcmAttempt, SessionRow, User
from test_app import BASE, ORIGIN, client, db, env, login  # noqa: F401 (fixtures)
from test_certificats import finish, get_cert


def count(client, model):
    with db(client) as s:
        return s.scalar(select(func.count()).select_from(model))


def test_export_contains_the_student_data_only(client, env):
    login(client, env, "bob@exemple.fr")  # un autre étudiant, qui ne doit pas apparaître
    c2 = TestClient(client.app, base_url=BASE)
    login(c2, env, "alice@exemple.fr")
    finish(c2, env, "u2")
    get_cert(c2, nom="Alice Martin")
    r = c2.get("/compte/donnees")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = json.loads(r.text)
    assert data["compte"]["email"] == "alice@exemple.fr"
    assert {q["module"] for q in data["qcm"]} == {"01-a", "02-b"}
    assert [e["module"] for e in data["exercices"]] == ["01-a", "02-b"]
    assert data["certificats"][0]["nom"] == "Alice Martin"
    assert "bob@exemple.fr" not in r.text
    anon = TestClient(client.app, base_url=BASE)
    assert anon.get("/compte/donnees", follow_redirects=False).status_code == 303


def test_delete_account_erases_everything_and_the_lab(client, env):
    login(client, env)
    finish(client, env, "u1")
    code = get_cert(client).headers["location"].rsplit("/", 1)[1]
    assert count(client, Certificate) == 1 and count(client, QcmAttempt) == 2
    page = client.get("/compte/supprimer")
    assert "définitive" in page.text
    # confirmation obligatoire, même origine obligatoire
    assert client.post("/compte/supprimer", data={"confirmation": "eleve@exemple.fr"}).status_code == 403
    r = client.post("/compte/supprimer", data={"confirmation": "autre@exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 400 and count(client, User) == 1
    r = client.post("/compte/supprimer", data={"confirmation": " Eleve@Exemple.fr "}, headers=ORIGIN)
    assert r.status_code == 200 and "Compte supprimé" in r.text
    assert env["hub"].deleted == ["u1"]
    for model in (User, Certificate, QcmAttempt, Exercise, SessionRow, LoginToken):
        assert count(client, model) == 0, model.__name__
    anon = TestClient(client.app, base_url=BASE)
    assert anon.get(f"/certificats/{code}").status_code == 404
    assert client.get("/compte/", follow_redirects=False).status_code == 303  # session effacée


def test_delete_refused_while_subscribed_or_when_the_hub_fails(client, env):
    login(client, env)
    with db(client) as s:
        u = s.scalar(select(User))
        u.stripe_subscription_id, u.abonnement_statut, u.formule = "sub_1", "active", "pro"
        s.commit()
    r = client.post("/compte/supprimer", data={"confirmation": "eleve@exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 409 and "résiliez-le d" in r.text and count(client, User) == 1
    with db(client) as s:
        s.scalar(select(User)).abonnement_resilie = True  # résilié : fin de période, plus de facturation
        s.commit()
    env["hub"].fail_delete = True
    r = client.post("/compte/supprimer", data={"confirmation": "eleve@exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 502 and count(client, User) == 1  # rien n'est supprimé à moitié
    env["hub"].fail_delete = False
    r = client.post("/compte/supprimer", data={"confirmation": "eleve@exemple.fr"}, headers=ORIGIN)
    assert r.status_code == 200 and count(client, User) == 0


def test_legal_pages(env):  # noqa: F811
    def pages(settings):
        app = appmod.create_app(settings, hub=env["hub"], contenus=env["contenus"], background=False)
        c = TestClient(app, base_url=BASE)
        return c.get("/mentions-legales").text, c.get("/confidentialite").text

    mentions, conf = pages(env["settings"])
    assert "[à compléter : nom ou raison sociale — EDITEUR_NOM]" in mentions
    assert "Mentions légales" in mentions and "Confidentialité" in mentions  # liens du pied de page
    assert "/compte/supprimer" in conf and "14 jours" in conf and "cnil.fr" in conf
    filled = replace(env["settings"], editeur_nom="Klein Formation", editeur_adresse="1 rue de la Paix, Paris",
                     editeur_contact="contact@exemple.fr", hebergeur="Hetzner Online GmbH", sauvegarde_jours=30)
    mentions, conf = pages(filled)
    assert "à compléter" not in mentions and "Klein Formation" in mentions and "mailto:contact@exemple.fr" in mentions
    assert "30 jours" in conf and "à compléter" not in conf


def test_account_page_links_to_the_rights(client, env):
    login(client, env)
    page = client.get("/compte/").text
    assert "/compte/donnees" in page and "/compte/supprimer" in page


def test_hub_client_stops_then_deletes_the_user():
    import httpx

    from academy_comptes.clients import HubClient, UpstreamError

    calls, state = [], {"server": True, "exists": True}

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "DELETE" and request.url.path.endswith("/server"):
            state["server"] = False
            return httpx.Response(202)
        if request.method == "GET":
            if not state["exists"]:
                return httpx.Response(404)
            return httpx.Response(200, json={"servers": {"": {}} if state["server"] else {}})
        if request.method == "DELETE":
            state["exists"] = False
            return httpx.Response(204)
        return httpx.Response(500)

    hub = HubClient("http://hub:8000", "t", http=httpx.Client(transport=httpx.MockTransport(handler)))
    hub.delete_user("u3")
    assert calls[0] == ("DELETE", "/hub/api/users/u3/server") and calls[-1] == ("DELETE", "/hub/api/users/u3")
    hub.delete_user("u3")  # plus d'utilisateur au Hub : rien à faire, pas d'erreur

    def refuse(request):
        if request.method == "GET":
            return httpx.Response(200, json={"servers": {}})
        return httpx.Response(202 if request.url.path.endswith("/server") else 400)

    broken = HubClient("http://hub:8000", "t", http=httpx.Client(transport=httpx.MockTransport(refuse)))
    try:
        broken.delete_user("u4")
        raise AssertionError("refus du Hub ignoré")
    except UpstreamError:
        pass

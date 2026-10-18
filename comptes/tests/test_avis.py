"""Avis des étudiants sur les modules : enregistrement, droits, tableau de bord formateur."""

import json

from fastapi.testclient import TestClient

from test_app import BASE, ORIGIN, client, env, login  # noqa: F401 (fixtures)

AVIS = {"note": 4, "difficulte": "adaptee", "commentaire": "Clair, mais l'indice 2 m'a manqué."}


def browser(client, env, email):
    b = TestClient(client.app, base_url=BASE)
    login(b, env, email)
    return b


def test_feedback_is_saved_and_replaced(client, env):
    assert client.get("/api/comptes/avis/01-a").status_code == 401
    login(client, env)
    assert client.get("/api/comptes/avis/01-a").json() == {"avis": None}
    r = client.post("/api/comptes/avis/01-a", json=AVIS, headers=ORIGIN)
    assert r.status_code == 200 and r.json()["avis"]["note"] == 4
    client.post("/api/comptes/avis/01-a", json={**AVIS, "note": 2, "difficulte": "trop_difficile"}, headers=ORIGIN)
    saved = client.get("/api/comptes/avis/01-a").json()["avis"]
    assert (saved["note"], saved["difficulte"], saved["commentaire"]) == (2, "trop_difficile", AVIS["commentaire"])
    export = json.loads(client.get("/compte/donnees").text)
    assert export["avis"][0]["module"] == "01-a" and export["avis"][0]["note"] == 2


def test_feedback_is_validated(client, env):
    login(client, env)
    assert client.post("/api/comptes/avis/01-a", json=AVIS).status_code == 403  # sans Origin
    for bad in ({**AVIS, "note": 0}, {**AVIS, "note": 6}, {**AVIS, "difficulte": "moyen"},
                {**AVIS, "commentaire": "x" * 2001}):
        assert client.post("/api/comptes/avis/01-a", json=bad, headers=ORIGIN).status_code == 400, bad
    assert client.post("/api/comptes/avis/99-absent", json=AVIS, headers=ORIGIN).status_code == 404
    assert client.post("/api/comptes/avis/..%2Fx", json=AVIS, headers=ORIGIN).status_code == 404


def test_trainer_reads_feedback(client, env):
    alice = browser(client, env, "alice@exemple.fr")
    bob = browser(client, env, "bob@exemple.fr")
    alice.post("/api/comptes/avis/01-a", json=AVIS, headers=ORIGIN)
    bob.post("/api/comptes/avis/01-a", json={"note": 1, "difficulte": "trop_difficile",
                                            "commentaire": "=HYPERLINK(\"x\")"}, headers=ORIGIN)
    trainer = browser(client, env, "admin@exemple.fr")
    trainer.post("/api/comptes/avis/01-a", json={**AVIS, "note": 5}, headers=ORIGIN)  # l'équipe n'est pas comptée
    assert alice.get("/compte/formateur/avis").status_code == 403
    html = trainer.get("/compte/formateur").text
    assert "2,5 / 5" in html and "(2 avis, 1 trop difficile)" in html
    page = trainer.get("/compte/formateur/avis?module=01-a").text
    assert "Clair, mais l&#39;indice 2 m&#39;a manqué." in page and "2 avis" in page
    assert "admin@exemple.fr" not in page
    csv = trainer.get("/compte/formateur/avis.csv").text
    assert "01-a;Module A;alice@exemple.fr" in csv and "'=HYPERLINK" in csv  # pas de formule dans le tableur

"""Tableau de bord formateur : données construites par l'API, comme par de vrais étudiants."""

import csv
import io
import re

from fastapi.testclient import TestClient

from academy_comptes.db import Exercise
from test_app import BASE, ORIGIN, client, db, env, login  # noqa: F401 (fixtures)

QCM_20 = {"reponses": {"q1": [0], "q2": [1]}}
QCM_10 = {"reponses": {"q1": [0]}}


def browser(client):
    return TestClient(client.app, base_url=BASE)


def build(client, env):
    """Parcours de test : 01-a (coef 1) et 02-b (coef 3). Trois étudiants et le formateur."""
    a = browser(client)  # u1 : parcours terminé
    login(a, env, "alice@exemple.fr")
    b = browser(client)  # u2 : bloqué sur 01-a
    login(b, env, "bob@exemple.fr")
    c = browser(client)  # u3 : inscrit, rien fait
    login(c, env, "=cmd|calc@exemple.fr")
    for module in ("01-a", "02-b"):
        env["contenus"].verdicts[(module, "u1")] = {"ok": True, "code": 0, "journal": "ok"}
    a.post("/api/comptes/qcm/01-a", json=QCM_20, headers=ORIGIN)  # 20
    a.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN)  # 1 vérification → 20 → module 20
    a.post("/api/comptes/qcm/02-b", json=QCM_10, headers=ORIGIN)  # 10
    a.post("/api/comptes/qcm/02-b", json=QCM_20, headers=ORIGIN)  # meilleure : 20
    a.post("/api/comptes/exercices/02-b/indices/1", headers=ORIGIN)
    a.post("/api/comptes/exercices/02-b/indices/2", headers=ORIGIN)
    env["contenus"].verdicts[("02-b", "u1")] = {"ok": False, "code": 1, "journal": "non"}
    a.post("/api/comptes/exercices/02-b/verification", headers=ORIGIN)
    env["contenus"].verdicts[("02-b", "u1")] = {"ok": True, "code": 0, "journal": "ok"}
    a.post("/api/comptes/exercices/02-b/verification", headers=ORIGIN)  # 2e essai, 2 indices → 14 → module 17
    b.post("/api/comptes/qcm/01-a", json=QCM_10, headers=ORIGIN)
    b.post("/api/comptes/exercices/01-a/indices/1", headers=ORIGIN)
    for _ in range(3):
        b.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN)  # 3 échecs : bloqué
    trainer = browser(client)
    login(trainer, env, "admin@exemple.fr")
    return trainer, b


def test_trainer_only(client, env):
    trainer, student = build(client, env)
    assert student.get("/compte/formateur").status_code == 403
    assert student.get("/compte/formateur/etudiants.csv").status_code == 403
    assert student.get("/compte/formateur/etudiants/1").status_code == 403
    anon = browser(client)
    r = anon.get("/compte/formateur", follow_redirects=False)
    assert r.status_code == 303 and "/connexion?suite=" in r.headers["location"]
    assert "Tableau de bord formateur" in trainer.get("/compte/").text
    assert "Tableau de bord formateur" not in student.get("/compte/").text


def test_overview_and_module_stats(client, env):
    trainer, _ = build(client, env)
    env["hub"].servers = {"u1": True, "u2": False, "test-e2e": True}
    html = trainer.get("/compte/formateur").text
    tiles = dict((label, value) for value, label in
                 re.findall(r'<span class="tile-value">([^<]*)</span><span class="tile-label">([^<]*)</span>', html))
    assert tiles == {"étudiants inscrits": "3", "actifs ces 7 derniers jours": "3", "labs en cours": "2",
                     "minutes de lab ce mois-ci": "0", "parcours terminés": "1", "en formule pro": "0"}
    rows = re.findall(r"<tr>\s*<td><a href=\"/modules/([^/]+)/\">.*?</tr>", html, re.S)
    assert rows == ["01-a", "02-b"]
    row_a = re.search(r'href="/modules/01-a/".*?</tr>', html, re.S).group(0)
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td>(.*?)</td>", row_a, re.S)]
    # commencé 2 (alice, bob) ; réussi 1/2 ; bloqués 1 ; 1 vérification avant réussite ; indices 1/0/0 ;
    # QCM moyen (20 + 10) / 2 = 15 ; note moyenne des modules terminés : 20
    assert cells == ["2", "1 / 2 · 50 %", "1", "1,0", "1 / 0 / 0", "15,0 / 20", "20,00 / 20"]
    row_b = re.search(r'href="/modules/02-b/".*?</tr>', html, re.S).group(0)
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td>(.*?)</td>", row_b, re.S)]
    assert cells == ["1", "1 / 1 · 100 %", "0", "2,0", "1 / 1 / 0", "20,0 / 20", "17,00 / 20"]
    assert "admin@exemple.fr" not in html  # le formateur n'est pas compté parmi les étudiants
    assert "bloqué sur Module A" in html


def test_students_search_and_detail(client, env):
    trainer, _ = build(client, env)
    html = trainer.get("/compte/formateur", params={"q": "ALICE"}).text
    assert "alice@exemple.fr" in html and "bob@exemple.fr" not in html and "1 sur 3 étudiants" in html
    # alice : (20 × 1 + 17 × 3) / 4 = 17,75
    assert "<strong>17,75</strong> / 20" in html
    detail = trainer.get("/compte/formateur/etudiants/2").text
    assert "bob@exemple.fr" in detail and "<strong class=\"warn\">bloqué</strong>" in detail
    assert "10,0" in detail and "(1/2)" in detail and "1 / 3" in detail
    assert trainer.get("/compte/formateur/etudiants/99").status_code == 404
    assert trainer.get("/compte/formateur/etudiants/4").status_code == 404  # le formateur lui-même


def test_csv_export_is_spreadsheet_safe(client, env):
    trainer, _ = build(client, env)
    r = trainer.get("/compte/formateur/etudiants.csv")
    assert r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    assert r.text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿")), delimiter=";"))
    header, data = rows[0], {row[1]: dict(zip(rows[0], row)) for row in rows[1:]}
    assert header[:9] == ["id", "email", "nom", "formule", "inscrit le", "dernière activité", "minutes ce mois",
                          "modules terminés", "note finale"]
    assert data["alice@exemple.fr"]["note finale"] == "17,75"
    assert data["alice@exemple.fr"]["02-b indices"] == "2" and data["alice@exemple.fr"]["02-b vérifications"] == "2"
    assert data["bob@exemple.fr"]["01-a vérifications"] == "3" and data["bob@exemple.fr"]["note finale"] == ""
    # une adresse qui commence par « = » ne devient pas une formule dans le tableur
    assert "'=cmd|calc@exemple.fr" in data
    assert len(data) == 3


def test_verifications_are_counted(client, env):
    login(client, env)
    for _ in range(2):
        client.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN)
    with db(client) as s:
        assert s.get(Exercise, (1, "01-a")).verifications == 2

"""Tableau de bord « Mon apprentissage » : minutes par semaine, questions, badges, page en noir et or."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from academy_comptes import tableau
from academy_comptes.db import UsageTick, User
from test_app import BASE, ORIGIN, client, db, env, login, succeed  # noqa: F401 (fixtures)


def test_weekly_minutes_and_chart(client, env):
    login(client, env)
    now = datetime(2026, 10, 21, 15, 0)  # un mercredi
    lundi = datetime(2026, 10, 19)
    with db(client) as s:
        user = s.query(User).one()
        s.add_all([UsageTick(user_id=user.id, minute=lundi + timedelta(minutes=i)) for i in range(30)])  # cette semaine
        s.add_all([UsageTick(user_id=user.id, minute=lundi - timedelta(days=2, minutes=i)) for i in range(60)])  # la précédente
        s.add(UsageTick(user_id=user.id, minute=lundi - timedelta(weeks=8)))  # trop ancienne
        s.commit()
        semaines = tableau.weekly_minutes(s, user, now)
    assert len(semaines) == 8 and semaines[-1]["debut"] == lundi
    assert [w["minutes"] for w in semaines[-2:]] == [60, 30] and sum(w["minutes"] for w in semaines) == 90
    g = tableau.chart(semaines)
    barres = g["barres"]
    assert barres[-2]["hauteur"] == 156 and barres[-1]["hauteur"] == 78  # la plus haute occupe la hauteur utile
    assert barres[-2]["etiquette"] == "60 min" and barres[-1]["etiquette"] == "30 min" and barres[0]["etiquette"] == ""
    assert barres[0]["hauteur"] == 0 and g["total"] == 90 and barres[-1]["date"] == "19/10"
    assert tableau.chart([{"debut": lundi, "minutes": 0}])["barres"][0]["hauteur"] == 0  # aucun lab : pas de division par 0


def test_dashboard_page(client, env):
    login(client, env)
    page = client.get("/compte/apprentissage").text
    assert 'class="theme-noir-or"' in page and "Minutes de lab par semaine" in page
    assert "Votre moyenne apparaît dès votre premier module terminé." in page
    assert page.count('class="badge badge-a_faire"') == 2 and "Mes badges" in page
    assert "/static/contenus/icones/noeuds.webp" in page  # parcours sans objet dédié : le graphe de nœuds
    assert "style=" not in page  # CSP : aucun style en ligne
    # le lab s'ouvre depuis un module, pas depuis le tableau de bord ni la page du compte
    assert 'href="/compte/lab"' not in page and 'href="/compte/lab"' not in client.get("/compte/").text
    client.post("/api/comptes/qcm/01-a", json={"reponses": {"q1": [0], "q2": [1]}}, headers=ORIGIN)
    succeed(env, "01-a")
    client.post("/api/comptes/exercices/01-a/verification", headers=ORIGIN)
    client.post("/api/comptes/exercices/02-b/indices/1", headers=ORIGIN)
    page = client.get("/compte/apprentissage").text
    assert 'class="badge badge-termine"' in page and 'class="badge badge-en_cours"' in page
    assert "Au-dessus du seuil du certificat" in page and "Encore 1 module" in page
    assert '<span class="chiffre-label">Indices utilisés</span><span class="chiffre-valeur">1</span>' in page


def test_dashboard_questions(client, env):
    login(client, env)
    assert "« Je suis bloqué » pose votre question" in client.get("/compte/apprentissage").text
    q = client.post("/api/comptes/questions/02-b", json={"titre": "Rien ne bouge", "texte": "Le robot reste immobile."},
                    headers=ORIGIN).json()["question"]
    prof = TestClient(client.app, base_url=BASE)
    login(prof, env, "admin@exemple.fr")
    prof.post(f"/api/comptes/questions/{q['id']}/reponses", json={"texte": "Regardez le nom du topic."}, headers=ORIGIN)
    page = client.get("/compte/apprentissage").text
    assert "1 posée · 1 avec une réponse de l'équipe" in page and 'href="/modules/02-b/#questions"' in page


def test_monthly_minutes_keep_history_across_months_and_years(client, env):
    login(client, env)
    now = datetime(2027, 1, 10, 12, 0)
    with db(client) as s:
        user = s.query(User).one()
        s.add_all([UsageTick(user_id=user.id, minute=datetime(2027, 1, 3) + timedelta(minutes=i)) for i in range(20)])
        s.add_all([UsageTick(user_id=user.id, minute=datetime(2026, 12, 31, 23) + timedelta(minutes=i)) for i in range(45)])
        s.add_all([UsageTick(user_id=user.id, minute=datetime(2026, 3, 15) + timedelta(minutes=i)) for i in range(7)])
        s.add(UsageTick(user_id=user.id, minute=datetime(2025, 12, 31)))  # plus de 12 mois : hors historique
        s.commit()
        mois = tableau.monthly_minutes(s, user, now)
    assert len(mois) == 12 and mois[0]["debut"] == datetime(2026, 2, 1) and mois[-1]["debut"] == datetime(2027, 1, 1)
    assert [m["minutes"] for m in mois] == [0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 45, 20]
    assert mois[-1]["libelle"] == "janv. 27" and mois[-2]["libelle"] == "déc." and mois[0]["libelle"] == "févr. 26"
    g = tableau.chart(mois, largeur=840)
    assert g["total"] == 72 and g["barres"][-2]["periode"] == "déc. 2026" and g["barres"][-1]["derniere"]


def test_lab_history_shown_to_student_and_trainer(client, env):
    login(client, env)
    with db(client) as s:
        user = s.query(User).one()
        uid = user.id
        il_y_a_deux_mois = tableau.add_months(tableau.month_start(datetime.utcnow()), -2) + timedelta(days=3)
        s.add_all([UsageTick(user_id=uid, minute=il_y_a_deux_mois + timedelta(minutes=i)) for i in range(25)])
        s.commit()
    page = client.get("/compte/apprentissage").text
    # le mois en cours repart à zéro pour le quota, mais les mois précédents restent visibles
    assert "Le lab, mois par mois" in page and "25 min au total" in page and "l'historique est conservé" in page
    assert "style=" not in page
    prof = TestClient(client.app, base_url=BASE)
    login(prof, env, "admin@exemple.fr")
    page = prof.get(f"/compte/formateur/etudiants/{uid}").text
    assert "Temps de lab, mois par mois" in page and "25 min au total" in page

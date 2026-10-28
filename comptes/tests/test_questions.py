"""Questions et réponses sur les modules : visibilité, équipe, résolution, modération, e-mails."""

import json
import re
from datetime import timedelta

from fastapi.testclient import TestClient

from academy_comptes.db import utcnow
from test_app import BASE, ORIGIN, client, db, env, login, signup  # noqa: F401 (fixtures)

Q = {"titre": "Le robot ne bouge pas", "texte": "J'ai lancé le nœud mais rien.\n```\nros2 run my_pkg n\n```"}


def browser(client, env, email, nom=None):
    b = TestClient(client.app, base_url=BASE)
    if nom:
        signup(b, email, nom=nom)
        _, link, _ = env["sent"][-1]
        b.get(link.replace(BASE, ""), follow_redirects=False)
    else:
        login(b, env, email)
    return b


def post(b, url, body=None):
    return b.post(url, json=body or {}, headers=ORIGIN)


def test_ask_answer_resolve(client, env):
    alice = browser(client, env, "alice@exemple.fr", nom="Alice Martin")
    bob = browser(client, env, "bob@exemple.fr", nom="Bob Durand")
    prof = browser(client, env, "admin@exemple.fr", nom="Claire Prof")
    assert client.get("/api/comptes/questions/01-a").status_code == 401
    r = post(alice, "/api/comptes/questions/01-a", Q)
    assert r.status_code == 200
    q = r.json()["question"]
    assert q["auteur"] == "Alice" and q["moi"] and not q["resolue"] and "journal" not in q
    # visible des autres étudiants, avec le prénom seulement
    seen = bob.get("/api/comptes/questions/01-a").json()
    assert [x["titre"] for x in seen["questions"]] == ["Le robot ne bouge pas"]
    assert "alice@" not in json.dumps(seen) and "Martin" not in json.dumps(seen) and not seen["equipe"]
    # un étudiant répond, puis l'équipe : sa réponse passe en premier, l'auteur est prévenu
    post(bob, f"/api/comptes/questions/{q['id']}/reponses", {"texte": "As-tu sourcé install/setup.bash ?"})
    env["sent"].clear()
    r = post(prof, f"/api/comptes/questions/{q['id']}/reponses", {"texte": "Le topic est cmd_vel, pas cmd_vell."})
    rep = r.json()["question"]["reponses"]
    assert [a["auteur"] for a in rep] == ["Claire", "Bob"] and rep[0]["equipe"] and not rep[1]["equipe"]
    assert env["sent"][0][0] == "alice@exemple.fr" and env["sent"][0][2] == "nouvelle_reponse"
    assert env["sent"][0][1].endswith(f"/modules/01-a/#question-{q['id']}")
    # l'équipe valide la réponse de Bob ; seule Alice (ou l'équipe) marque la question résolue
    post(prof, f"/api/comptes/reponses/{rep[1]['id']}/valider", {"valeur": True})
    assert post(bob, f"/api/comptes/reponses/{rep[1]['id']}/valider").status_code == 403
    assert post(bob, f"/api/comptes/questions/{q['id']}/resolue").status_code == 403
    r = post(alice, f"/api/comptes/questions/{q['id']}/resolue", {"valeur": True})
    assert r.json()["question"]["resolue"] and r.json()["question"]["reponses"][1]["validee"]


def test_private_question_and_attached_verification(client, env):
    alice = browser(client, env, "alice@exemple.fr", nom="Alice")
    bob = browser(client, env, "bob@exemple.fr", nom="Bob")
    prof = browser(client, env, "admin@exemple.fr", nom="Prof")
    env["contenus"].verdicts[("01-a", "u1")] = {"ok": False, "code": 1, "journal": "Le robot n'avance pas."}
    post(alice, "/api/comptes/exercices/01-a/verification")
    r = post(alice, "/api/comptes/questions/01-a", {**Q, "prive": True, "solution": True,
                                                    "joindre_verification": True})
    qid = r.json()["question"]["id"]
    assert bob.get("/api/comptes/questions/01-a").json()["questions"] == []
    assert post(bob, f"/api/comptes/questions/{qid}/reponses", {"texte": "x"}).status_code == 404
    staff_view = prof.get("/api/comptes/questions/01-a").json()
    assert staff_view["equipe"] and staff_view["questions"][0]["journal"] == "Le robot n'avance pas."
    assert "journal" not in alice.get("/api/comptes/questions/01-a").json()["questions"][0]


def test_validation_limits_and_moderation(client, env):
    alice = browser(client, env, "alice@exemple.fr", nom="Alice")
    bob = browser(client, env, "bob@exemple.fr", nom="Bob")
    prof = browser(client, env, "admin@exemple.fr", nom="Prof")
    assert alice.post("/api/comptes/questions/01-a", json=Q).status_code == 403  # sans Origin
    for bad in ({**Q, "titre": " "}, {**Q, "titre": "x" * 151}, {**Q, "texte": "x" * 5001}):
        assert post(alice, "/api/comptes/questions/01-a", bad).status_code == 400
    assert post(alice, "/api/comptes/questions/99-absent", Q).status_code == 404
    qid = post(alice, "/api/comptes/questions/01-a", Q).json()["question"]["id"]
    assert post(bob, f"/api/comptes/questions/{qid}/signaler").json() == {"signale": True}
    assert "Messages signalés" in prof.get("/compte/formateur/questions").text
    assert post(bob, f"/api/comptes/questions/{qid}/masquer", {"valeur": True}).status_code == 403
    post(prof, f"/api/comptes/questions/{qid}/masquer", {"valeur": True})
    assert bob.get("/api/comptes/questions/01-a").json()["questions"] == []
    assert prof.get("/api/comptes/questions/01-a").json()["questions"][0]["masquee"]
    for _ in range(9):
        post(alice, "/api/comptes/questions/01-a", Q)
    r = post(alice, "/api/comptes/questions/01-a", Q)
    assert r.status_code == 400 and "demain" in r.json()["erreur"]


def test_trainer_page_digest_and_rgpd(client, env):
    alice = browser(client, env, "alice@exemple.fr", nom="Alice")
    prof = browser(client, env, "admin@exemple.fr", nom="Prof")
    assert alice.get("/compte/formateur/questions").status_code == 403
    qid = post(alice, "/api/comptes/questions/01-a", Q).json()["question"]["id"]
    with db(client) as s:
        from academy_comptes.db import Question
        s.get(Question, qid).cree_le = utcnow() - timedelta(hours=30)
        s.commit()
    page = prof.get("/compte/formateur/questions").text
    assert "Le robot ne bouge pas" in page and '<strong class="warn">30 h</strong>' in page
    assert "Questions (1 sans réponse)" in prof.get("/compte/formateur").text
    post(alice, "/api/comptes/questions/01-a", {**Q, "titre": "Autre question"})
    # récapitulatif : au plus un par heure, aux formateurs
    env["sent"].clear()
    now = utcnow()
    assert client.app.state.questions_digest(now) == 1
    assert env["sent"] == [("admin@exemple.fr", f"{BASE}/compte/formateur/questions", "questions")]
    assert client.app.state.questions_digest(now + timedelta(minutes=30)) == 0
    assert client.app.state.questions_digest(now + timedelta(hours=2)) == 0  # rien de nouveau
    post(prof, f"/api/comptes/questions/{qid}/reponses", {"texte": "Réponse"})
    assert "Le robot ne bouge pas" not in prof.get("/compte/formateur/questions").text
    export = json.loads(alice.get("/compte/donnees").text)
    assert len(export["questions"]) == 2 and export["reponses"] == []
    assert re.search(r"Aucune question en attente|Autre question", prof.get("/compte/formateur/questions").text)


def test_same_question_counts_and_notifies_on_team_answer(client, env):
    alice = browser(client, env, "alice@exemple.fr", nom="Alice")
    bob = browser(client, env, "bob@exemple.fr", nom="Bob")
    chloe = browser(client, env, "chloe@exemple.fr", nom="Chloé")
    prof = browser(client, env, "admin@exemple.fr", nom="Prof")
    qid = post(alice, "/api/comptes/questions/01-a", Q).json()["question"]["id"]
    assert post(alice, f"/api/comptes/questions/{qid}/meme", {"valeur": True}).status_code == 400  # la sienne
    r = post(bob, f"/api/comptes/questions/{qid}/meme", {"valeur": True})
    assert r.json()["question"]["meme"] == 1 and r.json()["question"]["moi_meme"]
    post(bob, f"/api/comptes/questions/{qid}/meme", {"valeur": True})  # deux fois : compté une fois
    post(chloe, f"/api/comptes/questions/{qid}/meme", {"valeur": True})
    seen = alice.get("/api/comptes/questions/01-a").json()["questions"][0]
    assert seen["meme"] == 2 and not seen["moi_meme"]
    assert "2 étudiants de plus ont la même question" in prof.get("/compte/formateur/questions").text
    post(chloe, f"/api/comptes/questions/{qid}/meme", {"valeur": False})
    assert alice.get("/api/comptes/questions/01-a").json()["questions"][0]["meme"] == 1
    # réponse d'un étudiant : seul l'auteur est prévenu ; réponse de l'équipe : ceux qui suivent aussi
    env["sent"].clear()
    post(chloe, f"/api/comptes/questions/{qid}/reponses", {"texte": "Moi aussi, aucune idée."})
    assert [(e, s) for e, _, s in env["sent"]] == [("alice@exemple.fr", "nouvelle_reponse")]
    env["sent"].clear()
    post(prof, f"/api/comptes/questions/{qid}/reponses", {"texte": "Vérifiez le nom du topic."})
    assert sorted((e, s) for e, _, s in env["sent"]) == [("alice@exemple.fr", "nouvelle_reponse"),
                                                          ("bob@exemple.fr", "meme_question")]
    assert json.loads(bob.get("/compte/donnees").text)["meme_question"] == [qid]


def test_team_question_is_listed_apart(client, env):
    # un formateur qui teste la formation pose une question : à part de celles des étudiants
    alice = browser(client, env, "alice@exemple.fr", nom="Alice")
    prof = browser(client, env, "admin@exemple.fr", nom="Prof")
    post(alice, "/api/comptes/questions/01-a", Q)
    post(prof, "/api/comptes/questions/01-a", {**Q, "titre": "Question de test du formateur"})
    etudiants = prof.get("/compte/formateur/questions").text
    assert "Le robot ne bouge pas" in etudiants and "Question de test du formateur" not in etudiants
    assert "Équipe (1 sans réponse)" in etudiants
    equipe = prof.get("/compte/formateur/questions", params={"qui": "equipe"}).text
    assert "Question de test du formateur" in equipe and "Le robot ne bouge pas" not in equipe
    assert "Questions de l&#39;équipe" in equipe and "Étudiants (1 sans réponse)" in equipe
    assert "Questions (1 sans réponse)" in prof.get("/compte/formateur").text  # étudiants seulement
    tableau = prof.get("/compte/formateur", params={"qui": "equipe"}).text
    assert 'href="/compte/formateur/questions?qui=equipe">Questions (1 sans réponse)' in tableau
    # sur la page du module, elle est visible de tous, comme une autre
    titres = [q["titre"] for q in alice.get("/api/comptes/questions/01-a").json()["questions"]]
    assert "Question de test du formateur" in titres
    assert alice.get("/compte/formateur/questions", params={"qui": "equipe"}).status_code == 403

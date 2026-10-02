"""Certificats : éligibilité, émission figée, page publique, PDF, révocation."""

import io
import re

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from academy_comptes import certificats
from academy_comptes.certificats import CertificateError, clean_name, format_code, mention, normalize_code
from academy_comptes.db import Certificate
from test_app import BASE, ORIGIN, client, db, env, login  # noqa: F401 (fixtures)

QCM_20 = {"reponses": {"q1": [0], "q2": [1]}}


def browser(client):
    return TestClient(client.app, base_url=BASE)


def finish(client, env, student, qcm=QCM_20, hints=0):
    """Termine les deux modules du parcours de test (01-a coef 1, 02-b coef 3)."""
    for module in ("01-a", "02-b"):
        client.post(f"/api/comptes/qcm/{module}", json=qcm, headers=ORIGIN)
        for n in range(1, hints + 1):
            client.post(f"/api/comptes/exercices/{module}/indices/{n}", headers=ORIGIN)
        env["contenus"].verdicts[(module, student)] = {"ok": True, "code": 0, "journal": "ok"}
        client.post(f"/api/comptes/exercices/{module}/verification", headers=ORIGIN)


def get_cert(client, nom="Élodie N'Diaye-Martin"):
    r = client.post("/compte/certificats", data={"parcours": "ros2", "nom": nom}, headers=ORIGIN,
                    follow_redirects=False)
    return r


# --- Règles

@pytest.mark.parametrize("note,expected", [(20, "Très bien"), (16, "Très bien"), (15.99, "Bien"), (14, "Bien"),
                                           (12, "Assez bien"), (11.99, ""), (10, "")])
def test_mention(note, expected):
    assert mention(note) == expected


@pytest.mark.parametrize("name", ["Élodie N'Diaye-Martin", "Jean-Pierre O’Neil", "M. Ngono", "Zoé", "李明"])
def test_valid_names(name):
    assert clean_name(f"  {name}  ") == name


@pytest.mark.parametrize("name", ["", "A", "x" * 81, "<b>Jean</b>", "Jean 2", "-Jean", "Jean_Paul", "Jean; DROP",
                                  "=HYPERLINK(1)"])
def test_invalid_names(name):
    with pytest.raises(CertificateError):
        clean_name(name)


def test_codes_are_random_readable_and_normalized():
    codes = {certificats.new_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(re.fullmatch(r"[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{16}", c) for c in codes)
    code = next(iter(codes))
    assert normalize_code(format_code(code).lower()) == code
    assert normalize_code("ABC") is None and normalize_code("0" * 16) is None and normalize_code("../etc") is None


# --- Émission

def test_not_finished_or_below_threshold_is_refused(client, env):
    login(client, env)
    page = client.get("/compte/resultats").text
    assert "Un certificat est délivré quand le parcours est terminé" in page
    r = get_cert(client)
    assert r.status_code == 303 and "Terminez%20tous%20les%20modules" in r.headers["location"]
    finish(client, env, "u1", qcm={"reponses": {}}, hints=3)  # QCM 0, exercices 11 → modules 5,5
    assert "au moins 10 / 20" in client.get("/compte/resultats").text
    r = get_cert(client)
    assert "au%20moins%2010" in r.headers["location"]
    with db(client) as s:
        assert s.query(Certificate).count() == 0


def test_issue_freezes_name_grade_and_modules(client, env):
    login(client, env)
    assert client.post("/compte/certificats", data={"parcours": "ros2", "nom": "X Y"}).status_code == 403  # Origin
    finish(client, env, "u1")
    page = client.get("/compte/resultats").text
    assert "vous pouvez obtenir votre certificat" in page
    bad = get_cert(client, nom="<script>")
    assert "Indiquez%20votre%20nom" in bad.headers["location"]
    r = get_cert(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/certificats/")
    code = r.headers["location"].rsplit("/", 1)[1]
    with db(client) as s:
        cert = s.get(Certificate, code)
        assert (cert.nom, cert.note, cert.mention, cert.parcours_titre) == (
            "Élodie N'Diaye-Martin", 20.0, "Très bien", "ROS 2 Fondamentaux")
        assert certificats.modules(cert) == [{"titre": "Module A", "coef": 1, "note": 20.0},
                                             {"titre": "Module B", "coef": 3, "note": 20.0}]
    # un seul certificat par parcours
    assert "d%C3%A9j%C3%A0%20un%20certificat" in get_cert(client, nom="Autre Nom").headers["location"]
    assert "Télécharger le certificat (PDF)" in client.get("/compte/resultats").text


def test_public_page_and_pdf(client, env):
    login(client, env)
    finish(client, env, "u1", hints=1)  # exercices 17 → modules 18,5
    code = get_cert(client).headers["location"].rsplit("/", 1)[1]
    anon = browser(client)
    page = anon.get(f"/certificats/{code}")
    assert page.status_code == 200
    assert "Certificat authentique" in page.text and "Élodie N&#39;Diaye-Martin" in page.text
    assert "18,50 / 20" in page.text and "mention Très bien" in page.text
    assert "eleve@exemple.fr" not in page.text  # jamais l'adresse e-mail
    assert "Télécharger le PDF" not in page.text  # seulement pour son titulaire
    # le numéro tel qu'imprimé (avec tirets, minuscules) mène à la page
    r = anon.get(f"/certificats/{format_code(code).lower()}", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"] == f"/certificats/{code}"
    assert anon.get("/certificats/AAAAAAAAAAAAAAAA").status_code == 404
    pdf = anon.get(f"/certificats/{code}.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    for expected in ("Certificat de réussite", "Élodie N'Diaye-Martin", "ROS 2 Fondamentaux",
                     "Note finale : 18,50 / 20 — mention Très bien", format_code(code),
                     f"{BASE}/certificats/{code}", "Module B (coef. 3)"):
        assert expected in text, expected


def test_trainer_revokes(client, env):
    login(client, env)
    finish(client, env, "u1")
    code = get_cert(client).headers["location"].rsplit("/", 1)[1]
    assert client.post(f"/compte/formateur/certificats/{code}/revoquer", headers=ORIGIN).status_code == 403
    trainer = browser(client)
    login(trainer, env, "admin@exemple.fr")
    assert f"n° {format_code(code)}" in trainer.get("/compte/formateur/etudiants/1").text
    assert trainer.post(f"/compte/formateur/certificats/{code}/revoquer", data={"motif": "plagiat"}).status_code == 403
    r = trainer.post(f"/compte/formateur/certificats/{code}/revoquer", data={"motif": "  plagiat   avéré "},
                     headers=ORIGIN, follow_redirects=False)
    assert r.status_code == 303
    anon = browser(client)
    page = anon.get(f"/certificats/{code}").text
    assert "Certificat révoqué" in page and "Certificat authentique" not in page
    assert anon.get(f"/certificats/{code}.pdf").status_code == 410
    assert "votre certificat a été révoqué" in client.get("/compte/resultats").text.lower()
    with db(client) as s:
        assert s.get(Certificate, code).revoque_motif == "plagiat avéré"

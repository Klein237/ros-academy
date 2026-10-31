"""Profil public des formateurs et page « Qui sommes-nous »."""

from test_app import ORIGIN, client, db, env, login  # noqa: F401 (fixtures)
from test_inscriptions import admin, browser


def profil(b, **champs):
    data = {"nom": "", "titre": "", "linkedin": "", **champs}
    return b.post("/compte/formateur/profil", data=data, headers=ORIGIN)


def test_page_shows_founding_team_until_a_profile_is_published(client, env):
    page = browser(client).get("/qui-sommes-nous/").text
    assert "RoboForge est une formation Umoja Roboti" in page and 'aria-current="page">Qui sommes-nous' in page
    for nom in ("Ivan", "Yves Thoukam", "Franklin Yangoua"):
        assert nom in page
    assert 'href="https://www.linkedin.com/in/franklin-yangoua/"' in page
    assert browser(client).get("/qui-sommes-nous", follow_redirects=False).headers["location"] == "/qui-sommes-nous/"


def test_trainer_edits_own_profile(client, env):
    adm = admin(client, env)
    adm.post("/compte/formateur/equipe", data={"email": "prof@exemple.fr"}, headers=ORIGIN)
    prof = browser(client)
    login(prof, env, "prof@exemple.fr")
    assert 'href="/compte/formateur/profil"' in prof.get("/compte/formateur").text
    assert prof.get("/compte/formateur/profil").status_code == 200
    # brouillon : enregistré, pas encore affiché
    r = profil(prof, nom="Yves  Thoukam", titre="Ingénieur logiciel robotique",
               linkedin="https://www.linkedin.com/in/yves-thoukam-a57635207/")
    assert r.status_code == 200 and "Profil enregistré" in r.text and "Non affiché" in r.text
    page = browser(client).get("/qui-sommes-nous/").text
    assert "Ingénieur logiciel robotique" not in page and "Franklin Yangoua" in page
    # publié : remplace l'équipe par défaut, sans jamais montrer l'adresse
    r = profil(prof, nom="Yves Thoukam", titre="Ingénieur logiciel robotique",
               linkedin="https://www.linkedin.com/in/yves-thoukam-a57635207/", visible="1")
    assert r.status_code == 200
    page = browser(client).get("/qui-sommes-nous/").text
    assert "Yves Thoukam" in page and "Ingénieur logiciel robotique" in page and ">YT<" in page
    assert "Franklin Yangoua" not in page and "prof@exemple.fr" not in page
    assert prof.get("/compte/donnees").json()["profil_formateur"]["visible"] is True
    # retiré de l'équipe : son profil disparaît de la page
    adm.post("/compte/formateur/equipe/retirer", data={"email": "prof@exemple.fr"}, headers=ORIGIN)
    assert "Yves Thoukam" in browser(client).get("/qui-sommes-nous/").text  # équipe par défaut revenue
    assert "Ingénieur logiciel robotique" not in browser(client).get("/qui-sommes-nous/").text


def test_profile_is_validated_and_reserved_to_trainers(client, env):
    adm = admin(client, env)
    for champs, message in [({"linkedin": "javascript:alert(1)"}, "linkedin.com/in/"),
                            ({"linkedin": "https://exemple.fr/moi"}, "linkedin.com/in/"),
                            ({"visible": "1"}, "Indiquez votre nom"),
                            ({"nom": "x" * 81}, "80 caractères")]:
        r = profil(adm, **champs)
        assert r.status_code == 400 and message in r.text, champs
    assert "javascript:" not in browser(client).get("/qui-sommes-nous/").text
    etudiant = browser(client)
    login(etudiant, env, "etudiant@exemple.fr")
    assert etudiant.get("/compte/formateur/profil").status_code == 403
    assert profil(etudiant, nom="Moi", visible="1").status_code == 403
    assert profil(browser(client), nom="Moi").status_code in (401, 303)
    # sans en-tête d'origine : refusé (CSRF)
    assert adm.post("/compte/formateur/profil", data={"nom": "A"}).status_code in (400, 403)

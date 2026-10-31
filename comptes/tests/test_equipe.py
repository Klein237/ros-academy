"""Profil public des formateurs et page « Qui sommes-nous »."""

import io

from PIL import Image

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


def image(fmt="JPEG", size=(900, 600), exif=True):
    im = Image.new("RGB", size, (200, 120, 40))
    out = io.BytesIO()
    kwargs = {}
    if exif and fmt == "JPEG":
        e = Image.Exif()
        e[0x010F] = "Fabricant-secret"  # Make
        kwargs["exif"] = e.tobytes()
    im.save(out, fmt, **kwargs)
    return out.getvalue()


def envoyer(b, data, nom_fichier="moi.jpg", type_="image/jpeg", **champs):
    form = {"nom": "Franklin Yangoua", "titre": "", "linkedin": "", **champs}
    return b.post("/compte/formateur/profil", data=form, files={"photo": (nom_fichier, data, type_)}, headers=ORIGIN)


def test_photo_is_resized_stripped_and_shown(client, env):
    adm = admin(client, env)
    r = envoyer(adm, image())
    assert r.status_code == 200 and "Profil enregistré" in r.text
    import re
    url = re.search(r'src="(/compte/equipe/photos/\d+\.webp\?v=1)"', r.text).group(1)
    # brouillon : visible par son auteur seulement
    assert browser(client).get(url).status_code == 404
    photo = adm.get(url)
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/webp"
    with Image.open(io.BytesIO(photo.content)) as im:
        assert im.format == "WEBP" and im.size == (320, 320) and not im.getexif()
    assert b"Fabricant-secret" not in photo.content
    # publié : publique, en cache longue durée, et sur la page
    envoyer(adm, b"", nom_fichier="", visible="1")  # sans nouveau fichier, la photo reste
    r = browser(client).get(url)
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    page = browser(client).get("/qui-sommes-nous/").text
    assert f'src="{url}"' in page and 'alt="Photo de Franklin Yangoua"' in page
    # nouvelle photo : nouvelle adresse ; puis retrait
    r = envoyer(adm, image("PNG", (400, 800)), "moi.png", "image/png", visible="1")
    assert "photos/" in r.text and ".webp?v=2" in r.text
    r = adm.post("/compte/formateur/profil", data={"nom": "Franklin Yangoua", "visible": "1", "retirer_photo": "1"},
                 headers=ORIGIN)
    assert r.status_code == 200 and "/compte/equipe/photos/" not in r.text
    assert browser(client).get(url.replace("v=1", "v=2")).status_code == 404
    assert ">FY<" in browser(client).get("/qui-sommes-nous/").text


def test_photo_rejects_non_images_and_large_files(client, env):
    adm = admin(client, env)
    for data, nom_fichier, message in [(b"<svg onload=alert(1)></svg>", "x.svg", "pas une image lisible"),
                                       (b"GIF89a" + b"0" * 50, "x.gif", "pas une image lisible"),
                                       (image("GIF", exif=False), "x.gif", "JPEG, PNG ou WebP"),
                                       (b"0" * (5 * 1024 * 1024 + 10), "gros.jpg", "5 Mo au plus")]:
        r = envoyer(adm, data, nom_fichier)
        assert r.status_code == 400 and message in r.text, nom_fichier
    assert "/compte/equipe/photos/" not in adm.get("/compte/formateur/profil").text
    assert browser(client).get("/compte/equipe/photos/1.webp").status_code == 404

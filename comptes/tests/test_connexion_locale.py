"""Lien de confirmation à l'écran (test en local) et commande de test SMTP."""

import smtplib
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import academy_comptes.app as appmod
from academy_comptes import mail
from academy_comptes.settings import Settings
from test_app import SECRET, env  # noqa: F401 (fixture)

LOCAL = "https://localhost"


@pytest.mark.parametrize("url,smtp,flag,shown", [
    ("https://localhost", "", True, True),
    ("https://127.0.0.1:8443", "", True, True),
    ("https://localhost", "", False, False),
    ("https://localhost", "smtp.exemple.fr", True, False),  # un vrai envoi : pas de lien à l'écran
    ("https://academy.exemple.fr", "", True, False),  # en ligne : jamais
    ("https://localhost.exemple.fr", "", True, False),
])
def test_link_on_screen_only_locally_without_smtp(url, smtp, flag, shown):
    s = Settings(jwt_secret=SECRET, public_url=url, smtp_host=smtp, login_link_on_screen=flag)
    assert s.show_login_link is shown


def test_flag_read_from_environment(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("CONNEXION_LIEN_A_L_ECRAN", "1")
    assert Settings.from_env().show_login_link  # DOMAIN par défaut : localhost
    monkeypatch.setenv("DOMAIN", "academy.exemple.fr")
    assert not Settings.from_env().show_login_link


def page_after_request(env, settings):
    app = appmod.create_app(settings, hub=env["hub"], contenus=env["contenus"], background=False)
    c = TestClient(app, base_url=settings.public_url)
    return c, c.post("/connexion/inscription", data={"email": "eleve@exemple.fr", "mot_de_passe": "un-mot-de-passe-solide"},
                     headers={"Origin": settings.public_url})


def test_page_shows_a_working_link_in_local_mode(env):  # noqa: F811
    settings = replace(env["settings"], public_url=LOCAL, login_link_on_screen=True)
    c, r = page_after_request(env, settings)
    assert r.status_code == 200 and "Test en local" in r.text
    link = env["sent"][-1][1]
    assert f'href="{link}"' in r.text and "/connexion/confirmer/" in link
    login = c.get(link.removeprefix(LOCAL), follow_redirects=False)
    assert login.status_code == 303


def test_page_never_shows_the_link_online(env):  # noqa: F811
    settings = replace(env["settings"], public_url="https://academy.exemple.fr", login_link_on_screen=True)
    _, r = page_after_request(env, settings)
    assert "Vérifiez votre boîte de réception" in r.text
    assert env["sent"][-1][1] not in r.text


class FakeSMTP:
    sent, logins, fail = [], [], None

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context):
        pass

    def login(self, user, password):
        if FakeSMTP.fail:
            raise FakeSMTP.fail
        FakeSMTP.logins.append(user)

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.logins, FakeSMTP.fail = [], [], None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def test_mail_test_command(smtp, capsys):
    s = Settings(jwt_secret=SECRET, smtp_host="smtp.gmail.com", smtp_user="moi@gmail.com", smtp_password="x",
                 smtp_from="ROS Academy <moi@gmail.com>")
    assert mail.main(["dest@exemple.fr"], settings=s) == 0
    assert smtp.logins == ["moi@gmail.com"] and smtp.sent[0]["To"] == "dest@exemple.fr"
    assert "E-mail de test envoyé" in capsys.readouterr().out
    smtp.fail = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    assert mail.main(["dest@exemple.fr"], settings=s) == 1
    assert "mot de passe d'application" in capsys.readouterr().out
    assert mail.main(["pas-une-adresse"], settings=s) == 2
    assert mail.main(["dest@exemple.fr"], settings=Settings(jwt_secret=SECRET)) == 1
    assert "SMTP_HOST est vide" in capsys.readouterr().out

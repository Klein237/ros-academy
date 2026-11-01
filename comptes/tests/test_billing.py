import hashlib
import hmac
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import academy_comptes.app as appmod
from academy_comptes import acces
from academy_comptes.billing import BadSignature, StripeClient, StripeError, format_amount, price_cents, verify_signature
from academy_comptes.clients import comptes_token
from academy_comptes.db import Access, Certificate, StripeEvent, User, utcnow
from test_app import BASE, ORIGIN, SECRET, FakeContenus, FakeHub, db, login, oauth_transport

WHSEC = "whsec_test_secret"


# --- Signature du webhook

def sign(payload: bytes, secret=WHSEC, stamp=None):
    stamp = int(time.time()) if stamp is None else stamp
    mac = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={mac}"


def test_signature_valid_and_with_several_v1():
    body = b'{"id": "evt_1"}'
    verify_signature(body, sign(body), WHSEC)
    stamp = int(time.time())
    verify_signature(body, f"t={stamp},v1=deadbeef,{sign(body, stamp=stamp).split(',')[1]}", WHSEC)


@pytest.mark.parametrize("header", ["", "v1=abc", "t=abc,v1=abc", "t=1,t=2,v1=abc", "SIGNED"])
def test_signature_unreadable_header_is_refused(header):
    with pytest.raises(BadSignature):
        verify_signature(b"{}", header, WHSEC)


def test_signature_wrong_secret_body_or_age_is_refused():
    body = b'{"id": "evt_1"}'
    with pytest.raises(BadSignature):
        verify_signature(body, sign(body, secret="whsec_autre"), WHSEC)
    with pytest.raises(BadSignature):
        verify_signature(body + b" ", sign(body), WHSEC)
    with pytest.raises(BadSignature):
        verify_signature(body, sign(body, stamp=int(time.time()) - 301), WHSEC)
    with pytest.raises(BadSignature):
        verify_signature(body, sign(body, stamp=int(time.time()) + 301), WHSEC)


# --- Prix et durée

def test_price_of_a_parcours():
    assert price_cents({"prix": 30}) == 3000 and price_cents({"prix": 29.5}) == 2950
    assert price_cents({"prix": None}) is None and price_cents({}) is None and price_cents({"prix": 0}) is None
    assert price_cents({"prix": 30, "offert": True}) is None  # offert avec un certificat : jamais vendu
    assert format_amount(3000) == "30 €" and format_amount(2950) == "29,50 €"


def test_twelve_months_later():
    assert acces.add_months(datetime(2026, 10, 14, 9, 30), 12) == datetime(2027, 10, 14, 9, 30)
    assert acces.add_months(datetime(2027, 1, 31), 1) == datetime(2027, 2, 28)
    assert acces.add_months(datetime(2026, 11, 30), 3) == datetime(2027, 2, 28)


# --- Client Stripe

class FakeStripe:
    """API Stripe simulée : sessions de paiement, requêtes enregistrées."""

    def __init__(self):
        self.requests = []
        self.down = False

    def handler(self, request):
        self.requests.append(request)
        if request.headers.get("authorization") != "Bearer sk_test_cle":
            return httpx.Response(401, json={"error": {"message": "clé invalide"}})
        if self.down:
            return httpx.Response(500, json={"error": {"message": "panne"}})
        if request.url.path == "/v1/checkout/sessions":
            return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"})
        return httpx.Response(404, json={"error": {"message": "inconnu"}})

    def client(self):
        return StripeClient("sk_test_cle", http=httpx.Client(transport=httpx.MockTransport(self.handler)))

    def last_form(self):
        return {k: v[0] for k, v in parse_qs(self.requests[-1].content.decode()).items()}


def test_client_errors_become_stripe_errors():
    fake = FakeStripe()
    user = User(id=1, email="eleve@exemple.fr")
    p = {"id": "ros2", "titre": "ROS 2"}
    fake.down = True
    with pytest.raises(StripeError, match="500"):
        fake.client().create_checkout(user, p, 3000, 12, "https://ok", "https://ko")
    with pytest.raises(StripeError):
        StripeClient("sk_test_cle", http=httpx.Client(transport=httpx.MockTransport(
            lambda r: (_ for _ in ()).throw(httpx.ConnectError("x"))))).create_checkout(user, p, 3000, 12, "a", "b")


# --- Application

class ShopContenus(FakeContenus):
    def parcours(self):
        return [
            {"id": "ros2", "titre": "Apprendre ROS 2", "prix": 30, "modules": [
                {"id": "01-a", "titre": "Module A", "coef": 1}, {"id": "02-b", "titre": "Module B", "coef": 3}]},
            {"id": "bras", "titre": "Bras robotique", "prix": 29.5, "modules": [
                {"id": "30-e", "titre": "Module E", "coef": 1}]},
            {"id": "docker", "titre": "Docker", "offert": True, "modules": [
                {"id": "20-d", "titre": "Module D", "coef": 1}]},
        ]


@pytest.fixture
def benv(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(appmod, "send_account_mail", lambda settings, email, sorte, link: sent.append((email, link, sorte)))
    base = appmod.Settings(jwt_secret=SECRET, public_url=BASE, database_url=f"sqlite:///{tmp_path}/c.db",
                           admin_emails=frozenset({"admin@exemple.fr"}))
    fake = FakeStripe()

    def make(contenus=None, **changes):
        settings = replace(base, **{"stripe_secret_key": "sk_test_cle", "stripe_webhook_secret": WHSEC,
                                    "acces_payant": True, **changes})
        app = appmod.create_app(settings, hub=FakeHub(), contenus=contenus or ShopContenus(),
                                http=httpx.Client(transport=oauth_transport()), background=False, stripe=fake.client())
        return TestClient(app, base_url=BASE)

    return {"client": make(), "make": make, "stripe": fake, "sent": sent}


def webhook(client, event, secret=WHSEC):
    body = json.dumps(event).encode()
    return client.post("/api/comptes/stripe/webhook", content=body,
                       headers={"Stripe-Signature": sign(body, secret), "Content-Type": "application/json"})


def paid(user_id, parcours="ros2", evt="evt_1", session="cs_1", status="paid", amount=3000):
    return {"id": evt, "type": "checkout.session.completed", "data": {"object": {
        "id": session, "mode": "payment", "payment_status": status, "client_reference_id": str(user_id),
        "customer": "cus_1", "amount_total": amount, "metadata": {"user_id": str(user_id), "parcours_id": parcours}}}}


def accesses(client):
    with db(client) as s:
        return [(a.parcours_id, a.origine, a.fin) for a in s.scalars(select(Access).order_by(Access.id))]


def header(client):
    return client.get("/api/comptes/interne/session").headers.get("X-Academy-Acces")


def test_no_payment_without_stripe(benv):
    client = benv["make"](stripe_secret_key="", stripe_webhook_secret="")
    login(client, benv)
    page = client.get("/compte/acheter/ros2").text
    assert "30 €" in page and "pas encore ouvert" in page and "Payer" not in page
    assert client.post("/compte/acheter/ros2", data={"renonciation": "oui"}, headers=ORIGIN).status_code == 404
    assert client.post("/api/comptes/stripe/webhook", content=b"{}").status_code == 404


def test_buy_redirects_to_stripe_with_the_price_of_the_parcours(benv):
    client, fake = benv["client"], benv["stripe"]
    assert client.get("/compte/acheter/ros2", follow_redirects=False).headers["location"].startswith("/connexion")
    login(client, benv)
    page = client.get("/compte/acheter/ros2").text
    assert "30 €" in page and "12 mois" in page and "droit de rétractation" in page
    # sans la case « accès immédiat, renonciation au droit de rétractation » : pas de paiement
    r = client.post("/compte/acheter/ros2", headers=ORIGIN)
    assert r.status_code == 400 and not fake.requests
    assert client.post("/compte/acheter/ros2", data={"renonciation": "oui"}).status_code == 403  # origine absente
    r = client.post("/compte/acheter/ros2", data={"renonciation": "oui"}, headers=ORIGIN, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "https://checkout.stripe.com/c/pay/cs_1"
    form = fake.last_form()
    assert form["mode"] == "payment" and form["line_items[0][price_data][unit_amount]"] == "3000"
    assert form["line_items[0][price_data][currency]"] == "eur"
    assert form["metadata[parcours_id]"] == "ros2" and form["client_reference_id"] == "1"
    assert form["customer_email"] == "eleve@exemple.fr"
    assert form["success_url"] == f"{BASE}/compte/acheter/ros2?retour=paye"
    # la redirection vers Stripe est permise par la CSP (form-action)
    assert "https://checkout.stripe.com" in r.headers["content-security-policy"]


def test_not_for_sale(benv):
    client = benv["client"]
    login(client, benv)
    assert client.post("/compte/acheter/docker", data={"renonciation": "oui"}, headers=ORIGIN).status_code == 404
    assert "certificat" in client.get("/compte/acheter/docker").text
    assert client.get("/compte/acheter/inconnu").status_code == 404


def test_paid_checkout_opens_twelve_months_once(benv):
    client = benv["client"]
    login(client, benv)
    assert "confirmation en cours" not in client.get("/compte/acheter/ros2?retour=paye").text.lower()
    assert "ouverture de l'accès en cours" in client.get("/compte/acheter/ros2?retour=paye").text
    assert webhook(client, paid(1, status="unpaid", evt="evt_0")).status_code == 200
    assert accesses(client) == []
    assert webhook(client, paid(1)).json() == {"recu": True}
    [(pid, origine, fin)] = accesses(client)
    assert (pid, origine) == ("ros2", "achat") and abs((fin - acces.add_months(utcnow(), 12)).total_seconds()) < 60
    # le même événement, puis la même session dans un autre événement : un seul accès
    webhook(client, paid(1))
    webhook(client, paid(1, evt="evt_2"))
    assert len(accesses(client)) == 1
    with db(client) as s:
        assert s.get(StripeEvent, "evt_2") and s.scalar(select(User)).stripe_customer_id == "cus_1"
    assert "Vous avez accès à ce parcours jusqu'au" in client.get("/compte/acheter/ros2").text
    assert "Apprendre ROS 2" in client.get("/compte/").text
    # nouvel achat avant la fin : prolongé depuis la fin du premier
    webhook(client, paid(1, evt="evt_3", session="cs_2"))
    assert accesses(client)[1][2] == acces.add_months(fin, 12)


def test_bad_webhooks_open_nothing(benv):
    client = benv["client"]
    login(client, benv)
    body = json.dumps(paid(1)).encode()
    r = client.post("/api/comptes/stripe/webhook", content=body, headers={"Stripe-Signature": sign(body, "whsec_x")})
    assert r.status_code == 400
    webhook(client, paid(99, evt="evt_u"))  # compte inconnu
    event = paid(1, evt="evt_p")
    del event["data"]["object"]["metadata"]["parcours_id"]
    webhook(client, event)
    subscription = {"id": "evt_s", "type": "checkout.session.completed",
                    "data": {"object": {"id": "cs_s", "mode": "subscription", "client_reference_id": "1"}}}
    webhook(client, subscription)
    assert accesses(client) == []


def test_access_header_follows_purchases_offers_and_certificates(benv):
    client = benv["client"]
    login(client, benv)
    assert header(client) == ""
    webhook(client, paid(1, parcours="bras"))
    assert header(client) == "bras"
    with db(client) as s:
        s.add(Certificate(code="ABCDEFGHJKLMNPQR", user_id=1, parcours_id="bras", parcours_titre="Bras", nom="É",
                          note=15, modules_json="[]"))
        s.commit()
    assert header(client) == "bras,docker"  # le certificat ouvre le parcours offert
    with db(client) as s:
        s.add(Access(user_id=1, parcours_id="*", origine="offert", fin=utcnow() - timedelta(days=1)))
        s.commit()
    assert header(client) == "bras,docker"  # accès offert terminé
    with db(client) as s:
        s.add(Access(user_id=1, parcours_id="*", origine="offert"))
        s.commit()
    assert header(client) == "*"


def test_beta_opens_everything(benv):
    client = benv["make"](acces_payant=False)
    login(client, benv)
    assert header(client) == "*"
    assert client.get("/api/comptes/qcm/30-e").status_code == 200
    claims = lab_claims(client)
    assert claims["plan"] == "free"


def lab_claims(client):
    r = client.get("/compte/lab", follow_redirects=False)
    assert r.status_code == 303, r.text
    token = parse_qs(urlsplit(r.headers["location"]).query)["token"][0]
    return jwt.decode(token, SECRET, algorithms=["HS256"], audience="ros-lab")


def test_modules_and_lab_need_an_access(benv):
    client = benv["client"]
    login(client, benv)
    ok = {"X-Academy-Interne": comptes_token(SECRET)}
    assert client.get("/api/comptes/qcm/01-a").status_code == 403
    assert client.post("/api/comptes/exercices/01-a/indices/1", headers=ORIGIN).status_code == 403
    assert client.post("/api/comptes/qcm/01-a", json={"reponses": {}}, headers=ORIGIN).status_code == 403
    r = client.get("/compte/lab", follow_redirects=False)
    assert r.status_code == 403 and "/tarifs/" in r.text
    assert client.get("/api/comptes/interne/lab/u1", headers=ok).json() == {"autorise": False}
    assert client.get("/api/comptes/moi").json()["formule"] == "aucune"
    webhook(client, paid(1))
    assert client.get("/api/comptes/qcm/01-a").status_code == 200
    assert client.get("/api/comptes/qcm/30-e").status_code == 403  # un autre parcours
    assert lab_claims(client)["plan"] == "pro"
    assert client.get("/api/comptes/interne/lab/u1", headers=ok).json() == {"autorise": True}
    assert client.get("/api/comptes/moi").json()["minutes_restantes"] is None


def admin(client, benv):
    login(client, benv, email="admin@exemple.fr")


def test_offered_access_is_for_trainers(benv):
    client = benv["client"]
    login(client, benv)
    assert client.get("/compte/formateur/acces").status_code == 403
    assert client.post("/compte/formateur/acces", data={"emails": "eleve@exemple.fr"}, headers=ORIGIN).status_code == 403


def test_trainer_offers_and_removes_access(benv):
    other = benv["make"]()
    login(other, benv)  # le compte eleve@exemple.fr (u1)
    client = benv["client"]
    admin(client, benv)
    page = client.get("/compte/formateur/acces").text
    assert "Offrir un accès" in page and "Tous les parcours" in page
    r = client.post("/compte/formateur/acces", data={"emails": "eleve@exemple.fr\ninconnu@exemple.fr pas-une-adresse",
                                                     "parcours": "*", "fin": "2099-12-31", "motif": "Bêta-test"},
                    headers=ORIGIN)
    assert r.status_code == 200 and "Accès offert à 1 compte." in r.text
    assert "inconnu@exemple.fr" in r.text and "pas-une-adresse" in r.text
    assert accesses(client) == [("*", "offert", datetime(2099, 12, 31, 23, 59))]
    assert header(other) == "*"
    for data, message in (({"emails": "eleve@exemple.fr", "parcours": "nav2"}, "Parcours inconnu"),
                          ({"emails": "eleve@exemple.fr", "fin": "31/12/2099"}, "illisible"),
                          ({"emails": "eleve@exemple.fr", "fin": "2020-01-01"}, "déjà passée"),
                          ({"emails": "personne@exemple.fr"}, "Aucun compte")):
        r = client.post("/compte/formateur/acces", data=data, headers=ORIGIN)
        assert r.status_code == 400 and message in r.text
    # tous les comptes (bêta-testeurs) : élève et administrateur
    r = client.post("/compte/formateur/acces", data={"tous_les_comptes": "oui", "parcours": "ros2"}, headers=ORIGIN)
    assert "Accès offert à 2 comptes." in r.text
    with db(client) as s:
        first = s.scalar(select(Access).order_by(Access.id))
    assert client.post(f"/compte/formateur/acces/{first.id}/retirer", headers=ORIGIN,
                       follow_redirects=False).status_code == 303
    assert header(other) == "ros2"
    webhook(client, paid(1, parcours="bras"))
    with db(client) as s:
        bought = s.scalar(select(Access).where(Access.origine == "achat"))
    assert client.post(f"/compte/formateur/acces/{bought.id}/retirer", headers=ORIGIN).status_code == 409
    assert "achat (30,00 €)" in client.get("/compte/formateur/acces").text
    assert "avec un accès payé ou offert" in client.get("/compte/formateur").text


def test_free_path_module_opens_without_purchase(benv):
    """Un module du parcours gratuit (dans aucun parcours payant) : QCM et indices ouverts à tout compte."""
    contenus = ShopContenus()
    contenus.gratuits = [{"id": "02-linux", "titre": "Linux pour la robotique", "coef": 1, "bonus": False,
                          "exercice": True}]
    client = benv["make"](contenus=contenus)
    login(client, benv)
    assert client.get("/api/comptes/qcm/01-a").status_code == 403  # parcours payant, pas acheté
    assert client.get("/api/comptes/qcm/02-linux").status_code == 200  # module gratuit
    assert client.post("/api/comptes/exercices/02-linux/indices/1", headers=ORIGIN).status_code == 200
    assert client.post("/api/comptes/ouvertures/02-linux", headers=ORIGIN).status_code == 200

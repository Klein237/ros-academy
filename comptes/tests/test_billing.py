import hashlib
import hmac
import json
import time
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

import academy_comptes.app as appmod
from academy_comptes.billing import (
    BadSignature,
    StripeClient,
    StripeError,
    apply_subscription,
    format_price,
    verify_signature,
)
from academy_comptes.db import StripeEvent, User
from test_app import BASE, ORIGIN, SECRET, FakeContenus, FakeHub, client, db, env, login, oauth_transport  # noqa: F401 (fixtures)

WHSEC = "whsec_test_secret"
PRICE = "price_pro"


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


@pytest.mark.parametrize("header", [
    "",
    "v1=abc",
    "t=abc,v1=abc",
    "t=1,t=2,v1=abc",
    "SIGNED",
])
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


# --- Statut → formule

def sub(status, id="sub_1", customer="cus_1", end=1_800_000_000, cancel=False, new_api=False):
    s = {"id": id, "customer": customer, "status": status, "cancel_at_period_end": cancel}
    if new_api:
        s["items"] = {"data": [{"current_period_end": end}]}
    else:
        s["current_period_end"] = end
    return s


@pytest.mark.parametrize("status,formule", [
    ("active", "pro"), ("trialing", "pro"), ("past_due", "pro"),
    ("canceled", "free"), ("unpaid", "free"), ("incomplete", "free"), ("incomplete_expired", "free"), ("paused", "free"),
])
def test_status_decides_the_plan(status, formule):
    user = User(email="a@b.fr", formule="free")
    assert apply_subscription(user, sub(status)) is True
    assert user.formule == formule and user.abonnement_statut == status


def test_period_end_from_the_subscription_or_its_items():
    for new_api in (False, True):
        user = User(email="a@b.fr")
        apply_subscription(user, sub("active", end=1_800_000_000, cancel=True, new_api=new_api))
        assert user.abonnement_fin.isoformat() == "2027-01-15T08:00:00"
        assert user.abonnement_resilie is True


def test_old_subscription_ending_does_not_remove_a_newer_one():
    user = User(email="a@b.fr")
    apply_subscription(user, sub("active", id="sub_new"))
    assert apply_subscription(user, sub("canceled", id="sub_old")) is False
    assert user.formule == "pro" and user.stripe_subscription_id == "sub_new"


def test_format_price():
    assert format_price({"unit_amount": 900, "currency": "eur", "recurring": {"interval": "month"}}) == "9,00 € / mois"
    assert format_price({"unit_amount": 1250, "currency": "usd"}) == "12,50 $"


# --- Client Stripe

class FakeStripe:
    """API Stripe simulée : abonnements modifiables par les tests, requêtes enregistrées."""

    def __init__(self):
        self.subscriptions = {}
        self.requests = []
        self.down = False

    def handler(self, request):
        self.requests.append(request)
        if request.headers.get("authorization") != "Bearer sk_test_cle":
            return httpx.Response(401, json={"error": {"message": "clé invalide"}})
        if self.down:
            return httpx.Response(500, json={"error": {"message": "panne"}})
        path = request.url.path
        if path == "/v1/checkout/sessions":
            return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"})
        if path == "/v1/billing_portal/sessions":
            return httpx.Response(200, json={"url": "https://billing.stripe.com/p/session/1"})
        if path.startswith("/v1/subscriptions/"):
            s = self.subscriptions.get(path.rsplit("/", 1)[1])
            return httpx.Response(200, json=s) if s else httpx.Response(404, json={"error": {"message": "absent"}})
        if path == f"/v1/prices/{PRICE}":
            return httpx.Response(200, json={"unit_amount": 900, "currency": "eur", "recurring": {"interval": "month"}})
        return httpx.Response(404, json={"error": {"message": "inconnu"}})

    def client(self):
        return StripeClient("sk_test_cle", http=httpx.Client(transport=httpx.MockTransport(self.handler)))


def test_client_errors_become_stripe_errors():
    fake = FakeStripe()
    with pytest.raises(StripeError, match="404"):
        fake.client().subscription("sub_absent")
    fake.down = True
    with pytest.raises(StripeError, match="500"):
        fake.client().price(PRICE)
    with pytest.raises(StripeError):
        StripeClient("sk_test_cle", http=httpx.Client(transport=httpx.MockTransport(
            lambda r: (_ for _ in ()).throw(httpx.ConnectError("x"))))).price(PRICE)


# --- Application

@pytest.fixture
def benv(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(appmod, "send_login_link", lambda settings, email, link: sent.append((email, link)))
    settings = replace(
        appmod.Settings(jwt_secret=SECRET, public_url=BASE, database_url=f"sqlite:///{tmp_path}/c.db"),
        stripe_secret_key="sk_test_cle", stripe_webhook_secret=WHSEC, stripe_price_id=PRICE)
    fake = FakeStripe()
    app = appmod.create_app(settings, hub=FakeHub(), contenus=FakeContenus(),
                            http=httpx.Client(transport=oauth_transport()), background=False, stripe=fake.client())
    client = TestClient(app, base_url=BASE)
    return {"client": client, "stripe": fake, "sent": sent, "settings": settings}


def webhook(client, event, secret=WHSEC):
    body = json.dumps(event).encode()
    return client.post("/api/comptes/stripe/webhook", content=body,
                       headers={"Stripe-Signature": sign(body, secret), "Content-Type": "application/json"})


def checkout_completed(user_id, evt="evt_cs", customer="cus_1", subscription="sub_1"):
    return {"id": evt, "type": "checkout.session.completed", "data": {"object": {
        "mode": "subscription", "client_reference_id": str(user_id), "customer": customer,
        "subscription": subscription, "customer_details": {"email": "autre@pirate.fr"}}}}


def sub_event(evt, kind="updated", id="sub_1", customer="cus_1", status="active"):
    return {"id": evt, "type": f"customer.subscription.{kind}",
            "data": {"object": {"id": id, "customer": customer, "status": status}}}


def formule(client, email="eleve@exemple.fr"):
    with db(client) as s:
        return s.query(User).filter_by(email=email).one().formule


def test_billing_routes_absent_without_stripe(client, env):
    login(client, env)
    assert client.get("/compte/abonnement").status_code == 404
    assert client.post("/compte/abonnement/souscrire", headers=ORIGIN).status_code == 404
    assert client.post("/api/comptes/stripe/webhook", content=b"{}").status_code == 404
    assert "Passer en pro" not in client.get("/compte/").text


def test_subscribe_redirects_to_checkout_for_this_account(benv):
    client, fake = benv["client"], benv["stripe"]
    assert client.post("/compte/abonnement/souscrire", headers=ORIGIN).status_code == 401
    login(client, benv)
    page = client.get("/compte/abonnement").text
    assert "9,00 € / mois" in page and "S'abonner" in page
    assert "Passer en pro" in client.get("/compte/").text
    assert client.post("/compte/abonnement/souscrire").status_code == 403  # sans Origin
    r = client.post("/compte/abonnement/souscrire", headers=ORIGIN, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "https://checkout.stripe.com/c/pay/cs_1"
    form = parse_qs(fake.requests[-1].content.decode())
    assert form["mode"] == ["subscription"] and form["line_items[0][price]"] == [PRICE]
    assert form["client_reference_id"] == ["1"] and form["customer_email"] == ["eleve@exemple.fr"]
    assert form["success_url"] == [f"{BASE}/compte/abonnement?retour=paye"]
    assert "sk_test_cle" not in page


def test_webhook_refuses_bad_signatures(benv):
    client = benv["client"]
    login(client, benv)
    body = json.dumps(checkout_completed(1)).encode()
    for headers in ({}, {"Stripe-Signature": "t=1,v1=abc"}, {"Stripe-Signature": sign(body, "whsec_autre")},
                    {"Stripe-Signature": sign(body, stamp=int(time.time()) - 600)}):
        assert client.post("/api/comptes/stripe/webhook", content=body, headers=headers).status_code == 400
    assert formule(client) == "free"


def test_checkout_then_subscription_lifecycle(benv):
    client, fake = benv["client"], benv["stripe"]
    login(client, benv)
    fake.subscriptions["sub_1"] = sub("active")
    assert client.get("/compte/abonnement?retour=paye").text.count("confirmation en cours") == 1
    assert webhook(client, checkout_completed(1)).status_code == 200
    assert formule(client) == "pro"
    page = client.get("/compte/abonnement?retour=paye").text
    assert "Gérer mon abonnement" in page and "confirmation en cours" not in page
    assert "Prochain renouvellement le 15/01/2027" in page
    # le JWT du lab porte la formule pro (limites du conteneur côté Hub)
    q = parse_qs(urlsplit(client.get("/compte/lab", follow_redirects=False).headers["location"]).query)
    assert jwt.decode(q["token"][0], SECRET, algorithms=["HS256"], audience="ros-lab")["plan"] == "pro"
    assert client.get("/api/comptes/moi").json()["minutes_restantes"] is None
    # déjà abonné : pas de seconde souscription
    assert client.post("/compte/abonnement/souscrire", headers=ORIGIN).status_code == 409
    # résiliation programmée, puis fin de l'abonnement
    fake.subscriptions["sub_1"] = sub("active", cancel=True)
    webhook(client, sub_event("evt_2"))
    assert formule(client) == "pro" and "reste active jusqu'au 15/01/2027" in client.get("/compte/abonnement").text
    fake.subscriptions["sub_1"] = sub("canceled")
    webhook(client, sub_event("evt_3", kind="deleted", status="canceled"))
    assert formule(client) == "free"
    assert client.get("/api/comptes/moi").json()["minutes_restantes"] == 600


def test_events_are_idempotent_and_order_does_not_matter(benv):
    client, fake = benv["client"], benv["stripe"]
    login(client, benv)
    fake.subscriptions["sub_1"] = sub("active")
    # la mise à jour arrive avant le paiement : client encore inconnu, ignorée sans erreur
    assert webhook(client, sub_event("evt_early", kind="created")).status_code == 200
    assert formule(client) == "free"
    webhook(client, checkout_completed(1))
    # un événement ancien (« incomplete ») livré en retard : la relecture chez Stripe dit « active »
    webhook(client, sub_event("evt_late", status="incomplete"))
    assert formule(client) == "pro"
    # un événement déjà traité n'a aucun effet, même si Stripe a changé depuis
    fake.subscriptions["sub_1"] = sub("canceled")
    n = len(fake.requests)
    assert webhook(client, checkout_completed(1)).status_code == 200
    assert len(fake.requests) == n and formule(client) == "pro"
    with db(client) as s:
        assert s.query(StripeEvent).count() == 3


def test_subscription_is_linked_by_reference_never_by_email(benv):
    client, fake = benv["client"], benv["stripe"]
    login(client, benv, "a@exemple.fr")
    other = TestClient(client.app, base_url=BASE)
    login(other, benv, "b@exemple.fr")
    fake.subscriptions["sub_1"] = sub("active")
    webhook(client, checkout_completed(2, customer="cus_1"))
    assert formule(client, "b@exemple.fr") == "pro" and formule(client, "a@exemple.fr") == "free"
    # un même client Stripe ne peut pas être rattaché à un second compte
    fake.subscriptions["sub_2"] = sub("active", id="sub_2", customer="cus_1")
    webhook(client, checkout_completed(1, evt="evt_cs2", customer="cus_1", subscription="sub_2"))
    assert formule(client, "a@exemple.fr") == "free"
    # un abonnement relu chez Stripe pour un autre client ne s'applique pas
    fake.subscriptions["sub_3"] = sub("active", id="sub_3", customer="cus_autre")
    webhook(client, checkout_completed(1, evt="evt_cs3", customer="cus_9", subscription="sub_3"))
    assert formule(client, "a@exemple.fr") == "free"
    # référence inconnue ou absente : ignorée
    assert webhook(client, checkout_completed(99, evt="evt_cs4", customer="cus_x")).status_code == 200


def test_stripe_down_makes_stripe_retry(benv):
    client, fake = benv["client"], benv["stripe"]
    login(client, benv)
    fake.down = True
    assert webhook(client, checkout_completed(1)).status_code == 503
    fake.down = False
    fake.subscriptions["sub_1"] = sub("active")
    assert webhook(client, checkout_completed(1)).status_code == 200  # renvoi du même événement
    assert formule(client) == "pro"


def test_portal_and_manual_pro_untouched(benv):
    client, fake = benv["client"], benv["stripe"]
    login(client, benv)
    assert client.post("/compte/abonnement/gerer", headers=ORIGIN).status_code == 404  # pas de client Stripe
    with db(client) as s:
        s.query(User).one().formule = "pro"  # attribuée à la main
        s.commit()
    assert "attribuée par l'équipe" in client.get("/compte/abonnement").text
    fake.subscriptions["sub_1"] = sub("active")
    webhook(client, checkout_completed(1))
    r = client.post("/compte/abonnement/gerer", headers=ORIGIN, follow_redirects=False)
    assert r.headers["location"] == "https://billing.stripe.com/p/session/1"
    assert parse_qs(fake.requests[-1].content.decode()) == {"customer": ["cus_1"], "return_url": [f"{BASE}/compte/abonnement"]}


def test_quota_page_offers_pro(benv):
    from datetime import timedelta

    from academy_comptes.db import UsageTick, utcnow
    client = benv["client"]
    login(client, benv)
    with db(client) as s:
        start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        s.add_all([UsageTick(user_id=1, minute=start + timedelta(minutes=i)) for i in range(600)])
        s.commit()
    r = client.get("/compte/lab")
    assert r.status_code == 403 and 'href="/compte/abonnement"' in r.text

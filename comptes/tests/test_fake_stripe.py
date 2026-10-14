"""Le faux Stripe des tests de bout en bout, branché sur Comptes en mémoire."""

from dataclasses import replace
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

import academy_comptes.app as appmod
from academy_comptes.billing import StripeClient, verify_signature
from fake_stripe import create_app as create_fake
from test_app import BASE, ORIGIN, SECRET, FakeHub, db, login, oauth_transport
from test_billing import ShopContenus
from academy_comptes.db import Access

KEY, WHSEC = "sk_test_simule", "whsec_simule"
STRIPE = "https://stripe.simule"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Comptes et le faux Stripe, chacun appelant l'autre comme sur le réseau."""
    sent = []
    monkeypatch.setattr(appmod, "send_account_mail", lambda settings, email, sorte, link: sent.append((email, link, sorte)))
    holder = {}

    def to_comptes(request):
        r = holder["comptes"].post(request.url.path, content=request.content, headers=dict(request.headers))
        return httpx.Response(r.status_code, content=r.content)

    fake = create_fake(KEY, WHSEC, f"{BASE}/api/comptes/stripe/webhook", STRIPE,
                       http=httpx.Client(transport=httpx.MockTransport(to_comptes)))
    stripe_http = TestClient(fake, base_url=STRIPE)
    settings = replace(appmod.Settings(jwt_secret=SECRET, public_url=BASE, database_url=f"sqlite:///{tmp_path}/c.db"),
                       stripe_secret_key=KEY, stripe_webhook_secret=WHSEC, stripe_redirect_origins=(STRIPE,),
                       acces_payant=True)
    app = appmod.create_app(settings, hub=FakeHub(), contenus=ShopContenus(),
                            http=httpx.Client(transport=oauth_transport()), background=False,
                            stripe=StripeClient(KEY, http=stripe_http, base=f"{STRIPE}/v1"))
    holder["comptes"] = TestClient(app, base_url=BASE)
    return {"client": holder["comptes"], "stripe": stripe_http, "fake": fake, "sent": sent}


def parcours(client):
    with db(client) as s:
        return [a.parcours_id for a in s.query(Access).order_by(Access.id)]


def buy(client, parcours_id="ros2"):
    return client.post(f"/compte/acheter/{parcours_id}", data={"renonciation": "oui"}, headers=ORIGIN,
                       follow_redirects=False)


def test_api_requires_the_secret_key(world):
    assert world["stripe"].post("/v1/checkout/sessions", data={"mode": "payment"}).status_code == 401
    r = world["stripe"].post("/v1/checkout/sessions", data={}, headers={"Authorization": "Bearer sk_autre"})
    assert r.status_code == 401 and "Invalid API Key" in r.json()["error"]["message"]


def test_webhooks_are_signed_like_stripe(world):
    login(world["client"], world)
    checkout = buy(world["client"])
    world["stripe"].post(urlsplit(checkout.headers["location"]).path + "/payer")
    # chaque envoi a été accepté par Comptes, qui vérifie la signature
    deliveries = world["fake"].state.store["deliveries"]
    assert [d["type"] for d in deliveries] == ["checkout.session.completed"]
    assert all(d["status"] == 200 for d in deliveries)
    from fake_stripe import sign
    verify_signature(b"{}", sign(b"{}", WHSEC), WHSEC)


def test_purchase_through_the_fake(world):
    client, stripe = world["client"], world["stripe"]
    login(client, world)
    csp = client.get("/compte/acheter/ros2").headers["content-security-policy"]
    assert f"form-action 'self' {STRIPE};" in csp

    # paiement annulé : rien ne change
    r = buy(client)
    page = stripe.get(urlsplit(r.headers["location"]).path)
    assert "30,00 €" in page.text and "eleve@exemple.fr" in page.text and "Apprendre ROS 2" in page.text
    assert parcours(client) == []

    # paiement : retour sur Comptes, accès ouvert
    r = buy(client)
    back = stripe.post(urlsplit(r.headers["location"]).path + "/payer", follow_redirects=False)
    assert back.headers["location"] == f"{BASE}/compte/acheter/ros2?retour=paye"
    assert parcours(client) == ["ros2"]
    assert "Vous avez accès à ce parcours" in client.get("/compte/acheter/ros2?retour=paye").text
    assert stripe.post(urlsplit(r.headers["location"]).path + "/payer").status_code == 404  # session close

    # un deuxième parcours, au prix de ce parcours
    r = buy(client, "bras")
    assert "29,50 €" in stripe.get(urlsplit(r.headers["location"]).path).text
    stripe.post(urlsplit(r.headers["location"]).path + "/payer")
    assert parcours(client) == ["ros2", "bras"]
    assert all(d["status"] == 200 for d in world["fake"].state.store["deliveries"])


def test_redirect_origins_are_validated():
    from academy_comptes.settings import _origins
    assert _origins("") == ("https://checkout.stripe.com",)
    assert _origins("http://localhost:12111, https://pay.example") == ("http://localhost:12111", "https://pay.example")
    for bad in ("localhost:12111", "https://x/chemin", "https://x; script-src *", "'unsafe-inline'"):
        with pytest.raises(SystemExit):
            _origins(bad)


def test_default_csp_lets_forms_reach_stripe_only_when_billing_is_on(world, client):
    assert "form-action 'self';" in client.get("/connexion").headers["content-security-policy"]
    csp = world["client"].get("/connexion").headers["content-security-policy"]
    assert f"form-action 'self' {STRIPE};" in csp


from test_app import client, env  # noqa: E402,F401 (fixtures)

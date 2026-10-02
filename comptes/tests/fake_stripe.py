"""Faux Stripe pour les tests de bout en bout (jamais déployé en production).

Imite la partie de Stripe utilisée par Comptes : API (Checkout, portail client,
abonnements, prix), pages hébergées (paiement, portail) et webhooks signés comme
Stripe. Configuration par l'environnement :

- FAKE_STRIPE_KEY : clé secrète attendue (Authorization: Bearer …) ;
- FAKE_STRIPE_WEBHOOK_SECRET : secret de signature des webhooks (whsec_…) ;
- FAKE_STRIPE_WEBHOOK_URL : où envoyer les webhooks (le service Comptes) ;
- FAKE_STRIPE_PUBLIC_URL : adresse des pages vue par le navigateur ;
- FAKE_STRIPE_PRICE : identifiant du prix (9,00 € / mois).

Lancement : uvicorn fake_stripe:create_app_from_env --factory --port 12111
"""

import hashlib
import hmac
import html
import itertools
import json
import os
import time

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

PERIOD = 30 * 86400

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:sans-serif;max-width:520px;margin:40px auto;padding:0 16px}}
button{{font:inherit;padding:8px 14px;margin:4px 0}} .muted{{color:#666}}</style></head>
<body><p class="muted">Stripe simulé — environnement de test</p><h1>{title}</h1>{body}</body></html>"""


def sign(payload: bytes, secret: str, stamp=None):
    stamp = int(time.time()) if stamp is None else stamp
    mac = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={mac}"


def create_app(key, webhook_secret, webhook_url, public_url, price_id, http=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    http = http or httpx.Client(timeout=10)
    public = public_url.rstrip("/")
    ids = itertools.count(1)
    st = {"checkouts": {}, "portals": {}, "subscriptions": {}, "customers": {}, "events": [], "deliveries": []}
    app.state.store = st

    def new_id(prefix):
        return f"{prefix}_{next(ids):06d}"

    def auth(request: Request):
        if request.headers.get("authorization") != f"Bearer {key}":
            raise HTTPException(401, "Invalid API Key provided")

    @app.exception_handler(HTTPException)
    async def stripe_error(request, exc):
        return JSONResponse({"error": {"message": exc.detail, "type": "invalid_request_error"}}, exc.status_code)

    def emit(kind, obj):
        """Webhook signé comme Stripe ; l'objet est une copie de l'état au moment de l'événement."""
        event = {"id": new_id("evt"), "object": "event", "type": kind, "created": int(time.time()),
                 "data": {"object": json.loads(json.dumps(obj))}}
        st["events"].append(event)
        body = json.dumps(event).encode()
        try:
            r = http.post(webhook_url, content=body, headers={
                "Content-Type": "application/json", "Stripe-Signature": sign(body, webhook_secret)})
            st["deliveries"].append({"event": event["id"], "type": kind, "status": r.status_code})
        except httpx.HTTPError as exc:
            st["deliveries"].append({"event": event["id"], "type": kind, "status": 0, "error": str(exc)})

    def update(sub, **changes):
        sub.update(changes)
        emit("customer.subscription.deleted" if sub["status"] == "canceled" else "customer.subscription.updated", sub)

    # --- API

    @app.post("/v1/checkout/sessions")
    async def checkout_create(request: Request):
        auth(request)
        form = dict(await request.form())
        if form.get("mode") != "subscription" or form.get("line_items[0][price]") != price_id:
            raise HTTPException(400, "mode subscription et prix connu attendus")
        cs = {"id": new_id("cs"), "object": "checkout.session", "mode": "subscription",
              "customer": form.get("customer"), "customer_email": form.get("customer_email"),
              "client_reference_id": form.get("client_reference_id"), "success_url": form["success_url"],
              "cancel_url": form["cancel_url"], "subscription": None, "status": "open"}
        cs["url"] = f"{public}/checkout/{cs['id']}"
        st["checkouts"][cs["id"]] = cs
        return cs

    @app.post("/v1/billing_portal/sessions")
    async def portal_create(request: Request):
        auth(request)
        form = dict(await request.form())
        if form.get("customer") not in st["customers"]:
            raise HTTPException(404, "No such customer")
        ps = {"id": new_id("bps"), "customer": form["customer"], "return_url": form["return_url"]}
        ps["url"] = f"{public}/portal/{ps['id']}"
        st["portals"][ps["id"]] = ps
        return ps

    @app.get("/v1/subscriptions/{sub_id}")
    def subscription_get(sub_id: str, request: Request):
        auth(request)
        if sub_id not in st["subscriptions"]:
            raise HTTPException(404, "No such subscription")
        return st["subscriptions"][sub_id]

    @app.get("/v1/prices/{pid}")
    def price_get(pid: str, request: Request):
        auth(request)
        if pid != price_id:
            raise HTTPException(404, "No such price")
        return {"id": pid, "object": "price", "unit_amount": 900, "currency": "eur", "recurring": {"interval": "month"}}

    # --- Pages hébergées

    @app.get("/checkout/{cs_id}", response_class=HTMLResponse)
    def checkout_page(cs_id: str):
        cs = st["checkouts"].get(cs_id)
        if not cs or cs["status"] != "open":
            raise HTTPException(404, "Session de paiement expirée")
        email = html.escape(cs["customer_email"] or st["customers"].get(cs["customer"], {}).get("email", ""))
        body = (f"<p>ROS Academy pro — <strong>9,00 € / mois</strong></p><p>{email}</p>"
                f'<form method="post" action="/checkout/{cs_id}/payer"><button type="submit">Payer</button></form>'
                f'<p><a href="{html.escape(cs["cancel_url"])}">Annuler et revenir</a></p>')
        return PAGE.format(title="Paiement", body=body)

    @app.post("/checkout/{cs_id}/payer")
    def checkout_pay(cs_id: str):
        cs = st["checkouts"].get(cs_id)
        if not cs or cs["status"] != "open":
            raise HTTPException(404, "Session de paiement expirée")
        customer = cs["customer"]
        if not customer:
            customer = new_id("cus")
            st["customers"][customer] = {"id": customer, "email": cs["customer_email"]}
        now = int(time.time())
        sub = {"id": new_id("sub"), "object": "subscription", "customer": customer, "status": "active",
               "cancel_at_period_end": False, "items": {"data": [{"price": {"id": price_id},
                                                                   "current_period_end": now + PERIOD}]}}
        st["subscriptions"][sub["id"]] = sub
        cs.update(status="complete", customer=customer, subscription=sub["id"])
        # comme Stripe : l'abonnement est créé avant la fin de la session de paiement
        emit("customer.subscription.created", sub)
        emit("checkout.session.completed", cs)
        return RedirectResponse(cs["success_url"], status_code=303)

    def portal_or_404(ps_id):
        ps = st["portals"].get(ps_id)
        if not ps:
            raise HTTPException(404, "Session du portail expirée")
        subs = [s for s in st["subscriptions"].values() if s["customer"] == ps["customer"]]
        return ps, (subs[-1] if subs else None)

    @app.get("/portal/{ps_id}", response_class=HTMLResponse)
    def portal_page(ps_id: str):
        ps, sub = portal_or_404(ps_id)
        state = "aucun abonnement" if not sub else (
            f"{sub['status']}{' — résiliation à la fin de la période' if sub['cancel_at_period_end'] else ''}")
        actions = ""
        if sub and sub["status"] != "canceled":
            for action, label in (("resilier-fin", "Résilier à la fin de la période"),
                                  ("resilier", "Résilier maintenant"),
                                  ("echec", "Simuler un échec de paiement"),
                                  ("reprendre", "Reprendre l'abonnement")):
                actions += (f'<form method="post" action="/portal/{ps_id}/{action}">'
                            f'<button type="submit">{label}</button></form>')
        body = (f'<p>Abonnement : <strong class="etat">{html.escape(state)}</strong></p>{actions}'
                f'<p><a href="{html.escape(ps["return_url"])}">Retour à ROS Academy</a></p>')
        return PAGE.format(title="Votre abonnement", body=body)

    @app.post("/portal/{ps_id}/{action}")
    def portal_action(ps_id: str, action: str):
        ps, sub = portal_or_404(ps_id)
        if not sub or sub["status"] == "canceled":
            raise HTTPException(400, "Aucun abonnement actif")
        if action == "resilier-fin":
            update(sub, cancel_at_period_end=True)
        elif action == "resilier":
            update(sub, status="canceled", cancel_at_period_end=False)
        elif action == "echec":
            update(sub, status="past_due")
        elif action == "reprendre":
            update(sub, status="active", cancel_at_period_end=False)
        else:
            raise HTTPException(404, "Action inconnue")
        return RedirectResponse(f"/portal/{ps_id}", status_code=303)

    # --- Inspection par les tests

    @app.get("/__etat")
    def etat():
        return {"deliveries": st["deliveries"], "subscriptions": st["subscriptions"]}

    return app


def create_app_from_env():
    env = os.environ
    return create_app(env["FAKE_STRIPE_KEY"], env["FAKE_STRIPE_WEBHOOK_SECRET"], env["FAKE_STRIPE_WEBHOOK_URL"],
                      env["FAKE_STRIPE_PUBLIC_URL"], env.get("FAKE_STRIPE_PRICE", "price_pro_test"))

"""Faux Stripe pour les tests de bout en bout (jamais déployé en production).

Imite la partie de Stripe utilisée par Comptes : API (Checkout en paiement unique), page de
paiement hébergée et webhooks signés comme Stripe. Configuration par l'environnement :

- FAKE_STRIPE_KEY : clé secrète attendue (Authorization: Bearer …) ;
- FAKE_STRIPE_WEBHOOK_SECRET : secret de signature des webhooks (whsec_…) ;
- FAKE_STRIPE_WEBHOOK_URL : où envoyer les webhooks (le service Comptes) ;
- FAKE_STRIPE_PUBLIC_URL : adresse des pages vue par le navigateur.

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

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:sans-serif;max-width:520px;margin:40px auto;padding:0 16px}}
button{{font:inherit;padding:8px 14px;margin:4px 0}} .muted{{color:#666}}</style></head>
<body><p class="muted">Stripe simulé — environnement de test</p><h1>{title}</h1>{body}</body></html>"""


def sign(payload: bytes, secret: str, stamp=None):
    stamp = int(time.time()) if stamp is None else stamp
    mac = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={mac}"


def create_app(key, webhook_secret, webhook_url, public_url, http=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    http = http or httpx.Client(timeout=10)
    public = public_url.rstrip("/")
    ids = itertools.count(1)
    st = {"checkouts": {}, "customers": {}, "events": [], "deliveries": []}
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

    # --- API

    @app.post("/v1/checkout/sessions")
    async def checkout_create(request: Request):
        auth(request)
        form = dict(await request.form())
        amount = form.get("line_items[0][price_data][unit_amount]", "")
        if form.get("mode") != "payment" or not amount.isdigit() or not form.get("success_url"):
            raise HTTPException(400, "mode payment, montant et adresses de retour attendus")
        metadata = {k[len("metadata["):-1]: v for k, v in form.items() if k.startswith("metadata[")}
        cs = {"id": new_id("cs"), "object": "checkout.session", "mode": "payment", "payment_status": "unpaid",
              "customer": None, "customer_email": form.get("customer_email"),
              "client_reference_id": form.get("client_reference_id"), "metadata": metadata,
              "amount_total": int(amount), "currency": form.get("line_items[0][price_data][currency]"),
              "name": form.get("line_items[0][price_data][product_data][name]", ""),
              "success_url": form["success_url"], "cancel_url": form["cancel_url"], "status": "open"}
        cs["url"] = f"{public}/checkout/{cs['id']}"
        st["checkouts"][cs["id"]] = cs
        return cs

    # --- Page hébergée

    @app.get("/checkout/{cs_id}", response_class=HTMLResponse)
    def checkout_page(cs_id: str):
        cs = st["checkouts"].get(cs_id)
        if not cs or cs["status"] != "open":
            raise HTTPException(404, "Session de paiement expirée")
        montant = f"{cs['amount_total'] / 100:.2f}".replace(".", ",") + " €"
        body = (f"<p>{html.escape(cs['name'])} — <strong>{montant}</strong></p>"
                f"<p>{html.escape(cs['customer_email'] or '')}</p>"
                f'<form method="post" action="/checkout/{cs_id}/payer"><button type="submit">Payer</button></form>'
                f'<p><a href="{html.escape(cs["cancel_url"])}">Annuler et revenir</a></p>')
        return PAGE.format(title="Paiement", body=body)

    @app.post("/checkout/{cs_id}/payer")
    def checkout_pay(cs_id: str):
        cs = st["checkouts"].get(cs_id)
        if not cs or cs["status"] != "open":
            raise HTTPException(404, "Session de paiement expirée")
        customer = new_id("cus")
        st["customers"][customer] = {"id": customer, "email": cs["customer_email"]}
        cs.update(status="complete", payment_status="paid", customer=customer)
        emit("checkout.session.completed", cs)
        return RedirectResponse(cs["success_url"], status_code=303)

    # --- Inspection par les tests

    @app.get("/__etat")
    def etat():
        return {"deliveries": st["deliveries"], "checkouts": st["checkouts"]}

    return app


def create_app_from_env():
    env = os.environ
    return create_app(env["FAKE_STRIPE_KEY"], env["FAKE_STRIPE_WEBHOOK_SECRET"], env["FAKE_STRIPE_WEBHOOK_URL"],
                      env["FAKE_STRIPE_PUBLIC_URL"])

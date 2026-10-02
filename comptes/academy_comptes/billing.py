"""Abonnement à la formule pro avec Stripe (API REST, sans SDK).

Stripe fait foi : chaque événement du webhook déclenche une relecture de l'abonnement
auprès de l'API, puis la formule du compte suit son statut.
"""

import hashlib
import hmac
import time
from datetime import datetime, timezone

import httpx

from .db import User

API = "https://api.stripe.com/v1"
SIGNATURE_TOLERANCE = 300  # secondes
# Statuts où l'étudiant garde la formule pro (past_due : Stripe retente le paiement)
PAYING = {"active", "trialing", "past_due"}


class StripeError(Exception):
    pass


class BadSignature(Exception):
    pass


def verify_signature(payload: bytes, header: str, secret: str, now=None):
    """En-tête Stripe-Signature : « t=<horodatage>,v1=<hmac>[,v1=…] » sur « <t>.<corps brut> »."""
    now = time.time() if now is None else now
    parts = [p.split("=", 1) for p in (header or "").split(",") if "=" in p]
    stamps = [v for k, v in parts if k == "t"]
    signatures = [v for k, v in parts if k == "v1"]
    if len(stamps) != 1 or not signatures:
        raise BadSignature("en-tête de signature illisible")
    try:
        stamp = int(stamps[0])
    except ValueError:
        raise BadSignature("horodatage illisible") from None
    if abs(now - stamp) > SIGNATURE_TOLERANCE:
        raise BadSignature("horodatage hors tolérance")
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in signatures):
        raise BadSignature("signature invalide")


class StripeClient:
    def __init__(self, secret_key, http=None, base=API):
        self.base = base.rstrip("/")
        self.http = http or httpx.Client(timeout=15)
        self.headers = {"Authorization": f"Bearer {secret_key}"}

    def _call(self, method, path, data=None):
        try:
            r = self.http.request(method, f"{self.base}{path}", data=data, headers=self.headers)
        except httpx.HTTPError as exc:
            raise StripeError(f"Stripe injoignable : {exc.__class__.__name__}") from None
        if r.status_code >= 400:
            message = (r.json().get("error") or {}).get("message", "") if r.headers.get("content-type", "").startswith(
                "application/json") else ""
            raise StripeError(f"Stripe {r.status_code} sur {path} : {message}")
        return r.json()

    def create_checkout(self, user, price_id, success_url, cancel_url):
        data = {
            "mode": "subscription",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(user.id),
            "subscription_data[metadata][user_id]": str(user.id),
            "locale": "fr",
        }
        if user.stripe_customer_id:
            data["customer"] = user.stripe_customer_id
        else:
            data["customer_email"] = user.email
        return self._call("POST", "/checkout/sessions", data)["url"]

    def create_portal(self, customer_id, return_url):
        return self._call("POST", "/billing_portal/sessions", {"customer": customer_id, "return_url": return_url})["url"]

    def subscription(self, subscription_id):
        return self._call("GET", f"/subscriptions/{subscription_id}")

    def price(self, price_id):
        return self._call("GET", f"/prices/{price_id}")


def _period_end(sub):
    """Fin de la période en cours (au niveau de l'abonnement ou, en API récente, de ses lignes)."""
    end = sub.get("current_period_end")
    if end is None:
        items = (sub.get("items") or {}).get("data") or []
        ends = [i.get("current_period_end") for i in items if i.get("current_period_end")]
        end = max(ends) if ends else None
    return datetime.fromtimestamp(end, timezone.utc).replace(tzinfo=None) if end else None


def apply_subscription(user: User, sub: dict):
    """Met la formule du compte en accord avec l'abonnement relu chez Stripe.

    Un ancien abonnement qui se termine ne retire pas la formule pro portée par un autre
    abonnement, plus récent, du même compte.
    """
    paying = sub.get("status") in PAYING
    if user.stripe_subscription_id and user.stripe_subscription_id != sub["id"] and not paying:
        return False
    user.stripe_subscription_id = sub["id"]
    user.abonnement_statut = sub.get("status")
    user.abonnement_fin = _period_end(sub)
    user.abonnement_resilie = bool(sub.get("cancel_at_period_end"))
    user.formule = "pro" if paying else "free"
    return True


def format_price(price):
    """« 9,00 € / mois » à partir d'un objet Price de Stripe."""
    amount = (price.get("unit_amount") or 0) / 100
    currency = {"eur": "€", "usd": "$", "gbp": "£"}.get(price.get("currency", ""), price.get("currency", "").upper())
    interval = {"month": "mois", "year": "an", "week": "semaine", "day": "jour"}.get(
        (price.get("recurring") or {}).get("interval", ""), "")
    text = f"{amount:.2f}".replace(".", ",") + f" {currency}"
    return f"{text} / {interval}" if interval else text

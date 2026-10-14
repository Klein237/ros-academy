"""Achat d'un parcours avec Stripe Checkout (paiement unique, API REST, sans SDK).

Le prix vient du parcours (champ « prix » de parcours.yaml) : la session de paiement le porte
(price_data), sans produit ni prix à créer dans Stripe. Le webhook signé
« checkout.session.completed » (payée) ouvre l'accès.
"""

import hashlib
import hmac
import time

import httpx

API = "https://api.stripe.com/v1"
SIGNATURE_TOLERANCE = 300  # secondes


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

    def create_checkout(self, user, parcours, amount_cents, months, success_url, cancel_url):
        """Session de paiement unique pour un parcours ; renvoie l'adresse de la page de Stripe."""
        data = {
            "mode": "payment",
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "eur",
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": f"Parcours « {parcours['titre']} »",
            "line_items[0][price_data][product_data][description]": f"Accès de {months} mois : cours, lab, exercices "
                                                                     "corrigés et certificat",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(user.id),
            "metadata[user_id]": str(user.id),
            "metadata[parcours_id]": parcours["id"],
            "customer_email": user.email,
            "locale": "fr",
        }
        return self._call("POST", "/checkout/sessions", data)["url"]


def price_cents(parcours):
    """Prix d'un parcours en centimes (champ « prix » en euros) ; None s'il n'est pas en vente."""
    prix = parcours.get("prix")
    if prix is None or parcours.get("offert"):
        return None
    try:
        cents = round(float(prix) * 100)
    except (TypeError, ValueError):
        return None
    return cents if cents > 0 else None


def format_amount(cents):
    """3000 → « 30 € » ; 2950 → « 29,50 € »."""
    euros, rest = divmod(int(cents), 100)
    return f"{euros} €" if not rest else f"{euros},{rest:02d} €"

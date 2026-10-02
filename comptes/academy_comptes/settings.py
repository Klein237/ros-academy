"""Configuration du service Comptes, lue dans l'environnement."""

import os
from dataclasses import dataclass, field

# Formule → minutes de lab par mois civil (None : sans limite).
PLAN_MINUTES = {"free": 600, "pro": None}


def _secret(name):
    value = os.environ.get(name, "")
    if len(value) < 32 or value.startswith("remplacer"):
        raise SystemExit(f"{name} doit faire au moins 32 caractères")
    return value


@dataclass
class Settings:
    jwt_secret: str
    public_url: str = "https://localhost"
    database_url: str = "sqlite:///./comptes.db"
    hub_url: str = "http://hub:8000"
    hub_admin_token: str = ""
    contenus_url: str = "http://contenus:8200"
    active_server_limit: int = 35
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "ROS Academy <no-reply@localhost>"
    github_client_id: str = ""
    github_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    admin_emails: frozenset = field(default_factory=frozenset)
    cookie_secure: bool = True
    plan_minutes: dict = field(default_factory=lambda: dict(PLAN_MINUTES))

    @property
    def github_enabled(self):
        return bool(self.github_client_id and self.github_client_secret)

    @property
    def google_enabled(self):
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def billing_enabled(self):
        """Abonnement pro proposé seulement quand Stripe est entièrement configuré."""
        return bool(self.stripe_secret_key and self.stripe_webhook_secret and self.stripe_price_id)

    @classmethod
    def from_env(cls):
        env = os.environ.get
        domain = env("DOMAIN", "localhost")
        return cls(
            jwt_secret=_secret("JWT_SECRET"),
            public_url=env("PUBLIC_URL", f"https://{domain}").rstrip("/"),
            database_url=env("DATABASE_URL", "sqlite:///./comptes.db"),
            hub_url=env("HUB_URL", "http://hub:8000"),
            hub_admin_token=env("HUB_ADMIN_TOKEN", ""),
            contenus_url=env("CONTENUS_URL", "http://contenus:8200"),
            active_server_limit=int(env("ACTIVE_SERVER_LIMIT", "35")),
            smtp_host=env("SMTP_HOST", ""),
            smtp_port=int(env("SMTP_PORT", "587")),
            smtp_user=env("SMTP_USER", ""),
            smtp_password=env("SMTP_PASSWORD", ""),
            smtp_from=env("SMTP_FROM") or f"ROS Academy <no-reply@{domain}>",
            github_client_id=env("GITHUB_CLIENT_ID", ""),
            github_client_secret=env("GITHUB_CLIENT_SECRET", ""),
            google_client_id=env("GOOGLE_CLIENT_ID", ""),
            google_client_secret=env("GOOGLE_CLIENT_SECRET", ""),
            stripe_secret_key=env("STRIPE_SECRET_KEY", ""),
            stripe_webhook_secret=env("STRIPE_WEBHOOK_SECRET", ""),
            stripe_price_id=env("STRIPE_PRICE_ID", ""),
            admin_emails=frozenset(e.strip().lower() for e in env("ADMIN_EMAILS", "").split(",") if e.strip()),
            cookie_secure=env("COOKIE_SECURE", "1") != "0",
        )

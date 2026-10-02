"""Connexion à l'espace d'administration.

Un jeton JWT court (`role: admin`, audience `ros-academy-admin`), signé avec le secret
partagé, s'échange contre un cookie de session signé, limité à /admin.
"""

from urllib.parse import urlsplit

import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

ADMIN_AUDIENCE = "ros-academy-admin"
COOKIE_NAME = "academy_admin"
SESSION_MAX_AGE = 12 * 3600
MAX_TOKEN_LIFETIME = 3600


class AuthError(Exception):
    pass


def verify_admin_token(token, secret, leeway=30):
    if not token:
        raise AuthError("jeton manquant")
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], audience=ADMIN_AUDIENCE, leeway=leeway,
                            options={"require": ["exp", "iat", "sub", "aud"]})
    except jwt.PyJWTError as exc:
        raise AuthError(str(exc)) from exc
    if claims["exp"] - claims["iat"] > MAX_TOKEN_LIFETIME:
        raise AuthError("durée de vie du jeton trop longue")
    if claims.get("role") != "admin":
        raise AuthError("ce jeton ne donne pas accès à l'administration")
    return str(claims["sub"])


class Sessions:
    def __init__(self, secret):
        self._s = URLSafeTimedSerializer(secret, salt="academy-admin-session")

    def issue(self, admin):
        return self._s.dumps({"admin": admin})

    def read(self, cookie):
        if not cookie:
            return None
        try:
            return self._s.loads(cookie, max_age=SESSION_MAX_AGE)["admin"]
        except (BadSignature, SignatureExpired, KeyError, TypeError):
            return None


def same_origin(origin, host, scheme_hint="https"):
    """Vrai si l'en-tête Origin désigne la plateforme elle-même."""
    if not origin or not host:
        return False
    parts = urlsplit(origin)
    return parts.scheme in ("https", "http") and parts.netloc == host

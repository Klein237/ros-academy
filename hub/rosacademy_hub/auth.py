"""Connexion au Hub par jeton JWT émis par le service Comptes."""

import re

import jwt
from jupyterhub.auth import Authenticator
from jupyterhub.handlers import BaseHandler
from jupyterhub.utils import url_path_join
from tornado import web
from traitlets import Integer, Unicode

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class TokenError(Exception):
    pass


def verify_token(token, secret, audience="ros-lab", max_lifetime=3600, leeway=30):
    if not token:
        raise TokenError("jeton manquant")
    if not secret or len(secret) < 32:
        raise TokenError("secret non configuré")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            leeway=leeway,
            options={"require": ["exp", "iat", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if claims["exp"] - claims["iat"] > max_lifetime:
        raise TokenError("durée de vie du jeton trop longue")
    sub = claims["sub"]
    if not isinstance(sub, str) or not USERNAME_RE.fullmatch(sub):
        raise TokenError("identifiant invalide")
    return {"name": sub, "auth_state": {"plan": claims.get("plan")}}


class JWTLoginHandler(BaseHandler):
    async def get(self):
        user = await self.login_user({"token": self.get_argument("token", "")})
        if user is None:
            raise web.HTTPError(403, "Lien de connexion invalide ou expiré. Rouvrez le lab depuis le site.")
        self.redirect(self.get_next_url(user))


class ComptesJWTAuthenticator(Authenticator):
    secret = Unicode(help="Secret HS256 partagé avec le service Comptes").tag(config=True)
    audience = Unicode("ros-lab").tag(config=True)
    max_lifetime = Integer(3600).tag(config=True)

    def get_handlers(self, app):
        return [(r"/jwt_login", JWTLoginHandler)]

    def login_url(self, base_url):
        return url_path_join(base_url, "jwt_login")

    async def authenticate(self, handler, data):
        try:
            return verify_token(data.get("token", ""), self.secret, self.audience, self.max_lifetime)
        except TokenError as exc:
            self.log.warning("Connexion par jeton refusée : %s", exc)
            return None

"""Sessions, lien magique par e-mail, connexion GitHub et Google."""

import hashlib
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from email_validator import EmailNotValidError, validate_email
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, select

from .db import Identity, LoginToken, SessionRow, User, utcnow

SESSION_COOKIE = "academy_session"
OAUTH_COOKIE = "academy_oauth"
SESSION_DAYS = 30
LINK_MINUTES = 15
LINKS_PER_HOUR = 5
SAFE_NEXT_RE = re.compile(r"^/(?![/\\])[^\s\\]*$")


class AuthError(Exception):
    """Erreur présentable à l'étudiant."""


def safe_next(path, default="/"):
    return path if path and SAFE_NEXT_RE.fullmatch(path) else default


def _hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize_email(email):
    try:
        return validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise AuthError("Adresse e-mail invalide.") from None


# --- Comptes

def user_for_email(db, email, nom="", fournisseur=None, sujet=None):
    """Retrouve ou crée le compte d'une adresse vérifiée, et y rattache l'identité du fournisseur."""
    email = email.lower()
    if fournisseur and sujet:
        ident = db.scalar(select(Identity).where(Identity.fournisseur == fournisseur, Identity.sujet == sujet))
        if ident:
            return db.get(User, ident.user_id)
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, nom=nom[:120])
        db.add(user)
        db.flush()
    elif nom and not user.nom:
        user.nom = nom[:120]
    if fournisseur and sujet:
        db.add(Identity(user_id=user.id, fournisseur=fournisseur, sujet=sujet))
    db.commit()
    return user


# --- Sessions (cookie signé contenant un identifiant aléatoire ; seule son empreinte est en base)

class Sessions:
    def __init__(self, secret):
        self._s = URLSafeTimedSerializer(secret, salt="academy-session")
        self._oauth = URLSafeTimedSerializer(secret, salt="academy-oauth-state")

    def create(self, db, user):
        raw = secrets.token_urlsafe(32)
        db.add(SessionRow(id_hash=_hash(raw), user_id=user.id, expire_le=utcnow() + timedelta(days=SESSION_DAYS)))
        db.commit()
        return self._s.dumps(raw)

    def user(self, db, cookie):
        if not cookie:
            return None
        try:
            raw = self._s.loads(cookie, max_age=SESSION_DAYS * 86400)
        except (BadSignature, SignatureExpired):
            return None
        row = db.get(SessionRow, _hash(raw))
        if not row or row.revoquee or row.expire_le < utcnow():
            return None
        return db.get(User, row.user_id)

    def revoke(self, db, cookie):
        try:
            raw = self._s.loads(cookie or "", max_age=SESSION_DAYS * 86400)
        except (BadSignature, SignatureExpired):
            return
        row = db.get(SessionRow, _hash(raw))
        if row:
            row.revoquee = True
            db.commit()

    # État OAuth, lié au navigateur par un cookie signé de 10 min
    def oauth_state(self, provider, suite):
        state = secrets.token_urlsafe(24)
        return state, self._oauth.dumps({"state": state, "provider": provider, "suite": safe_next(suite)})

    def check_oauth_state(self, cookie, provider, state):
        try:
            data = self._oauth.loads(cookie or "", max_age=600)
        except (BadSignature, SignatureExpired):
            raise AuthError("La connexion a expiré : recommencez.") from None
        if data.get("provider") != provider or not state or not secrets.compare_digest(data.get("state", ""), state):
            raise AuthError("Connexion refusée (requête inattendue) : recommencez.")
        return data["suite"]


# --- Lien magique

def request_login_link(db, email, suite, public_url):
    email = normalize_email(email)
    hour_ago = utcnow() - timedelta(hours=1)
    recent = db.scalar(select(func.count()).select_from(LoginToken)
                       .where(LoginToken.email == email, LoginToken.cree_le > hour_ago))
    if recent >= LINKS_PER_HOUR:
        raise AuthError("Trop de demandes pour cette adresse : réessayez dans une heure.")
    raw = secrets.token_urlsafe(32)
    db.add(LoginToken(hash=_hash(raw), email=email, suite=safe_next(suite),
                      expire_le=utcnow() + timedelta(minutes=LINK_MINUTES)))
    db.commit()
    return email, f"{public_url}/connexion/email/{raw}"


def consume_login_link(db, raw):
    row = db.get(LoginToken, _hash(raw or ""))
    if not row or row.utilise_le is not None or row.expire_le < utcnow():
        raise AuthError("Ce lien de connexion n'est plus valable : demandez-en un nouveau.")
    row.utilise_le = utcnow()
    db.commit()
    return row.email, row.suite


# --- OAuth

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"
GOOGLE_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


def authorize_url(settings, provider, state):
    redirect = f"{settings.public_url}/connexion/{provider}/retour"
    if provider == "github":
        q = {"client_id": settings.github_client_id, "redirect_uri": redirect, "scope": "read:user user:email",
             "state": state, "allow_signup": "true"}
        return f"{GITHUB_AUTHORIZE}?{urlencode(q)}"
    q = {"client_id": settings.google_client_id, "redirect_uri": redirect, "response_type": "code",
         "scope": "openid email profile", "state": state, "prompt": "select_account"}
    return f"{GOOGLE_AUTHORIZE}?{urlencode(q)}"


def oauth_identity(settings, http, provider, code):
    """Échange le code contre l'identité (email vérifié, sujet, nom). `http` : client httpx."""
    redirect = f"{settings.public_url}/connexion/{provider}/retour"
    try:
        if provider == "github":
            r = http.post(GITHUB_TOKEN, headers={"Accept": "application/json"}, data={
                "client_id": settings.github_client_id, "client_secret": settings.github_client_secret,
                "code": code, "redirect_uri": redirect})
            token = r.json().get("access_token")
            if not token:
                raise AuthError("GitHub a refusé la connexion.")
            h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
            profile = http.get(f"{GITHUB_API}/user", headers=h).json()
            emails = http.get(f"{GITHUB_API}/user/emails", headers=h).json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            if not primary:
                raise AuthError("Votre adresse e-mail principale GitHub n'est pas vérifiée.")
            return primary["email"], str(profile["id"]), profile.get("name") or profile.get("login") or ""
        r = http.post(GOOGLE_TOKEN, data={
            "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
            "code": code, "redirect_uri": redirect, "grant_type": "authorization_code"})
        token = r.json().get("access_token")
        if not token:
            raise AuthError("Google a refusé la connexion.")
        info = http.get(GOOGLE_USERINFO, headers={"Authorization": f"Bearer {token}"}).json()
        if not info.get("email") or info.get("email_verified") is not True:
            raise AuthError("Votre adresse e-mail Google n'est pas vérifiée.")
        return info["email"], str(info["sub"]), info.get("name", "")
    except AuthError:
        raise
    except Exception:  # noqa: BLE001 - réseau, JSON inattendu
        raise AuthError("Le fournisseur de connexion ne répond pas : réessayez.") from None

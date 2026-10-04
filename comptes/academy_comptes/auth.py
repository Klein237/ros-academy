"""Sessions, mot de passe, liens par e-mail (confirmation, réinitialisation), connexion GitHub et Google."""

import base64
import hashlib
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from email_validator import EmailNotValidError, validate_email
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, select

from .db import Identity, LoginFailure, LoginToken, SessionRow, User, utcnow

SESSION_COOKIE = "academy_session"
OAUTH_COOKIE = "academy_oauth"
SESSION_DAYS = 30
LINK_MINUTES = {"confirmation": 24 * 60, "reinitialisation": 30}
LINK_PATHS = {"confirmation": "/connexion/confirmer/", "reinitialisation": "/connexion/mot-de-passe/"}
LINKS_PER_HOUR = 5
RESEND_SECONDS = 60
PASSWORD_MIN = 10
PASSWORD_MAX = 200
FAILURES_MAX = 10  # mots de passe refusés par adresse…
FAILURES_MINUTES = 15  # …sur cette durée
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

# --- Mots de passe (scrypt, sel aléatoire ; seule l'empreinte est en base)

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def _b64(raw):
    return base64.b64encode(raw).decode()


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${_b64(salt)}${_b64(digest)}"


def check_password(password, stored):
    """Vrai si le mot de passe correspond ; sans empreinte, un calcul a lieu quand même (temps constant)."""
    try:
        _, n, r, p, salt, digest = (stored or "").split("$")
        params = {"n": int(n), "r": int(r), "p": int(p)}
        salt, digest = base64.b64decode(salt), base64.b64decode(digest)
    except ValueError:
        hashlib.scrypt(password.encode(), salt=b"0" * 16, dklen=32, **_SCRYPT)
        return False
    return secrets.compare_digest(hashlib.scrypt(password.encode(), salt=salt, dklen=32, **params), digest)


def check_new_password(password):
    if len(password) < PASSWORD_MIN:
        raise AuthError(f"Le mot de passe doit contenir au moins {PASSWORD_MIN} caractères.")
    if len(password) > PASSWORD_MAX:
        raise AuthError("Mot de passe trop long.")
    return password


def too_many_failures(db, email):
    since = utcnow() - timedelta(minutes=FAILURES_MINUTES)
    count = db.scalar(select(func.count()).select_from(LoginFailure)
                      .where(LoginFailure.email == email, LoginFailure.cree_le > since))
    return count >= FAILURES_MAX


def record_failure(db, email):
    db.add(LoginFailure(email=email))
    db.commit()


def authenticate(db, email, password):
    """Compte correspondant à l'adresse et au mot de passe ; AuthError sinon (message identique dans tous
    les cas, pour ne pas révéler quelles adresses ont un compte)."""
    email = normalize_email(email)
    if too_many_failures(db, email):
        raise AuthError(f"Trop d'essais pour cette adresse : réessayez dans {FAILURES_MINUTES} minutes, "
                        "ou choisissez un nouveau mot de passe avec « Mot de passe oublié ».")
    user = db.scalar(select(User).where(User.email == email))
    if not check_password(password, user.mot_de_passe if user else None):
        record_failure(db, email)
        raise AuthError("Adresse e-mail ou mot de passe incorrect.")
    return user


def user_for_email(db, email, nom="", fournisseur=None, sujet=None):
    """Retrouve ou crée le compte d'une adresse vérifiée (par Google, GitHub ou un lien reçu par e-mail),
    et y rattache l'identité du fournisseur."""
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
    if user.email_verifie_le is None:
        user.email_verifie_le = utcnow()
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


# --- Liens envoyés par e-mail (confirmation de l'adresse, réinitialisation du mot de passe)

def create_link(db, email, but, suite, public_url):
    """Nouveau lien à usage unique ; il annule les liens précédents du même but pour cette adresse."""
    now = utcnow()
    tokens = select(LoginToken).where(LoginToken.email == email, LoginToken.but == but)
    last = db.scalar(tokens.order_by(LoginToken.cree_le.desc()).limit(1))
    if last and (now - last.cree_le).total_seconds() < RESEND_SECONDS:
        raise AuthError("Un e-mail vient de vous être envoyé : patientez une minute avant d'en demander un autre.")
    recent = db.scalar(select(func.count()).select_from(LoginToken)
                       .where(LoginToken.email == email, LoginToken.cree_le > now - timedelta(hours=1)))
    if recent >= LINKS_PER_HOUR:
        raise AuthError("Trop de demandes pour cette adresse : réessayez dans une heure.")
    for old in db.scalars(tokens.where(LoginToken.utilise_le.is_(None))):
        old.utilise_le = now  # un seul lien valable à la fois
    raw = secrets.token_urlsafe(32)
    db.add(LoginToken(hash=_hash(raw), email=email, but=but, suite=safe_next(suite),
                      expire_le=now + timedelta(minutes=LINK_MINUTES[but])))
    db.commit()
    return f"{public_url}{LINK_PATHS[but]}{raw}"


def peek_link(db, raw, but):
    """Le lien est-il encore valable ? (sans le consommer : page du formulaire de mot de passe)"""
    row = db.get(LoginToken, _hash(raw or ""))
    if not row or row.but != but or row.utilise_le is not None or row.expire_le < utcnow():
        raise AuthError("Ce lien n'est plus valable : demandez-en un nouveau.")
    return row


def consume_link(db, raw, but):
    row = peek_link(db, raw, but)
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

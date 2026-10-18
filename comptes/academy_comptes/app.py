"""Service Comptes : connexion, accès au lab, quotas, progression, notes."""

import asyncio
import hmac
import json
import logging
import re
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
import jwt
from itsdangerous import BadSignature as BadToken, SignatureExpired, URLSafeTimedSerializer
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from . import acces, avis, certificats, formateur, grading, inscriptions, questions, rgpd
from .billing import BadSignature, StripeClient, StripeError, format_amount, price_cents, verify_signature
from .auth import (
    OAUTH_COOKIE,
    SESSION_COOKIE,
    SESSION_DAYS,
    AuthError,
    Sessions,
    authenticate,
    authorize_url,
    check_new_password,
    consume_link,
    create_link,
    hash_password,
    check_password,
    normalize_email,
    oauth_identity,
    peek_link,
    safe_next,
    user_for_email,
)
from .clients import INTERNAL_HEADER, ContenusClient, HubClient, UpstreamError, comptes_token
from .db import (
    Access,
    Answer,
    Base,
    Certificate,
    Exercise,
    ModuleFeedback,
    QcmAttempt,
    Question,
    QueueTicket,
    SessionRow,
    StripeEvent,
    Trainer,
    User,
    make_engine,
    make_sessionmaker,
    utcnow,
)
from .mail import send_account_mail
from .quotas import HUB_NAME_RE, join_queue, leave_queue, minutes_left, minutes_used, queue_position, record_minute
from .settings import Settings

log = logging.getLogger("comptes")
HERE = Path(__file__).parent
MODULE_ID_RE = re.compile(r"^[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
LAB_TOKEN_TTL = 300
def csp(form_targets=()):
    # form-action s'applique aussi à la redirection qui suit un formulaire (« Payer » → Stripe)
    form = " ".join(("'self'", *form_targets))
    return ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            f"connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action {form}; object-src 'none'")


class QcmBody(BaseModel):
    reponses: dict[str, list[int]] = {}


class QuestionBody(BaseModel):
    titre: str
    texte: str
    prive: bool = False
    solution: bool = False
    joindre_verification: bool = False


class AnswerBody(BaseModel):
    texte: str
    solution: bool = False


class FlagBody(BaseModel):
    valeur: bool = True


class FeedbackBody(BaseModel):
    note: int
    difficulte: str
    commentaire: str = ""


def mint_lab_token(secret, user, plan):
    now = int(time.time())
    return jwt.encode({"sub": user.hub_name, "plan": plan, "aud": "ros-lab", "iat": now,
                       "exp": now + LAB_TOKEN_TTL}, secret, algorithm="HS256")


def mint_admin_token(secret, user):
    now = int(time.time())
    return jwt.encode({"sub": user.email, "role": "admin", "aud": "ros-academy-admin", "iat": now,
                       "exp": now + LAB_TOKEN_TTL}, secret, algorithm="HS256")


def safe_lab_next(path):
    path = safe_next(path, "/lab/")
    return path if path == "/lab/" or path.startswith("/lab/?") else "/lab/"


def create_app(settings: Settings, hub=None, contenus=None, http=None, background=True, stripe=None):
    engine = make_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)  # Postgres : migrations Alembic
    SessionLocal = make_sessionmaker(engine)
    sessions = Sessions(settings.jwt_secret)
    hub = hub or HubClient(settings.hub_url, settings.hub_admin_token)
    contenus = contenus or ContenusClient(settings.contenus_url, settings.jwt_secret)
    http = http or httpx.Client(timeout=15)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.globals["billing"] = settings.billing_enabled
    if settings.show_login_link:
        log.warning("Liens de connexion affichés à l'écran (CONNEXION_LIEN_A_L_ECRAN=1) : test en local seulement")
    elif settings.login_link_on_screen:
        log.warning("CONNEXION_LIEN_A_L_ECRAN ignoré : seulement sans SMTP et sur une adresse locale (DOMAIN=localhost)")
    if settings.billing_enabled:
        stripe = stripe or StripeClient(settings.stripe_secret_key, base=settings.stripe_api_base)
    page_csp = csp(settings.stripe_redirect_origins if settings.billing_enabled else ())
    state = {"actifs": 0, "releve": 0.0, "parcours": [], "parcours_lu": 0.0}

    def tick():
        with SessionLocal() as db:
            actifs, stopped = record_minute(db, hub, settings)
        state["actifs"], state["releve"] = actifs, time.time()
        for name in stopped:
            log.info("Quota épuisé : serveur de %s arrêté", name)

    def questions_digest(now=None):
        """Au plus une fois par heure : prévient l'équipe s'il y a de nouvelles questions."""
        with SessionLocal() as db:
            if not questions.digest_due(db, now or utcnow()):
                return 0
            staff = sorted(inscriptions.staff_emails(db, settings))
        for email in staff:
            notify(email, "questions", f"{settings.public_url}/compte/formateur/questions")
        return len(staff)

    async def digest_loop():
        while True:
            await asyncio.sleep(60)
            try:
                await asyncio.to_thread(questions_digest)
            except Exception as exc:  # noqa: BLE001 - base ou SMTP indisponibles un moment
                log.warning("Récapitulatif des questions impossible : %s", exc)

    async def loop():
        while True:
            try:
                await asyncio.to_thread(tick)
            except Exception as exc:  # noqa: BLE001 - le Hub peut redémarrer
                log.warning("Relevé des minutes impossible : %s", exc)
            await asyncio.sleep(60)

    @asynccontextmanager
    async def lifespan(_app):
        task = asyncio.create_task(loop()) if background and settings.hub_admin_token else None
        digest = asyncio.create_task(digest_loop()) if background else None
        yield
        for t in (task, digest):
            if t:
                t.cancel()

    app = FastAPI(title="Comptes RoboForge", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.session_factory = SessionLocal
    app.state.tick = tick
    app.state.questions_digest = questions_digest
    app.mount("/static/comptes", StaticFiles(directory=str(HERE / "static")), name="static")

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", page_csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers["Cache-Control"] = "no-store"
        return response

    def get_db():
        with SessionLocal() as db:
            yield db

    def current_user(request: Request, db=Depends(get_db)):
        """Compte de la session ; un compte en attente ou désinscrit n'en a pas (voir enter)."""
        user = sessions.user(db, request.cookies.get(SESSION_COOKIE))
        return user if user and user.statut == inscriptions.ACTIF else None

    def require_user(user=Depends(current_user)):
        if not user:
            raise HTTPException(401, "Connexion requise")
        return user

    def same_origin(request: Request):
        origin = request.headers.get("origin")
        if not origin or urlsplit(origin).netloc != request.headers.get("host"):
            raise HTTPException(403, "Requête refusée (origine inconnue)")

    def page(request, name, status=200, **ctx):
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    def login_redirect(suite):
        return RedirectResponse(f"/connexion?suite={quote(suite, safe='')}", status_code=303)

    def open_session(db, user, suite):
        response = RedirectResponse(safe_next(suite), status_code=303)
        response.set_cookie(SESSION_COOKIE, sessions.create(db, user), max_age=SESSION_DAYS * 86400, path="/",
                            httponly=True, secure=settings.cookie_secure, samesite="lax")
        response.delete_cookie(OAUTH_COOKIE, path="/connexion")
        return response

    # --- Inscriptions par vagues : un compte sans place attend, sans session

    quitting = URLSafeTimedSerializer(settings.jwt_secret, salt="academy-quitter")

    def notify(email, sorte, link):
        """E-mail d'information (liste d'attente, invitation, équipe) ; un échec d'envoi est journalisé."""
        try:
            send_account_mail(settings, email, sorte, link)
            return True
        except Exception:  # noqa: BLE001 - serveur SMTP
            log.exception("Envoi de l'e-mail (%s) à %s impossible", sorte, email)
            return False

    def waiting_page(request, db, user, status=200):
        return page(request, "liste_attente.html", status, compte=user, rang=inscriptions.position(db, user),
                    jeton=quitting.dumps(user.id), contact=settings.editeur_contact)

    def enter(request, db, user, suite):
        """Adresse confirmée : ouvre la session, ou affiche la liste d'attente (ou l'inscription close)."""
        if inscriptions.admit(db, settings, user):
            log.info("u%s sur la liste d'attente", user.id)
            notify(user.email, "attente", f"{settings.public_url}/")
        if user.statut == inscriptions.ACTIF:
            return open_session(db, user, suite)
        return waiting_page(request, db, user)

    def check_module(module):
        if not MODULE_ID_RE.fullmatch(module):
            raise HTTPException(404, "Module introuvable")

    # --- Accès aux parcours (achat, accès offert, parcours offerts avec un certificat)

    def catalogue():
        """Parcours disponibles, relus chez Contenus au plus une fois par minute (dernière liste si injoignable)."""
        if time.time() - state["parcours_lu"] > 60:
            try:
                state["parcours"], state["parcours_lu"] = contenus.parcours(), time.time()
            except Exception as exc:  # noqa: BLE001
                log.warning("Parcours illisibles chez Contenus : %s", exc)
        return state["parcours"]

    def offerts():
        return [p["id"] for p in catalogue() if p.get("offert")]

    def accessible(db, user):
        return acces.accessible(db, user, settings, utcnow(), offerts())

    def require_module_access(db, user, module):
        """QCM, indices, vérification : réservés aux parcours ouverts au compte (une fois l'accès payant activé)."""
        check_module(module)
        if not settings.acces_payant:
            return
        ids = [p["id"] for p in catalogue() if any(m["id"] == module for m in p["modules"])]
        if not acces.can_open(accessible(db, user), ids):
            raise HTTPException(403, "Ce module fait partie d'un parcours que vous n'avez pas encore acheté")

    def lab_plan(db, user):
        return acces.plan(db, user, settings, utcnow())

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"erreur": exc.detail}, status_code=exc.status_code)
        return page(request, "message.html", exc.status_code, titre="Erreur", message=exc.detail)

    # --- Connexion

    def login_page(request, status=200, suite="/", **ctx):
        return page(request, "connexion.html", status, suite=safe_next(suite), github=settings.github_enabled,
                    google=settings.google_enabled, **ctx)

    def mail_sent(request, email, sorte, link, suite, titre, message, status=200, renvoi=False):
        """Envoie le lien et affiche « Vérifiez votre boîte » (ou le lien lui-même en test local)."""
        try:
            send_account_mail(settings, email, sorte, link)
        except Exception:  # noqa: BLE001 - serveur SMTP
            log.exception("Envoi de l'e-mail (%s) impossible", sorte)
            return page(request, "message.html", 502, titre="Envoi impossible",
                        message="L'e-mail n'a pas pu être envoyé. Réessayez dans un instant.")
        return page(request, "attente.html", status, titre=titre, message=message, email=email,
                    suite=safe_next(suite), renvoi=renvoi, lien=link if settings.show_login_link else None)

    def send_confirmation(request, db, user, suite, titre, message):
        try:
            link = create_link(db, user.email, "confirmation", suite, settings.public_url)
        except AuthError as exc:  # renvoi trop rapproché : le lien précédent reste valable
            return page(request, "attente.html", titre=titre, message=message, email=user.email,
                        suite=safe_next(suite), renvoi=True, erreur=str(exc))
        return mail_sent(request, user.email, "confirmation", link, suite, titre, message, renvoi=True)

    def revoke_sessions(db, user):
        for row in db.scalars(select(SessionRow).where(SessionRow.user_id == user.id, SessionRow.revoquee.is_(False))):
            row.revoquee = True
        db.commit()

    @app.get("/connexion", response_class=HTMLResponse)
    def connexion(request: Request, suite: str = "/", user=Depends(current_user)):
        if user:
            return RedirectResponse(safe_next(suite), status_code=303)
        return login_page(request, suite=suite)

    @app.post("/connexion", response_class=HTMLResponse)
    def connexion_post(request: Request, email: str = Form(...), mot_de_passe: str = Form(...), suite: str = Form("/"),
                       db=Depends(get_db), _=Depends(same_origin)):
        try:
            user = authenticate(db, email, mot_de_passe)
        except AuthError as exc:
            return login_page(request, 400, suite=suite, erreur=str(exc), email=email[:320])
        if user.email_verifie_le is None:
            return send_confirmation(request, db, user, suite, "Confirmez d'abord votre adresse",
                                     f"Votre compte n'est pas encore activé. Ouvrez le lien envoyé à {user.email} "
                                     "pour le confirmer.")
        return enter(request, db, user, suite)

    @app.get("/connexion/inscription", response_class=HTMLResponse)
    def inscription(request: Request, suite: str = "/", user=Depends(current_user), db=Depends(get_db)):
        if user:
            return RedirectResponse(safe_next(suite), status_code=303)
        return page(request, "inscription.html", suite=safe_next(suite), complet=inscriptions.free(db, settings) == 0)

    @app.post("/connexion/inscription", response_class=HTMLResponse)
    def inscription_post(request: Request, nom: str = Form(""), email: str = Form(...), mot_de_passe: str = Form(...),
                         suite: str = Form("/"), db=Depends(get_db), _=Depends(same_origin)):
        nom = nom.strip()[:120]
        try:
            email = normalize_email(email)
            check_new_password(mot_de_passe)
        except AuthError as exc:
            return page(request, "inscription.html", 400, suite=safe_next(suite), erreur=str(exc), nom=nom,
                        email=email[:320], complet=inscriptions.free(db, settings) == 0)
        titre = "Vérifiez votre boîte de réception"
        message = f"Nous avons envoyé un e-mail à {email}. Ouvrez le lien qu'il contient pour activer votre compte."
        if inscriptions.free(db, settings) == 0:
            message = (f"Nous avons envoyé un e-mail à {email}. Les places de la phase de test sont toutes prises : "
                       "ouvrez le lien qu'il contient pour confirmer votre adresse et prendre rang sur la liste "
                       "d'attente.")
        user = db.scalar(select(User).where(User.email == email))
        if user and user.email_verifie_le is not None:
            # Adresse déjà inscrite : même réponse, et un e-mail qui propose de choisir un nouveau mot de passe
            # (on ne révèle pas ici quelles adresses ont un compte).
            try:
                link = create_link(db, email, "reinitialisation", suite, settings.public_url)
            except AuthError:
                return page(request, "attente.html", titre=titre, message=message, email=email, suite=safe_next(suite))
            return mail_sent(request, email, "compte_existant", link, suite, titre, message)
        if user is None:
            user = User(email=email)
            db.add(user)
        user.nom = nom or user.nom
        user.mot_de_passe = hash_password(mot_de_passe)
        db.commit()
        return send_confirmation(request, db, user, suite, titre, message)

    @app.post("/connexion/renvoyer", response_class=HTMLResponse)
    def renvoyer(request: Request, email: str = Form(...), suite: str = Form("/"), db=Depends(get_db),
                 _=Depends(same_origin)):
        titre = "Vérifiez votre boîte de réception"
        try:
            email = normalize_email(email)
        except AuthError as exc:
            return login_page(request, 400, suite=suite, erreur=str(exc))
        message = f"Un nouvel e-mail a été envoyé à {email}, s'il correspond à un compte à activer."
        user = db.scalar(select(User).where(User.email == email))
        if not user or user.email_verifie_le is not None:
            return page(request, "attente.html", titre=titre, message=message, email=email, suite=safe_next(suite),
                        renvoi=True)
        return send_confirmation(request, db, user, suite, titre, message)

    @app.get("/connexion/confirmer/{raw}")
    def confirmer(request: Request, raw: str, db=Depends(get_db)):
        try:
            email, suite = consume_link(db, raw, "confirmation")
        except AuthError as exc:
            return page(request, "message.html", 400, titre="Lien expiré", message=str(exc),
                        lien="/connexion", lien_texte="Se connecter pour recevoir un nouveau lien")
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            raise HTTPException(404, "Compte introuvable")
        if user.email_verifie_le is None:
            user.email_verifie_le = utcnow()
            db.commit()
        return enter(request, db, user, suite)

    @app.post("/connexion/quitter", response_class=HTMLResponse)
    def quitter(request: Request, jeton: str = Form(""), db=Depends(get_db), _=Depends(same_origin)):
        """Quitter la liste d'attente (ou effacer une inscription close) : supprime le compte. Le jeton
        vient de la page affichée après la connexion, valable 15 minutes."""
        try:
            user = db.get(User, int(quitting.loads(jeton, max_age=900)))
        except (BadToken, SignatureExpired, ValueError, TypeError):
            user = None
        if not user or user.statut == inscriptions.ACTIF:
            return page(request, "message.html", 400, titre="Lien expiré",
                        message="Reconnectez-vous pour quitter la liste d'attente.", lien="/connexion",
                        lien_texte="Se connecter")
        try:
            rgpd.delete_account(db, user, hub)
        except (UpstreamError, httpx.HTTPError):
            log.exception("Suppression de l'inscription %s : Hub injoignable", user.id)
            return page(request, "message.html", 502, titre="Suppression impossible",
                        message="Réessayez dans un moment.", lien="/connexion", lien_texte="Se connecter")
        log.info("Inscription %s supprimée (liste d'attente quittée)", user.id)
        return page(request, "message.html", titre="Inscription supprimée",
                    message="Vous avez quitté la liste d'attente : votre compte et votre adresse ont été effacés.",
                    lien="/", lien_texte="Retour à l'accueil")

    @app.get("/connexion/oubli", response_class=HTMLResponse)
    def oubli(request: Request, suite: str = "/"):
        return page(request, "oubli.html", suite=safe_next(suite))

    @app.post("/connexion/oubli", response_class=HTMLResponse)
    def oubli_post(request: Request, email: str = Form(...), suite: str = Form("/"), db=Depends(get_db),
                   _=Depends(same_origin)):
        try:
            email = normalize_email(email)
        except AuthError as exc:
            return page(request, "oubli.html", 400, suite=safe_next(suite), erreur=str(exc))
        titre = "Vérifiez votre boîte de réception"
        message = (f"Si un compte existe pour {email}, nous venons d'y envoyer un lien pour choisir un nouveau mot "
                   "de passe. Il est valable 30 minutes.")
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            return page(request, "attente.html", titre=titre, message=message, email=email, suite=safe_next(suite))
        try:
            link = create_link(db, email, "reinitialisation", suite, settings.public_url)
        except AuthError as exc:
            return page(request, "oubli.html", 429, suite=safe_next(suite), erreur=str(exc), email=email)
        return mail_sent(request, email, "reinitialisation", link, suite, titre, message)

    @app.get("/connexion/mot-de-passe/{raw}", response_class=HTMLResponse)
    def nouveau_mot_de_passe(request: Request, raw: str, db=Depends(get_db)):
        try:
            row = peek_link(db, raw, "reinitialisation")
        except AuthError as exc:
            return page(request, "message.html", 400, titre="Lien expiré", message=str(exc),
                        lien="/connexion/oubli", lien_texte="Demander un nouveau lien")
        return page(request, "nouveau_mot_de_passe.html", email=row.email)

    @app.post("/connexion/mot-de-passe/{raw}", response_class=HTMLResponse)
    def nouveau_mot_de_passe_post(request: Request, raw: str, mot_de_passe: str = Form(...), db=Depends(get_db),
                                  _=Depends(same_origin)):
        try:
            row = peek_link(db, raw, "reinitialisation")
        except AuthError as exc:
            return page(request, "message.html", 400, titre="Lien expiré", message=str(exc),
                        lien="/connexion/oubli", lien_texte="Demander un nouveau lien")
        try:
            check_new_password(mot_de_passe)
        except AuthError as exc:
            return page(request, "nouveau_mot_de_passe.html", 400, email=row.email, erreur=str(exc))
        email, suite = consume_link(db, raw, "reinitialisation")
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            raise HTTPException(404, "Compte introuvable")
        user.mot_de_passe = hash_password(mot_de_passe)
        if user.email_verifie_le is None:
            user.email_verifie_le = utcnow()  # le lien prouve l'accès à la boîte
        db.commit()
        revoke_sessions(db, user)  # les autres appareils doivent se reconnecter
        log.info("Mot de passe changé pour u%s", user.id)
        return enter(request, db, user, suite)

    def oauth_start(provider, suite):
        enabled = settings.github_enabled if provider == "github" else settings.google_enabled
        if not enabled:
            raise HTTPException(404, "Cette méthode de connexion n'est pas configurée")
        oauth_state, cookie = sessions.oauth_state(provider, suite)
        response = RedirectResponse(authorize_url(settings, provider, oauth_state), status_code=303)
        response.set_cookie(OAUTH_COOKIE, cookie, max_age=600, path="/connexion", httponly=True,
                            secure=settings.cookie_secure, samesite="lax")
        return response

    def oauth_back(request, provider, code, oauth_state, db):
        try:
            suite = sessions.check_oauth_state(request.cookies.get(OAUTH_COOKIE), provider, oauth_state)
            email, sujet, nom = oauth_identity(settings, http, provider, code)
        except AuthError as exc:
            return page(request, "message.html", 400, titre="Connexion impossible", message=str(exc),
                        lien="/connexion", lien_texte="Réessayer")
        return enter(request, db, user_for_email(db, email, nom, provider, sujet), suite)

    @app.get("/connexion/github")
    def github(suite: str = "/"):
        return oauth_start("github", suite)

    @app.get("/connexion/github/retour")
    def github_back(request: Request, code: str = "", state: str = "", db=Depends(get_db)):
        return oauth_back(request, "github", code, state, db)

    @app.get("/connexion/google")
    def google(suite: str = "/"):
        return oauth_start("google", suite)

    @app.get("/connexion/google/retour")
    def google_back(request: Request, code: str = "", state: str = "", db=Depends(get_db)):
        return oauth_back(request, "google", code, state, db)

    @app.post("/deconnexion")
    def deconnexion(request: Request, db=Depends(get_db), _=Depends(same_origin)):
        sessions.revoke(db, request.cookies.get(SESSION_COOKIE))
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    # --- Compte, lab, administration

    def access_rows(db, user):
        """Accès du compte, du plus récent au plus ancien, avec le titre du parcours et leur état."""
        titres = {p["id"]: p["titre"] for p in catalogue()}
        now = utcnow()
        rows = db.scalars(select(Access).where(Access.user_id == user.id).order_by(Access.debut.desc()))
        return [{"acces": a, "titre": "Tous les parcours" if a.parcours_id == acces.TOUS else titres.get(a.parcours_id, a.parcours_id),
                 "valable": a.retire_le is None and a.debut <= now and (a.fin is None or a.fin > now)} for a in rows]

    def account_ctx(db, user):
        return {"user": user, "utilisees": minutes_used(db, user), "restantes": minutes_left(db, user, settings),
                "admin": inscriptions.is_admin(settings, user.email),
                "formateur": inscriptions.is_staff(db, settings, user.email), "acces": access_rows(db, user),
                "acces_payant": settings.acces_payant, "certificat": acces.has_certificate(db, user),
                "formule": lab_plan(db, user)}

    @app.get("/compte/", response_class=HTMLResponse)
    def compte(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/")
        return page(request, "compte.html", **account_ctx(db, user))

    @app.post("/compte/mot-de-passe", response_class=HTMLResponse)
    def compte_mot_de_passe(request: Request, actuel: str = Form(""), nouveau: str = Form(...),
                            user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        def retour(status, **ctx):
            return page(request, "compte.html", status, **account_ctx(db, user), **ctx)
        if user.mot_de_passe and not check_password(actuel, user.mot_de_passe):
            return retour(400, erreur_mdp="Mot de passe actuel incorrect.")
        try:
            check_new_password(nouveau)
        except AuthError as exc:
            return retour(400, erreur_mdp=str(exc))
        user.mot_de_passe = hash_password(nouveau)
        db.commit()
        log.info("Mot de passe changé pour u%s (depuis son compte)", user.id)
        return retour(200, info_mdp="Mot de passe enregistré.")

    @app.get("/compte/lab")
    def compte_lab(request: Request, suite: str = "/lab/", user=Depends(current_user), db=Depends(get_db)):
        suite = safe_lab_next(suite)
        if not user:
            return login_redirect(f"/compte/lab?suite={quote(suite, safe='')}")
        formule = lab_plan(db, user)
        if formule == "aucune":
            return page(request, "message.html", 403, titre="Le lab est inclus avec un parcours",
                        message="Le lab s'ouvre avec l'achat d'un parcours (ou un accès offert). « Découvrir ROS 2 » "
                                "reste ouvert à tous, sans compte.", lien="/tarifs/", lien_texte="Voir les tarifs")
        if minutes_left(db, user, settings) == 0:
            return page(request, "message.html", 403, titre="Quota de lab épuisé",
                        message="Vous avez utilisé toutes vos minutes de lab ce mois-ci. Les cours, les QCM et vos "
                                "notes restent accessibles ; le lab sera de nouveau disponible le mois prochain.",
                        lien="/compte/resultats", lien_texte="Voir mes résultats")
        token = mint_lab_token(settings.jwt_secret, user, formule)
        return RedirectResponse(f"/hub/jwt_login?token={token}&next={quote(suite, safe='')}", status_code=303)

    @app.get("/compte/admin")
    def compte_admin(user=Depends(current_user)):
        if not user:
            return login_redirect("/compte/admin")
        if user.email not in settings.admin_emails:
            raise HTTPException(403, "Ce compte n'a pas accès à l'administration")
        return RedirectResponse(f"/admin/login?token={mint_admin_token(settings.jwt_secret, user)}", status_code=303)

    # --- Données personnelles (RGPD) et pages légales

    @app.get("/compte/donnees")
    def compte_donnees(user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/")
        return Response(rgpd.export_json(db, user), media_type="application/json; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="roboforge-mes-donnees.json"',
                                 "Cache-Control": "no-store"})

    @app.get("/compte/supprimer", response_class=HTMLResponse)
    def compte_supprimer_page(request: Request, user=Depends(current_user)):
        if not user:
            return login_redirect("/compte/supprimer")
        return page(request, "supprimer.html", user=user)

    @app.post("/compte/supprimer", response_class=HTMLResponse)
    def compte_supprimer(request: Request, confirmation: str = Form(""), user=Depends(current_user),
                         db=Depends(get_db), _=Depends(same_origin)):
        if not user:
            return login_redirect("/compte/supprimer")
        if confirmation.strip().lower() != user.email:
            return page(request, "supprimer.html", 400, user=user,
                        erreur="Recopiez exactement votre adresse e-mail pour confirmer.")
        try:
            rgpd.delete_account(db, user, hub)
        except (UpstreamError, httpx.HTTPError):
            log.exception("Suppression du compte %s : Hub injoignable", user.id)
            return page(request, "supprimer.html", 502, user=user,
                        erreur="Votre lab n'a pas pu être supprimé pour l'instant : réessayez dans un moment.")
        log.info("Compte %s supprimé à la demande de son titulaire", user.id)
        response = page(request, "message.html", titre="Compte supprimé",
                        message="Votre compte, vos résultats, vos certificats et les fichiers de votre lab ont été "
                                "supprimés.", lien="/", lien_texte="Retour à l'accueil")
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @app.get("/mentions-legales", response_class=HTMLResponse)
    def mentions_legales(request: Request):
        return page(request, "mentions_legales.html", s=settings)

    @app.get("/confidentialite", response_class=HTMLResponse)
    def confidentialite(request: Request):
        return page(request, "confidentialite.html", s=settings, conservation=settings.sauvegarde_jours)

    # --- Achat d'un parcours (paiement unique, Stripe)

    def require_billing():
        if not settings.billing_enabled:
            raise HTTPException(404, "Page introuvable")

    def parcours_for_sale(parcours_id):
        p = next((x for x in catalogue() if x["id"] == parcours_id), None)
        if not p:
            raise HTTPException(404, "Parcours introuvable")
        return p

    def purchase_page(request, db, user, p, status=200, **ctx):
        prix = price_cents(p)
        actuel = next((r for r in access_rows(db, user) if r["valable"]
                       and r["acces"].parcours_id in (p["id"], acces.TOUS)), None)
        return page(request, "acheter.html", status, user=user, parcours=p, prix=format_amount(prix) if prix else None,
                    mois=settings.acces_duree_mois, actuel=actuel, billing=settings.billing_enabled,
                    certificat=acces.has_certificate(db, user), **ctx)

    @app.get("/compte/acheter/{parcours_id}", response_class=HTMLResponse)
    def acheter(request: Request, parcours_id: str, retour: str = "", user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect(f"/compte/acheter/{parcours_id}")
        return purchase_page(request, db, user, parcours_for_sale(parcours_id), en_attente=retour == "paye")

    @app.post("/compte/acheter/{parcours_id}", dependencies=[Depends(require_billing)])
    def payer(request: Request, parcours_id: str, renonciation: str = Form(""), user=Depends(require_user),
              db=Depends(get_db), _=Depends(same_origin)):
        p = parcours_for_sale(parcours_id)
        prix = price_cents(p)
        if not prix:
            raise HTTPException(404, "Ce parcours n'est pas en vente")
        if renonciation != "oui":
            return purchase_page(request, db, user, p, 400,
                                 erreur="Cochez la case : l'accès est ouvert dès le paiement, ce qui met fin au droit "
                                        "de rétractation.")
        try:
            url = stripe.create_checkout(user, p, prix, settings.acces_duree_mois,
                                         f"{settings.public_url}/compte/acheter/{p['id']}?retour=paye",
                                         f"{settings.public_url}/compte/acheter/{p['id']}")
        except StripeError as exc:
            log.warning("Session de paiement impossible : %s", exc)
            raise HTTPException(502, "Le paiement est momentanément indisponible, réessayez plus tard") from None
        return RedirectResponse(url, status_code=303)

    def handle_event(event):
        """Applique un événement Stripe vérifié ; renvoie False s'il était déjà traité."""
        with SessionLocal() as db:
            if db.get(StripeEvent, event["id"]):
                return False
            obj = (event.get("data") or {}).get("object") or {}
            if (event.get("type") in ("checkout.session.completed", "checkout.session.async_payment_succeeded")
                    and obj.get("mode") == "payment" and obj.get("payment_status") == "paid"):
                record_purchase(db, obj)
            db.add(StripeEvent(id=event["id"]))
            db.commit()
            return True

    def record_purchase(db, obj):
        """Ouvre l'accès payé (une fois par session de paiement, même si l'événement revient)."""
        meta = obj.get("metadata") or {}
        ref = str(obj.get("client_reference_id") or meta.get("user_id") or "")
        user = db.get(User, int(ref)) if ref.isdigit() else None
        parcours_id = str(meta.get("parcours_id") or "")
        if not user or not parcours_id or db.scalar(select(Access).where(Access.stripe_session_id == obj.get("id"))):
            if not user or not parcours_id:
                log.warning("Paiement %s sans compte ou sans parcours : accès non ouvert", obj.get("id"))
            return
        now = utcnow()
        fin = acces.purchase_end(db, user, parcours_id, now, settings.acces_duree_mois)
        db.add(Access(user_id=user.id, parcours_id=parcours_id, origine="achat", debut=now, fin=fin,
                      montant_centimes=obj.get("amount_total"), stripe_session_id=obj.get("id")))
        if obj.get("customer") and not user.stripe_customer_id:
            if not db.scalar(select(User).where(User.stripe_customer_id == obj["customer"])):
                user.stripe_customer_id = obj["customer"]
        log.info("Achat de u%s : parcours %s jusqu'au %s", user.id, parcours_id, fin.date())

    @app.post("/api/comptes/stripe/webhook", dependencies=[Depends(require_billing)])
    async def stripe_webhook(request: Request):
        payload = await request.body()
        try:
            verify_signature(payload, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret)
            event = json.loads(payload)
            event_id = event["id"]
        except (BadSignature, ValueError, KeyError, TypeError):
            raise HTTPException(400, "Signature ou contenu invalide") from None
        await asyncio.to_thread(handle_event, event)
        log.debug("Événement Stripe %s reçu", event_id)
        return {"recu": True}

    # --- Tableau de bord formateur (administrateurs ADMIN_EMAILS et formateurs de l'équipe)

    def require_trainer(db, user):
        if not inscriptions.is_staff(db, settings, user.email):
            raise HTTPException(403, "Le tableau de bord est réservé aux formateurs")

    def require_admin(user):
        if not inscriptions.is_admin(settings, user.email):
            raise HTTPException(403, "Réservé aux administrateurs")

    def trainer_data(db, parcours_id):
        try:
            all_parcours = contenus.parcours()
        except Exception:  # noqa: BLE001
            raise HTTPException(503, "Les parcours sont momentanément indisponibles") from None
        parcours = next((p for p in all_parcours if p["id"] == parcours_id), all_parcours[0] if all_parcours else None)
        return all_parcours, parcours, formateur.students(db, parcours, inscriptions.staff_emails(db, settings), utcnow())

    def users_with_access(db):
        now = utcnow()
        return {a.user_id for a in db.scalars(select(Access).where(Access.retire_le.is_(None), Access.debut <= now))
                if a.fin is None or a.fin > now}

    @app.get("/compte/formateur", response_class=HTMLResponse)
    def trainer(request: Request, parcours: str = "", q: str = "", user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur")
        require_trainer(db, user)
        all_parcours, current, students = trainer_data(db, parcours)
        try:
            labs = sum(1 for name in hub.running_servers() if HUB_NAME_RE.fullmatch(name))
        except Exception:  # noqa: BLE001 - Hub injoignable : le reste du tableau reste utile
            labs = None
        return page(request, "formateur.html", user=user, all_parcours=all_parcours, parcours=current, q=q,
                    resume=formateur.overview(students, labs, utcnow(), users_with_access(db)),
                    modules=formateur.module_stats(students, current),
                    avis=avis.summaries(db, [m["id"] for m in current["modules"]] if current else [],
                                        inscriptions.staff_emails(db, settings)),
                    students=sorted((st for st in students if formateur.matches(st, q)),
                                    key=lambda st: st.derniere_activite or datetime.min, reverse=True),
                    total=len(students), en_attente=inscriptions.waiting_count(db),
                    sans_reponse=len(questions.unanswered(db, inscriptions.staff_emails(db, settings))),
                    admin=inscriptions.is_admin(settings, user.email),
                    stuck_after=formateur.STUCK_AFTER)

    @app.get("/compte/formateur/etudiants/{student_id}", response_class=HTMLResponse)
    def trainer_student(request: Request, student_id: int, parcours: str = "", user=Depends(current_user),
                        db=Depends(get_db)):
        if not user:
            return login_redirect(f"/compte/formateur/etudiants/{student_id}")
        require_trainer(db, user)
        _, current, students = trainer_data(db, parcours)
        student = next((st for st in students if st.user.id == student_id), None)
        if not student:
            raise HTTPException(404, "Étudiant introuvable")
        certs = list(db.scalars(select(Certificate).where(Certificate.user_id == student.user.id)))
        return page(request, "formateur_etudiant.html", user=user, parcours=current, s=student, certificats=certs,
                    numero=certificats.format_code,
                    restantes=minutes_left(db, student.user, settings), stuck_after=formateur.STUCK_AFTER)

    @app.get("/compte/formateur/etudiants.csv")
    def trainer_csv(parcours: str = "", user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur")
        require_trainer(db, user)
        _, current, students = trainer_data(db, parcours)
        name = f"etudiants-{current['id'] if current else 'parcours'}-{utcnow():%Y-%m-%d}.csv"
        return Response(formateur.to_csv(students, current), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    # --- Accès offerts (bêta-testeurs, partenaires) : formateurs seulement

    def offered_page(request, user, db, status=200, **ctx):
        rows = db.execute(select(Access, User.email).join(User, User.id == Access.user_id)
                          .order_by(Access.debut.desc()).limit(300)).all()
        titres = {p["id"]: p["titre"] for p in catalogue()}
        now = utcnow()
        return page(request, "formateur_acces.html", status, user=user, parcours=catalogue(), titres=titres,
                    lignes=[{"acces": a, "email": email,
                             "valable": a.retire_le is None and a.debut <= now and (a.fin is None or a.fin > now)}
                            for a, email in rows],
                    acces_payant=settings.acces_payant, **ctx)

    @app.get("/compte/formateur/acces", response_class=HTMLResponse)
    def offered(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur/acces")
        require_trainer(db, user)
        return offered_page(request, user, db)

    @app.post("/compte/formateur/acces", response_class=HTMLResponse)
    def offer(request: Request, emails: str = Form(""), tous_les_comptes: str = Form(""), parcours: str = Form("*"),
              fin: str = Form(""), motif: str = Form(""), user=Depends(require_user), db=Depends(get_db),
              _=Depends(same_origin)):
        require_trainer(db, user)
        if parcours != acces.TOUS and parcours not in {p["id"] for p in catalogue()}:
            return offered_page(request, user, db, 400, erreur="Parcours inconnu.")
        try:
            end = datetime.strptime(fin, "%Y-%m-%d").replace(hour=23, minute=59) if fin.strip() else None
        except ValueError:
            return offered_page(request, user, db, 400, erreur="Date de fin illisible (attendu AAAA-MM-JJ).")
        if end and end <= utcnow():
            return offered_page(request, user, db, 400, erreur="La date de fin est déjà passée.")
        if tous_les_comptes == "oui":
            targets = list(db.scalars(select(User)))
            inconnues = []
        else:
            adresses, invalides = set(), []
            for e in (e for e in re.split(r"[\s,;]+", emails) if e.strip()):
                try:
                    adresses.add(normalize_email(e))
                except AuthError:
                    invalides.append(e)
            targets = list(db.scalars(select(User).where(User.email.in_(adresses)))) if adresses else []
            inconnues = sorted(adresses - {u.email for u in targets}) + invalides
        if not targets:
            return offered_page(request, user, db, 400, erreur="Aucun compte trouvé"
                                + (f" ({', '.join(inconnues)})" if inconnues else "") + ".")
        now = utcnow()
        for target in targets:
            db.add(Access(user_id=target.id, parcours_id=parcours, origine="offert", debut=now, fin=end,
                          motif=" ".join(motif.split())[:200]))
        db.commit()
        log.info("Accès offert par %s à %d compte(s) : %s jusqu'au %s", user.email, len(targets), parcours,
                 end.date() if end else "sans fin")
        info = f"Accès offert à {len(targets)} compte{'s' if len(targets) > 1 else ''}."
        if inconnues:
            info += f" Sans compte (à créer d'abord) : {', '.join(inconnues)}."
        return offered_page(request, user, db, info=info)

    @app.post("/compte/formateur/acces/{access_id}/retirer")
    def offer_remove(access_id: int, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        require_trainer(db, user)
        row = db.get(Access, access_id)
        if not row:
            raise HTTPException(404, "Accès introuvable")
        if row.origine != "offert":
            raise HTTPException(409, "Un accès payé ne se retire pas ici : remboursez-le depuis Stripe")
        if not row.retire_le:
            row.retire_le = utcnow()
            db.commit()
            log.info("Accès %s (u%s, %s) retiré par %s", row.id, row.user_id, row.parcours_id, user.email)
        return RedirectResponse("/compte/formateur/acces", status_code=303)

    # --- Questions des étudiants : formateurs

    @app.get("/compte/formateur/questions", response_class=HTMLResponse)
    def trainer_questions(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur/questions")
        require_trainer(db, user)
        now = utcnow()
        rows = questions.unanswered(db, inscriptions.staff_emails(db, settings))
        votes, _ = questions.votes_of(db, [q.id for q, _u in rows])
        attente = [{"q": q, "u": u, "attente": now - q.cree_le, "alerte": now - q.cree_le > questions.ATTENTE_ALERTE,
                    "meme": votes.get(q.id, 0)} for q, u in rows]
        signales_q, signales_r = questions.reported(db)
        return page(request, "formateur_questions.html", user=user, attente=attente, titres=module_titles(),
                    signales_q=signales_q, signales_r=signales_r,
                    questions_de={a.id: db.get(Question, a.question_id) for a in signales_r})

    # --- Avis des étudiants : formateurs

    def module_titles():
        return {m["id"]: m["titre"] for p in catalogue() for m in p["modules"]}

    @app.get("/compte/formateur/avis", response_class=HTMLResponse)
    def trainer_feedback(request: Request, module: str = "", user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur/avis")
        require_trainer(db, user)
        titres = module_titles()
        module = module if module in titres else ""
        rows = avis.listing(db, module or None, inscriptions.staff_emails(db, settings))
        return page(request, "formateur_avis.html", user=user, lignes=rows, titres=titres, module=module,
                    parcours=catalogue(), difficultes=avis.DIFFICULTES)

    @app.get("/compte/formateur/avis.csv")
    def trainer_feedback_csv(user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur/avis")
        require_trainer(db, user)
        rows = avis.listing(db, None, inscriptions.staff_emails(db, settings), limit=100000)
        return Response(avis.to_csv(rows, module_titles()), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="avis-{utcnow():%Y-%m-%d}.csv"'})

    # --- Inscriptions (places, liste d'attente, vagues) : formateurs

    STATUT_ORDRE = {inscriptions.ATTENTE: 0, inscriptions.ACTIF: 1, inscriptions.NOUVEAU: 2, inscriptions.DESINSCRIT: 3}

    def signups_page(request, user, db, status=200, statut="", **ctx):
        staff = inscriptions.staff_emails(db, settings)
        rangs = {u.id: i for i, u in enumerate(inscriptions.waiting(db), 1)}
        comptes = [u for u in db.scalars(select(User).order_by(User.cree_le.desc())) if u.email not in staff]
        comptes.sort(key=lambda u: (STATUT_ORDRE.get(u.statut, 9), rangs.get(u.id, 0)))
        compte = {s: sum(1 for u in comptes if u.statut == s) for s in STATUT_ORDRE}
        if statut in STATUT_ORDRE:
            comptes = [u for u in comptes if u.statut == statut]
        return page(request, "formateur_inscriptions.html", status, user=user, comptes=comptes, rangs=rangs,
                    nombre=compte, statut=statut, places=inscriptions.places(db),
                    occupees=inscriptions.occupied(db, settings), libres=inscriptions.free(db, settings), **ctx)

    def signup_target(db, user_id):
        target = db.get(User, user_id)
        if not target or inscriptions.is_staff(db, settings, target.email):
            raise HTTPException(404, "Compte introuvable")
        return target

    def invite(users):
        """Prévient par e-mail les comptes activés ; renvoie le nombre d'envois échoués."""
        return sum(0 if notify(u.email, "activation", f"{settings.public_url}/connexion") else 1 for u in users)

    def invited_info(users, echecs):
        if not users:
            return "Personne n'était en attente sur les places libres."
        info = f"{len(users)} compte{'s' if len(users) > 1 else ''} activé{'s' if len(users) > 1 else ''} et prévenu{'s' if len(users) > 1 else ''} par e-mail."
        if echecs:
            info += f" {echecs} e-mail{'s' if echecs > 1 else ''} n'{'ont' if echecs > 1 else 'a'} pas pu partir (voir les journaux)."
        return info

    @app.get("/compte/formateur/inscriptions", response_class=HTMLResponse)
    def signups(request: Request, statut: str = "", user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur/inscriptions")
        require_trainer(db, user)
        return signups_page(request, user, db, statut=statut)

    @app.post("/compte/formateur/inscriptions/places", response_class=HTMLResponse)
    def signups_places(request: Request, places: str = Form(""), user=Depends(require_user), db=Depends(get_db),
                       _=Depends(same_origin)):
        require_trainer(db, user)
        value = places.strip()
        if value and (not value.isdigit() or int(value) > inscriptions.PLACES_MAX):
            return signups_page(request, user, db, 400, erreur="Nombre de places invalide (un entier, ou vide).")
        n = int(value) if value else None
        inscriptions.set_places(db, n)
        log.info("Places des inscriptions : %s (par %s)", n if n is not None else "sans limite", user.email)
        return signups_page(request, user, db, info="Inscriptions sans limite." if n is None else
                            f"{n} place{'s' if n > 1 else ''} au total. Les comptes déjà actifs le restent.")

    @app.post("/compte/formateur/inscriptions/vague", response_class=HTMLResponse)
    def signups_wave(request: Request, places: str = Form("0"), user=Depends(require_user), db=Depends(get_db),
                     _=Depends(same_origin)):
        require_trainer(db, user)
        value = places.strip() or "0"
        if not value.isdigit() or int(value) > inscriptions.PLACES_MAX:
            return signups_page(request, user, db, 400, erreur="Nombre de places invalide.")
        invited = inscriptions.open_wave(db, settings, int(value))
        log.info("Vague ouverte par %s : +%s places, %d compte(s) invité(s)", user.email, value, len(invited))
        return signups_page(request, user, db, info=invited_info(invited, invite(invited)))

    @app.post("/compte/formateur/inscriptions/{user_id}/activer", response_class=HTMLResponse)
    def signup_activate(request: Request, user_id: int, user=Depends(require_user), db=Depends(get_db),
                        _=Depends(same_origin)):
        require_trainer(db, user)
        target = signup_target(db, user_id)
        if target.statut != inscriptions.ACTIF:
            inscriptions.activate(db, target)
            log.info("u%s activé par %s", target.id, user.email)
            if target.email_verifie_le:  # adresse pas encore confirmée : le lien de confirmation suffit
                return signups_page(request, user, db, info=invited_info([target], invite([target])))
        return RedirectResponse("/compte/formateur/inscriptions", status_code=303)

    @app.post("/compte/formateur/inscriptions/{user_id}/desinscrire")
    def signup_remove(user_id: int, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        require_trainer(db, user)
        target = signup_target(db, user_id)
        if target.statut != inscriptions.DESINSCRIT:
            inscriptions.unsubscribe(db, target)
            revoke_sessions(db, target)
            try:
                hub.stop(target.hub_name)
            except Exception:  # noqa: BLE001 - Hub injoignable : le lab s'arrêtera faute de session
                log.warning("Arrêt du lab de u%s impossible", target.id)
            log.info("u%s désinscrit par %s", target.id, user.email)
        return RedirectResponse("/compte/formateur/inscriptions", status_code=303)

    # --- Équipe des formateurs : administrateurs seulement

    def team_page(request, user, db, status=200, **ctx):
        return page(request, "formateur_equipe.html", status, user=user, admins=sorted(settings.admin_emails),
                    formateurs=list(db.scalars(select(Trainer).order_by(Trainer.ajoute_le))), **ctx)

    @app.get("/compte/formateur/equipe", response_class=HTMLResponse)
    def team(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur/equipe")
        require_admin(user)
        return team_page(request, user, db)

    @app.post("/compte/formateur/equipe", response_class=HTMLResponse)
    def team_add(request: Request, email: str = Form(""), user=Depends(require_user), db=Depends(get_db),
                 _=Depends(same_origin)):
        require_admin(user)
        try:
            email = normalize_email(email)
        except AuthError as exc:
            return team_page(request, user, db, 400, erreur=str(exc))
        if inscriptions.is_staff(db, settings, email):
            return team_page(request, user, db, 400, erreur=f"{email} fait déjà partie de l'équipe.")
        db.add(Trainer(email=email, ajoute_par=user.email))
        account = db.scalar(select(User).where(User.email == email))
        if account and account.statut != inscriptions.ACTIF:
            account.statut, account.attente_depuis = inscriptions.ACTIF, None  # un formateur n'attend pas
        db.commit()
        log.info("Formateur %s ajouté par %s", email, user.email)
        sent = notify(email, "formateur", f"{settings.public_url}/connexion?suite=/compte/formateur")
        return team_page(request, user, db, info=f"{email} a rejoint l'équipe" + (
            " et a été prévenu par e-mail." if sent else " (l'e-mail n'a pas pu partir : prévenez-le vous-même)."))

    @app.post("/compte/formateur/equipe/retirer")
    def team_remove(email: str = Form(""), user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        require_admin(user)
        row = db.get(Trainer, email.strip().lower())
        if not row:
            raise HTTPException(404, "Formateur introuvable")
        db.delete(row)
        db.commit()
        log.info("Formateur %s retiré par %s", row.email, user.email)
        return RedirectResponse("/compte/formateur/equipe", status_code=303)

    # --- Résultats

    def progress(db, user, module):
        notes = [a.note for a in db.scalars(select(QcmAttempt).where(QcmAttempt.user_id == user.id,
                                                                     QcmAttempt.module == module))]
        ex = db.get(Exercise, (user.id, module))
        return notes, ex

    def all_parcours():
        try:
            return contenus.parcours()
        except Exception:  # noqa: BLE001
            raise HTTPException(503, "Les parcours sont momentanément indisponibles") from None

    def certificate_eligibility(db, user, p):
        state = {}
        for m in p["modules"]:
            notes, ex = progress(db, user, m["id"])
            state[m["id"]] = (notes, bool(ex and ex.reussi_le), ex.indices if ex else 0)
        return certificats.eligibility(p, state, settings.certificat_note_min)

    def parcours_progress(db, user, p):
        """État de l'étudiant dans un parcours : notes, état de chaque module, prochain module."""
        rows, weighted = [], []
        for m in p["modules"]:
            notes, ex = progress(db, user, m["id"])
            g = grading.grade_of(m, notes, bool(ex and ex.reussi_le), ex.indices if ex else 0)
            if grading.counts(m):
                weighted.append((m["coef"], g))
            commence = bool(notes) or ex is not None
            etat = "termine" if g.termine else ("en_cours" if commence else "a_faire")
            rows.append({"module": m, "grade": g, "tentatives": len(notes), "etat": etat,
                         "indices": ex.indices if ex else 0, "reussi": bool(ex and ex.reussi_le)})
        # progression et note finale : les modules obligatoires (les bonus restent à part)
        requis = [r for r in rows if grading.counts(r["module"])]
        termines = sum(1 for r in requis if r["etat"] == "termine")
        # prochain module : le premier en cours, sinon le premier à faire
        prochain = next((r["module"] for r in rows if r["etat"] == "en_cours"),
                        next((r["module"] for r in rows if r["etat"] == "a_faire"), None))
        return {"parcours": p, "modules": rows, "finale": grading.final_grade(weighted), "termines": termines,
                "requis": len(requis), "commence": any(r["etat"] != "a_faire" for r in rows), "prochain": prochain,
                "pourcentage": round(100 * termines / len(requis)) if requis else 0}

    @app.get("/compte/resultats", response_class=HTMLResponse)
    def resultats(request: Request, erreur: str = "", user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/resultats")
        out = []
        for p in all_parcours():
            r = parcours_progress(db, user, p)
            r.update(certificat=certificats.existing(db, user.id, p["id"]), eligible=certificate_eligibility(db, user, p))
            out.append(r)
        return page(request, "resultats.html", user=user, resultats=out, note_min=settings.certificat_note_min,
                    erreur=erreur[:300])

    @app.get("/compte/apprentissage", response_class=HTMLResponse)
    def apprentissage(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/apprentissage")
        suivis = []
        for p in all_parcours():
            r = parcours_progress(db, user, p)
            r["certificat"] = certificats.existing(db, user.id, p["id"])
            suivis.append(r)
        # « Reprendre » : le parcours commencé (sinon le premier) qui a encore un module à faire
        actif = next((r for r in suivis if r["commence"] and r["prochain"]),
                     next((r for r in suivis if r["prochain"]), None))
        notes = [m["grade"].note for r in suivis for m in r["modules"] if m["etat"] == "termine"]
        return page(request, "apprentissage.html", user=user, suivis=suivis, actif=actif,
                    termines=len(notes), moyenne=round(sum(notes) / len(notes), 1) if notes else None,
                    utilisees=minutes_used(db, user), restantes=minutes_left(db, user, settings),
                    certificats=[r["certificat"] for r in suivis if r["certificat"] and not r["certificat"].revoque_le])

    @app.get("/api/comptes/progression/{parcours_id}")
    def progression(parcours_id: str, user=Depends(current_user), db=Depends(get_db)):
        """Page d'un parcours : état de chaque module (vide sans session)."""
        if not user:
            return {"connecte": False}
        p = next((x for x in all_parcours() if x["id"] == parcours_id), None)
        if not p:
            raise HTTPException(404, "Parcours introuvable")
        r = parcours_progress(db, user, p)
        return {"connecte": True, "acces": acces.can_open(accessible(db, user), [parcours_id]),
                "termines": r["termines"], "total": r["requis"],
                "prochain": r["prochain"]["id"] if r["prochain"] else None,
                "prochain_titre": r["prochain"]["titre"] if r["prochain"] else None,
                "modules": {m["module"]["id"]: {"etat": m["etat"], "note": m["grade"].note if m["etat"] == "termine" else None}
                            for m in r["modules"]}}

    # --- Certificats

    @app.post("/compte/certificats")
    def certificate_issue(parcours: str = Form(...), nom: str = Form(""), user=Depends(require_user),
                          db=Depends(get_db), _=Depends(same_origin)):
        p = next((x for x in all_parcours() if x["id"] == parcours), None)
        if not p:
            raise HTTPException(404, "Parcours introuvable")
        try:
            cert = certificats.issue(db, user, p, certificate_eligibility(db, user, p), nom)
        except certificats.CertificateError as exc:
            return RedirectResponse(f"/compte/resultats?erreur={quote(str(exc), safe='')}#certificat", status_code=303)
        log.info("Certificat %s délivré à u%s (%s, %.2f)", cert.code, user.id, p["id"], cert.note)
        return RedirectResponse(f"/certificats/{cert.code}", status_code=303)

    def certificate_or_404(db, raw):
        code = certificats.normalize_code(raw)
        cert = db.get(Certificate, code) if code else None
        if not cert:
            raise HTTPException(404, "Aucun certificat ne porte ce numéro")
        return cert

    @app.get("/certificats/{code}.pdf")
    def certificate_pdf(code: str, db=Depends(get_db)):
        cert = certificate_or_404(db, code)
        if cert.revoque_le:
            raise HTTPException(410, "Ce certificat a été révoqué")
        pdf = certificats.render_pdf(cert, f"{settings.public_url}/certificats/{cert.code}")
        return Response(pdf, media_type="application/pdf", headers={
            "Content-Disposition": f'inline; filename="certificat-roboforge-{cert.code}.pdf"'})

    @app.get("/certificats/{code}", response_class=HTMLResponse)
    def certificate_page(request: Request, code: str, user=Depends(current_user), db=Depends(get_db)):
        cert = certificate_or_404(db, code)
        if code != cert.code:
            return RedirectResponse(f"/certificats/{cert.code}", status_code=301)  # forme imprimée ABCD-EFGH-…
        return page(request, "certificat.html", cert=cert, modules=certificats.modules(cert),
                    numero=certificats.format_code(cert.code), date=certificats.date_fr(cert.emis_le),
                    revoque=certificats.date_fr(cert.revoque_le) if cert.revoque_le else None,
                    proprietaire=bool(user and user.id == cert.user_id), fr=certificats.fr)

    @app.post("/compte/formateur/certificats/{code}/revoquer")
    def certificate_revoke(code: str, motif: str = Form(""), user=Depends(require_user), db=Depends(get_db),
                           _=Depends(same_origin)):
        require_trainer(db, user)
        cert = certificate_or_404(db, code)
        if not cert.revoque_le:
            cert.revoque_le, cert.revoque_motif = utcnow(), " ".join(motif.split())[:200]
            db.commit()
            log.warning("Certificat %s révoqué par %s : %s", cert.code, user.email, cert.revoque_motif)
        return RedirectResponse(f"/compte/formateur/etudiants/{cert.user_id}", status_code=303)

    # --- API (Lab UI et pages du site)

    @app.get("/api/comptes/session")
    def session_state(user=Depends(current_user)):
        """En-tête du site : toujours 200, pour ne pas remplir la console de 401."""
        if not user:
            return {"connecte": False}
        return {"connecte": True, "nom": user.nom, "email": user.email}

    @app.get("/api/comptes/interne/session")
    def internal_session(user=Depends(current_user), db=Depends(get_db)):
        """Caddy (forward_auth) avant le cours d'un module : session ouverte ou non.

        Toujours 200 : le service Contenus affiche la page réservée sans session, ou sans accès au
        parcours (X-Academy-Acces : « * » ou les parcours ouverts). Caddy bloque /api/comptes/interne/
        depuis le navigateur ; seuls ces en-têtes sont recopiés vers Contenus.
        """
        headers = {"X-Academy-Etudiant": "1" if user else "0"}
        if user:
            headers["X-Academy-Acces"] = acces.header_value(accessible(db, user))
        return Response(status_code=200, headers=headers)

    @app.get("/api/comptes/moi")
    def moi(user=Depends(require_user), db=Depends(get_db)):
        return {"nom": user.nom, "email": user.email, "formule": lab_plan(db, user), "hub": user.hub_name,
                "minutes_restantes": minutes_left(db, user, settings), "minutes_utilisees": minutes_used(db, user)}

    @app.get("/api/comptes/qcm/{module}")
    def qcm_state(module: str, user=Depends(require_user), db=Depends(get_db)):
        require_module_access(db, user, module)
        notes, _ = progress(db, user, module)
        return {"tentatives": len(notes), "restantes": max(0, grading.MAX_QCM_ATTEMPTS - len(notes)),
                "meilleure": max(notes) if notes else None}

    @app.post("/api/comptes/qcm/{module}")
    def qcm_submit(module: str, body: QcmBody, user=Depends(require_user), db=Depends(get_db),
                   _=Depends(same_origin)):
        require_module_access(db, user, module)
        notes, _ = progress(db, user, module)
        if len(notes) >= grading.MAX_QCM_ATTEMPTS:
            raise HTTPException(409, "Vous avez déjà utilisé vos 2 tentatives pour ce QCM")
        try:
            result = contenus.correct_qcm(module, body.reponses)
        except UpstreamError as exc:
            raise HTTPException(404 if exc.status == 404 else 502, "Correction indisponible") from None
        db.add(QcmAttempt(user_id=user.id, module=module, note=float(result["note"])))
        db.commit()
        notes.append(float(result["note"]))
        return {**result, "tentative": len(notes), "restantes": grading.MAX_QCM_ATTEMPTS - len(notes),
                "meilleure": max(notes)}

    # --- Questions et réponses sur les modules

    def question_or_404(db, user, question_id):
        q = db.get(Question, question_id)
        staff = inscriptions.is_staff(db, settings, user.email)
        if not q or not questions.can_see(q, user, staff):
            raise HTTPException(404, "Question introuvable")
        require_module_access(db, user, q.module)
        return q, staff

    def require_staff(db, user):
        if not inscriptions.is_staff(db, settings, user.email):
            raise HTTPException(403, "Réservé à l'équipe des formateurs")

    def one_question(db, q, user, staff):
        return questions.as_json(db, [q], user, staff)[0]

    @app.get("/api/comptes/questions/{module}")
    def questions_list(module: str, user=Depends(require_user), db=Depends(get_db)):
        known_module(module)
        require_module_access(db, user, module)
        staff = inscriptions.is_staff(db, settings, user.email)
        return {"equipe": staff,
                "questions": questions.as_json(db, questions.listing(db, module, user, staff), user, staff)}

    @app.post("/api/comptes/questions/{module}")
    def question_ask(module: str, body: QuestionBody, user=Depends(require_user), db=Depends(get_db),
                     _=Depends(same_origin)):
        known_module(module)
        require_module_access(db, user, module)
        try:
            q = questions.ask(db, user, module, body.titre, body.texte, body.prive, body.solution,
                              body.joindre_verification)
        except questions.InvalidPost as exc:
            raise HTTPException(400, str(exc)) from None
        log.info("Question %s posée par u%s sur %s", q.id, user.id, module)
        return {"question": one_question(db, q, user, inscriptions.is_staff(db, settings, user.email))}

    @app.post("/api/comptes/questions/{question_id}/reponses")
    def question_answer(question_id: int, body: AnswerBody, user=Depends(require_user), db=Depends(get_db),
                        _=Depends(same_origin)):
        q, staff = question_or_404(db, user, question_id)
        try:
            questions.answer(db, user, q, body.texte, body.solution, staff)
        except questions.InvalidPost as exc:
            raise HTTPException(400, str(exc)) from None
        link = f"{settings.public_url}/modules/{q.module}/#question-{q.id}"
        author = db.get(User, q.user_id)
        if author and author.id != user.id:
            notify(author.email, "nouvelle_reponse", link)
        if staff:  # réponse de l'équipe : ceux qui ont la même question sont prévenus aussi
            for follower in questions.followers(db, q):
                if follower.id != user.id:
                    notify(follower.email, "meme_question", link)
        return {"question": one_question(db, q, user, staff)}

    @app.post("/api/comptes/questions/{question_id}/meme")
    def question_same(question_id: int, body: FlagBody, user=Depends(require_user), db=Depends(get_db),
                      _=Depends(same_origin)):
        q, staff = question_or_404(db, user, question_id)
        try:
            questions.same_question(db, user, q, body.valeur)
        except questions.InvalidPost as exc:
            raise HTTPException(400, str(exc)) from None
        return {"question": one_question(db, q, user, staff)}

    @app.post("/api/comptes/questions/{question_id}/resolue")
    def question_resolved(question_id: int, body: FlagBody, user=Depends(require_user), db=Depends(get_db),
                          _=Depends(same_origin)):
        q, staff = question_or_404(db, user, question_id)
        if q.user_id != user.id and not staff:
            raise HTTPException(403, "Seul l'auteur ou l'équipe peut marquer la question comme résolue")
        q.resolue_le = utcnow() if body.valeur else None
        db.commit()
        return {"question": one_question(db, q, user, staff)}

    @app.post("/api/comptes/questions/{question_id}/masquer")
    def question_hide(question_id: int, body: FlagBody, user=Depends(require_user), db=Depends(get_db),
                      _=Depends(same_origin)):
        require_staff(db, user)
        q, staff = question_or_404(db, user, question_id)
        q.masquee_le = utcnow() if body.valeur else None
        db.commit()
        log.info("Question %s %s par %s", q.id, "masquée" if body.valeur else "rétablie", user.email)
        return {"question": one_question(db, q, user, staff)}

    @app.post("/api/comptes/questions/{question_id}/signaler")
    def question_report(question_id: int, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        q, _staff = question_or_404(db, user, question_id)
        q.signalements += 1
        db.commit()
        return {"signale": True}

    def answer_or_404(db, user, answer_id):
        a = db.get(Answer, answer_id)
        if not a:
            raise HTTPException(404, "Réponse introuvable")
        q, staff = question_or_404(db, user, a.question_id)
        if a.masquee_le is not None and not staff:
            raise HTTPException(404, "Réponse introuvable")
        return a, q, staff

    @app.post("/api/comptes/reponses/{answer_id}/valider")
    def answer_validate(answer_id: int, body: FlagBody, user=Depends(require_user), db=Depends(get_db),
                        _=Depends(same_origin)):
        require_staff(db, user)
        a, q, staff = answer_or_404(db, user, answer_id)
        a.validee = body.valeur
        db.commit()
        return {"question": one_question(db, q, user, staff)}

    @app.post("/api/comptes/reponses/{answer_id}/masquer")
    def answer_hide(answer_id: int, body: FlagBody, user=Depends(require_user), db=Depends(get_db),
                    _=Depends(same_origin)):
        require_staff(db, user)
        a, q, staff = answer_or_404(db, user, answer_id)
        a.masquee_le = utcnow() if body.valeur else None
        db.commit()
        log.info("Réponse %s %s par %s", a.id, "masquée" if body.valeur else "rétablie", user.email)
        return {"question": one_question(db, q, user, staff)}

    @app.post("/api/comptes/reponses/{answer_id}/signaler")
    def answer_report(answer_id: int, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        a, _q, _staff = answer_or_404(db, user, answer_id)
        a.signalements += 1
        db.commit()
        return {"signale": True}

    # --- Avis sur les modules (phase de test)

    def known_module(module):
        check_module(module)
        ids = {m["id"] for p in catalogue() for m in p["modules"]}
        if ids and module not in ids:
            raise HTTPException(404, "Module introuvable")

    @app.get("/api/comptes/avis/{module}")
    def feedback_state(module: str, user=Depends(require_user), db=Depends(get_db)):
        known_module(module)
        return {"avis": avis.as_json(db.get(ModuleFeedback, (user.id, module)))}

    @app.post("/api/comptes/avis/{module}")
    def feedback_save(module: str, body: FeedbackBody, user=Depends(require_user), db=Depends(get_db),
                      _=Depends(same_origin)):
        known_module(module)
        require_module_access(db, user, module)
        try:
            row = avis.save(db, user, module, body.note, body.difficulte, body.commentaire)
        except avis.InvalidFeedback as exc:
            raise HTTPException(400, str(exc)) from None
        return {"avis": avis.as_json(row)}

    def exercise_row(db, user, module):
        ex = db.get(Exercise, (user.id, module))
        if not ex:
            ex = Exercise(user_id=user.id, module=module, indices=0)
            db.add(ex)
            db.flush()
        return ex

    @app.get("/api/comptes/exercices/{module}")
    def exercise_state(module: str, user=Depends(require_user), db=Depends(get_db)):
        require_module_access(db, user, module)
        ex = db.get(Exercise, (user.id, module))
        return {"indices": ex.indices if ex else 0, "reussi": bool(ex and ex.reussi_le)}

    @app.post("/api/comptes/exercices/{module}/indices/{n}")
    def exercise_hint(module: str, n: int, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        require_module_access(db, user, module)
        ex = exercise_row(db, user, module)
        if not 1 <= n <= grading.MAX_HINTS or n > ex.indices + 1:
            raise HTTPException(400, "Les indices se demandent dans l'ordre")
        try:
            hint = contenus.hint(module, n)
        except UpstreamError as exc:
            raise HTTPException(404 if exc.status == 404 else 502, "Indice indisponible") from None
        if n > ex.indices and not ex.reussi_le:
            ex.indices = n  # compté avant d'être renvoyé
        db.commit()
        return {"n": n, "html": hint["html"], "indices": ex.indices}

    verifying = set()  # une vérification à la fois par étudiant
    verifying_lock = threading.Lock()

    @app.post("/api/comptes/exercices/{module}/verification")
    def exercise_verification(module: str, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        """La réussite n'est enregistrée que si le check.sh officiel réussit hors du conteneur de l'étudiant."""
        require_module_access(db, user, module)
        with verifying_lock:
            if user.id in verifying:
                raise HTTPException(409, "Une vérification est déjà en cours")
            verifying.add(user.id)
        try:
            result = contenus.verify(module, user.hub_name)
        except UpstreamError as exc:
            if exc.status == 429:
                raise HTTPException(429, "Le serveur de vérification est occupé : réessayez dans un instant") from None
            raise HTTPException(404 if exc.status == 404 else 502, "Vérification indisponible") from None
        finally:
            with verifying_lock:
                verifying.discard(user.id)
        ex = exercise_row(db, user, module)
        ex.verifications = (ex.verifications or 0) + 1
        ex.dernier_journal = str(result.get("journal", ""))[-4000:]
        if result.get("ok") is True and not ex.reussi_le:
            ex.reussi_le = utcnow()
        db.commit()
        return {"reussi": bool(ex.reussi_le), "verification": bool(result.get("ok") is True),
                "journal": str(result.get("journal", ""))[-4000:], "indices": ex.indices}

    @app.get("/api/comptes/exercices/{module}/explication")
    def exercise_explanation(module: str, user=Depends(require_user), db=Depends(get_db)):
        require_module_access(db, user, module)
        ex = db.get(Exercise, (user.id, module))
        if not ex or not ex.reussi_le:
            raise HTTPException(403, "L'explication s'affiche une fois l'exercice réussi")
        try:
            return contenus.explanation(module)
        except UpstreamError:
            raise HTTPException(502, "Explication indisponible") from None

    # --- Route interne : le Hub demande avant chaque démarrage si le quota le permet

    hub_secret = comptes_token(settings.jwt_secret)

    @app.get("/api/comptes/interne/lab/{name}")
    def internal_lab(name: str, request: Request, db=Depends(get_db)):
        if not hmac.compare_digest(request.headers.get(INTERNAL_HEADER, ""), hub_secret):
            raise HTTPException(403, "Route interne")
        m = HUB_NAME_RE.fullmatch(name)
        user = db.get(User, int(m.group(1))) if m else None
        if not user:
            raise HTTPException(404, "Compte inconnu")
        return {"autorise": user.statut == inscriptions.ACTIF and minutes_left(db, user, settings) != 0}

    # --- File d'attente

    def free_seats():
        if time.time() - state["releve"] > 15:
            try:
                state["actifs"], state["releve"] = len(hub.running_servers()), time.time()
            except Exception:  # noqa: BLE001
                pass
        return max(0, settings.active_server_limit - state["actifs"])

    def own_ticket(db, user, ticket):
        row = db.get(QueueTicket, ticket)
        if not row or row.user_id != user.id:
            raise HTTPException(404, "Ticket expiré")

    def queue_json(db, ticket):
        position = queue_position(db, ticket)
        if position is None:
            raise HTTPException(404, "Ticket expiré")
        return {"ticket": ticket, "position": position, "a_vous": position <= free_seats()}

    @app.post("/api/comptes/file")
    def queue_join(user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        return queue_json(db, join_queue(db, user).ticket)

    @app.post("/api/comptes/file/{ticket}")
    def queue_beat(ticket: str, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        own_ticket(db, user, ticket)
        return queue_json(db, ticket)

    @app.delete("/api/comptes/file/{ticket}")
    def queue_leave(ticket: str, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        own_ticket(db, user, ticket)
        leave_queue(db, ticket)
        return {"ok": True}

    return app


def app_from_env():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # une ligne par requête au Hub, chaque minute
    return create_app(Settings.from_env())

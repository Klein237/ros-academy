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
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from . import certificats, formateur, grading, rgpd
from .billing import PAYING, BadSignature, StripeClient, StripeError, apply_subscription, format_price, verify_signature
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
    Base,
    Certificate,
    Exercise,
    QcmAttempt,
    QueueTicket,
    SessionRow,
    StripeEvent,
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
    # form-action s'applique aussi à la redirection qui suit un formulaire (« S'abonner » → Stripe)
    form = " ".join(("'self'", *form_targets))
    return ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            f"connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action {form}; object-src 'none'")


class QcmBody(BaseModel):
    reponses: dict[str, list[int]] = {}


def mint_lab_token(secret, user):
    now = int(time.time())
    return jwt.encode({"sub": user.hub_name, "plan": user.formule, "aud": "ros-lab", "iat": now,
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
    state = {"actifs": 0, "releve": 0.0, "prix": None, "prix_lu": 0.0}

    def tick():
        with SessionLocal() as db:
            actifs, stopped = record_minute(db, hub, settings)
        state["actifs"], state["releve"] = actifs, time.time()
        for name in stopped:
            log.info("Quota épuisé : serveur de %s arrêté", name)

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
        yield
        if task:
            task.cancel()

    app = FastAPI(title="Comptes ROS Academy", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.session_factory = SessionLocal
    app.state.tick = tick
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
        return sessions.user(db, request.cookies.get(SESSION_COOKIE))

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

    def check_module(module):
        if not MODULE_ID_RE.fullmatch(module):
            raise HTTPException(404, "Module introuvable")

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
        return open_session(db, user, suite)

    @app.get("/connexion/inscription", response_class=HTMLResponse)
    def inscription(request: Request, suite: str = "/", user=Depends(current_user)):
        if user:
            return RedirectResponse(safe_next(suite), status_code=303)
        return page(request, "inscription.html", suite=safe_next(suite))

    @app.post("/connexion/inscription", response_class=HTMLResponse)
    def inscription_post(request: Request, nom: str = Form(""), email: str = Form(...), mot_de_passe: str = Form(...),
                         suite: str = Form("/"), db=Depends(get_db), _=Depends(same_origin)):
        nom = nom.strip()[:120]
        try:
            email = normalize_email(email)
            check_new_password(mot_de_passe)
        except AuthError as exc:
            return page(request, "inscription.html", 400, suite=safe_next(suite), erreur=str(exc), nom=nom,
                        email=email[:320])
        titre = "Vérifiez votre boîte de réception"
        message = f"Nous avons envoyé un e-mail à {email}. Ouvrez le lien qu'il contient pour activer votre compte."
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
        return open_session(db, user, suite)

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
        return open_session(db, user, suite)

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
        return open_session(db, user_for_email(db, email, nom, provider, sujet), suite)

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

    @app.get("/compte/", response_class=HTMLResponse)
    def compte(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/")
        return page(request, "compte.html", user=user, utilisees=minutes_used(db, user),
                    restantes=minutes_left(db, user, settings), admin=user.email in settings.admin_emails)

    @app.post("/compte/mot-de-passe", response_class=HTMLResponse)
    def compte_mot_de_passe(request: Request, actuel: str = Form(""), nouveau: str = Form(...),
                            user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        def retour(status, **ctx):
            return page(request, "compte.html", status, user=user, utilisees=minutes_used(db, user),
                        restantes=minutes_left(db, user, settings), admin=user.email in settings.admin_emails, **ctx)
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
        if minutes_left(db, user, settings) == 0:
            return page(request, "message.html", 403, titre="Quota de lab épuisé",
                        message="Vous avez utilisé toutes vos minutes de lab ce mois-ci. Les cours, les QCM et vos "
                                "notes restent accessibles ; le lab sera de nouveau disponible le mois prochain.",
                        **({"lien": "/compte/abonnement", "lien_texte": "Passer en pro : lab sans limite"}
                           if settings.billing_enabled else
                           {"lien": "/compte/resultats", "lien_texte": "Voir mes résultats"}))
        token = mint_lab_token(settings.jwt_secret, user)
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
                        headers={"Content-Disposition": 'attachment; filename="ros-academy-mes-donnees.json"',
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
        except rgpd.DeletionRefused as exc:
            return page(request, "supprimer.html", 409, user=user, erreur=str(exc))
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

    # --- Abonnement (formule pro, Stripe)

    def require_billing():
        if not settings.billing_enabled:
            raise HTTPException(404, "Page introuvable")

    def price_text():
        if time.time() - state["prix_lu"] > 3600:
            try:
                state["prix"], state["prix_lu"] = format_price(stripe.price(settings.stripe_price_id)), time.time()
            except StripeError as exc:
                log.warning("Prix Stripe illisible : %s", exc)
        return state["prix"]

    @app.get("/compte/abonnement", response_class=HTMLResponse, dependencies=[Depends(require_billing)])
    def abonnement(request: Request, retour: str = "", user=Depends(current_user)):
        if not user:
            return login_redirect("/compte/abonnement")
        return page(request, "abonnement.html", user=user, prix=price_text(), actif=user.abonnement_statut in PAYING,
                    en_attente=retour == "paye" and user.formule != "pro")

    @app.post("/compte/abonnement/souscrire", dependencies=[Depends(require_billing)])
    def souscrire(user=Depends(require_user), _=Depends(same_origin)):
        if user.abonnement_statut in PAYING:
            raise HTTPException(409, "Vous êtes déjà abonné : gérez votre abonnement depuis votre compte")
        try:
            url = stripe.create_checkout(user, settings.stripe_price_id,
                                         f"{settings.public_url}/compte/abonnement?retour=paye",
                                         f"{settings.public_url}/compte/abonnement")
        except StripeError as exc:
            log.warning("Session de paiement impossible : %s", exc)
            raise HTTPException(502, "Le paiement est momentanément indisponible, réessayez plus tard") from None
        return RedirectResponse(url, status_code=303)

    @app.post("/compte/abonnement/gerer", dependencies=[Depends(require_billing)])
    def gerer(user=Depends(require_user), _=Depends(same_origin)):
        if not user.stripe_customer_id:
            raise HTTPException(404, "Aucun abonnement à gérer")
        try:
            url = stripe.create_portal(user.stripe_customer_id, f"{settings.public_url}/compte/abonnement")
        except StripeError as exc:
            log.warning("Portail client impossible : %s", exc)
            raise HTTPException(502, "La gestion de l'abonnement est momentanément indisponible") from None
        return RedirectResponse(url, status_code=303)

    def handle_event(event):
        """Applique un événement Stripe vérifié ; renvoie False s'il était déjà traité."""
        with SessionLocal() as db:
            if db.get(StripeEvent, event["id"]):
                return False
            obj = (event.get("data") or {}).get("object") or {}
            user, subscription_id = None, None
            if event.get("type") == "checkout.session.completed" and obj.get("mode") == "subscription":
                ref = str(obj.get("client_reference_id") or "")
                user = db.get(User, int(ref)) if ref.isdigit() else None
                if user and obj.get("customer"):
                    other = db.scalar(select(User).where(User.stripe_customer_id == obj["customer"]))
                    if other and other.id != user.id:
                        log.warning("Client Stripe %s déjà rattaché à un autre compte", obj["customer"])
                        user = None
                    else:
                        user.stripe_customer_id = obj["customer"]
                subscription_id = obj.get("subscription")
            elif event.get("type", "").startswith("customer.subscription."):
                user = db.scalar(select(User).where(User.stripe_customer_id == obj.get("customer")))
                subscription_id = obj.get("id")
            if user and subscription_id:
                # relu chez Stripe : l'ordre d'arrivée des événements ne compte pas
                sub = stripe.subscription(subscription_id)
                if sub.get("customer") == user.stripe_customer_id and apply_subscription(user, sub):
                    log.info("Abonnement de u%s : %s → formule %s", user.id, sub.get("status"), user.formule)
            db.add(StripeEvent(id=event["id"]))
            db.commit()
            return True

    @app.post("/api/comptes/stripe/webhook", dependencies=[Depends(require_billing)])
    async def stripe_webhook(request: Request):
        payload = await request.body()
        try:
            verify_signature(payload, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret)
            event = json.loads(payload)
            event_id = event["id"]
        except (BadSignature, ValueError, KeyError, TypeError):
            raise HTTPException(400, "Signature ou contenu invalide") from None
        try:
            await asyncio.to_thread(handle_event, event)
        except StripeError as exc:
            log.warning("Événement Stripe %s non traité : %s", event_id, exc)
            raise HTTPException(503, "Stripe injoignable : l'événement sera renvoyé") from None
        return {"recu": True}

    # --- Tableau de bord formateur (adresses ADMIN_EMAILS)

    def require_trainer(user):
        if user.email not in settings.admin_emails:
            raise HTTPException(403, "Le tableau de bord est réservé aux formateurs")

    def trainer_data(db, parcours_id):
        try:
            all_parcours = contenus.parcours()
        except Exception:  # noqa: BLE001
            raise HTTPException(503, "Les parcours sont momentanément indisponibles") from None
        parcours = next((p for p in all_parcours if p["id"] == parcours_id), all_parcours[0] if all_parcours else None)
        return all_parcours, parcours, formateur.students(db, parcours, settings.admin_emails, utcnow())

    @app.get("/compte/formateur", response_class=HTMLResponse)
    def trainer(request: Request, parcours: str = "", q: str = "", user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/formateur")
        require_trainer(user)
        all_parcours, current, students = trainer_data(db, parcours)
        try:
            labs = sum(1 for name in hub.running_servers() if HUB_NAME_RE.fullmatch(name))
        except Exception:  # noqa: BLE001 - Hub injoignable : le reste du tableau reste utile
            labs = None
        return page(request, "formateur.html", user=user, all_parcours=all_parcours, parcours=current, q=q,
                    resume=formateur.overview(students, labs, utcnow()),
                    modules=formateur.module_stats(students, current),
                    students=sorted((st for st in students if formateur.matches(st, q)),
                                    key=lambda st: st.derniere_activite or datetime.min, reverse=True),
                    total=len(students),
                    stuck_after=formateur.STUCK_AFTER)

    @app.get("/compte/formateur/etudiants/{student_id}", response_class=HTMLResponse)
    def trainer_student(request: Request, student_id: int, parcours: str = "", user=Depends(current_user),
                        db=Depends(get_db)):
        if not user:
            return login_redirect(f"/compte/formateur/etudiants/{student_id}")
        require_trainer(user)
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
        require_trainer(user)
        _, current, students = trainer_data(db, parcours)
        name = f"etudiants-{current['id'] if current else 'parcours'}-{utcnow():%Y-%m-%d}.csv"
        return Response(formateur.to_csv(students, current), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

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
            g = grading.module_grade(notes, bool(ex and ex.reussi_le), ex.indices if ex else 0)
            weighted.append((m["coef"], g))
            commence = bool(notes) or ex is not None
            etat = "termine" if g.termine else ("en_cours" if commence else "a_faire")
            rows.append({"module": m, "grade": g, "tentatives": len(notes), "etat": etat,
                         "indices": ex.indices if ex else 0, "reussi": bool(ex and ex.reussi_le)})
        termines = sum(1 for r in rows if r["etat"] == "termine")
        # prochain module : le premier en cours, sinon le premier à faire
        prochain = next((r["module"] for r in rows if r["etat"] == "en_cours"),
                        next((r["module"] for r in rows if r["etat"] == "a_faire"), None))
        return {"parcours": p, "modules": rows, "finale": grading.final_grade(weighted), "termines": termines,
                "commence": any(r["etat"] != "a_faire" for r in rows), "prochain": prochain,
                "pourcentage": round(100 * termines / len(rows)) if rows else 0}

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
        return {"connecte": True, "termines": r["termines"], "total": len(r["modules"]),
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
            "Content-Disposition": f'inline; filename="certificat-ros-academy-{cert.code}.pdf"'})

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
        require_trainer(user)
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

    @app.get("/api/comptes/moi")
    def moi(user=Depends(require_user), db=Depends(get_db)):
        return {"nom": user.nom, "email": user.email, "formule": user.formule, "hub": user.hub_name,
                "minutes_restantes": minutes_left(db, user, settings), "minutes_utilisees": minutes_used(db, user)}

    @app.get("/api/comptes/qcm/{module}")
    def qcm_state(module: str, user=Depends(require_user), db=Depends(get_db)):
        check_module(module)
        notes, _ = progress(db, user, module)
        return {"tentatives": len(notes), "restantes": max(0, grading.MAX_QCM_ATTEMPTS - len(notes)),
                "meilleure": max(notes) if notes else None}

    @app.post("/api/comptes/qcm/{module}")
    def qcm_submit(module: str, body: QcmBody, user=Depends(require_user), db=Depends(get_db),
                   _=Depends(same_origin)):
        check_module(module)
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

    def exercise_row(db, user, module):
        ex = db.get(Exercise, (user.id, module))
        if not ex:
            ex = Exercise(user_id=user.id, module=module, indices=0)
            db.add(ex)
            db.flush()
        return ex

    @app.get("/api/comptes/exercices/{module}")
    def exercise_state(module: str, user=Depends(require_user), db=Depends(get_db)):
        check_module(module)
        ex = db.get(Exercise, (user.id, module))
        return {"indices": ex.indices if ex else 0, "reussi": bool(ex and ex.reussi_le)}

    @app.post("/api/comptes/exercices/{module}/indices/{n}")
    def exercise_hint(module: str, n: int, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        check_module(module)
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
        check_module(module)
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
        if result.get("ok") is True and not ex.reussi_le:
            ex.reussi_le = utcnow()
        db.commit()
        return {"reussi": bool(ex.reussi_le), "verification": bool(result.get("ok") is True),
                "journal": str(result.get("journal", ""))[-4000:], "indices": ex.indices}

    @app.get("/api/comptes/exercices/{module}/explication")
    def exercise_explanation(module: str, user=Depends(require_user), db=Depends(get_db)):
        check_module(module)
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
        return {"autorise": minutes_left(db, user, settings) != 0}

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

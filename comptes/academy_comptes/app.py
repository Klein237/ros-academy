"""Service Comptes : connexion, accès au lab, quotas, progression, notes."""

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
import jwt
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from . import grading
from .auth import (
    OAUTH_COOKIE,
    SESSION_COOKIE,
    SESSION_DAYS,
    AuthError,
    Sessions,
    authorize_url,
    consume_login_link,
    oauth_identity,
    request_login_link,
    safe_next,
    user_for_email,
)
from .clients import ContenusClient, HubClient, UpstreamError
from .db import Base, Exercise, QcmAttempt, QueueTicket, make_engine, make_sessionmaker, utcnow
from .mail import send_login_link
from .quotas import join_queue, leave_queue, minutes_left, minutes_used, queue_position, record_minute
from .settings import Settings

log = logging.getLogger("comptes")
HERE = Path(__file__).parent
MODULE_ID_RE = re.compile(r"^[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
LAB_TOKEN_TTL = 300
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'; object-src 'none'")


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


def create_app(settings: Settings, hub=None, contenus=None, http=None, background=True):
    engine = make_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)  # Postgres : migrations Alembic
    SessionLocal = make_sessionmaker(engine)
    sessions = Sessions(settings.jwt_secret)
    hub = hub or HubClient(settings.hub_url, settings.hub_admin_token)
    contenus = contenus or ContenusClient(settings.contenus_url, settings.jwt_secret)
    http = http or httpx.Client(timeout=15)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    state = {"actifs": 0, "releve": 0.0}

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
        response.headers.setdefault("Content-Security-Policy", CSP)
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

    @app.get("/connexion", response_class=HTMLResponse)
    def connexion(request: Request, suite: str = "/", user=Depends(current_user)):
        if user:
            return RedirectResponse(safe_next(suite), status_code=303)
        return page(request, "connexion.html", suite=safe_next(suite), github=settings.github_enabled,
                    google=settings.google_enabled)

    @app.post("/connexion/email", response_class=HTMLResponse)
    def connexion_email(request: Request, email: str = Form(...), suite: str = Form("/"), db=Depends(get_db),
                        _=Depends(same_origin)):
        try:
            email, link = request_login_link(db, email, suite, settings.public_url)
        except AuthError as exc:
            return page(request, "connexion.html", 400, suite=safe_next(suite), erreur=str(exc),
                        github=settings.github_enabled, google=settings.google_enabled)
        try:
            send_login_link(settings, email, link)
        except Exception:  # noqa: BLE001 - serveur SMTP
            log.exception("Envoi du lien de connexion impossible")
            return page(request, "message.html", 502, titre="Envoi impossible",
                        message="Le lien de connexion n'a pas pu être envoyé. Réessayez dans un instant.")
        return page(request, "message.html", titre="Vérifiez votre boîte de réception",
                    message=f"Un lien de connexion a été envoyé à {email}. Il est valable 15 minutes.")

    @app.get("/connexion/email/{raw}")
    def connexion_email_retour(request: Request, raw: str, db=Depends(get_db)):
        try:
            email, suite = consume_login_link(db, raw)
        except AuthError as exc:
            return page(request, "message.html", 400, titre="Lien expiré", message=str(exc),
                        lien="/connexion", lien_texte="Demander un nouveau lien")
        return open_session(db, user_for_email(db, email), suite)

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

    @app.get("/compte/lab")
    def compte_lab(request: Request, suite: str = "/lab/", user=Depends(current_user), db=Depends(get_db)):
        suite = safe_lab_next(suite)
        if not user:
            return login_redirect(f"/compte/lab?suite={quote(suite, safe='')}")
        if minutes_left(db, user, settings) == 0:
            return page(request, "message.html", 403, titre="Quota de lab épuisé",
                        message="Vous avez utilisé toutes vos minutes de lab ce mois-ci. Les cours, les QCM et vos "
                                "notes restent accessibles ; le lab sera de nouveau disponible le mois prochain.",
                        lien="/compte/resultats", lien_texte="Voir mes résultats")
        token = mint_lab_token(settings.jwt_secret, user)
        return RedirectResponse(f"/hub/jwt_login?token={token}&next={quote(suite, safe='')}", status_code=303)

    @app.get("/compte/admin")
    def compte_admin(user=Depends(current_user)):
        if not user:
            return login_redirect("/compte/admin")
        if user.email not in settings.admin_emails:
            raise HTTPException(403, "Ce compte n'a pas accès à l'administration")
        return RedirectResponse(f"/admin/login?token={mint_admin_token(settings.jwt_secret, user)}", status_code=303)

    # --- Résultats

    def progress(db, user, module):
        notes = [a.note for a in db.scalars(select(QcmAttempt).where(QcmAttempt.user_id == user.id,
                                                                     QcmAttempt.module == module))]
        ex = db.get(Exercise, (user.id, module))
        return notes, ex

    @app.get("/compte/resultats", response_class=HTMLResponse)
    def resultats(request: Request, user=Depends(current_user), db=Depends(get_db)):
        if not user:
            return login_redirect("/compte/resultats")
        try:
            parcours = contenus.parcours()
        except Exception:  # noqa: BLE001
            raise HTTPException(503, "Les parcours sont momentanément indisponibles") from None
        out = []
        for p in parcours:
            rows, weighted = [], []
            for m in p["modules"]:
                notes, ex = progress(db, user, m["id"])
                g = grading.module_grade(notes, bool(ex and ex.reussi_le), ex.indices if ex else 0)
                weighted.append((m["coef"], g))
                rows.append({"module": m, "grade": g, "tentatives": len(notes),
                             "indices": ex.indices if ex else 0, "reussi": bool(ex and ex.reussi_le)})
            out.append({"parcours": p, "modules": rows, "finale": grading.final_grade(weighted),
                        "termines": sum(1 for _, g in weighted if g.termine)})
        return page(request, "resultats.html", user=user, resultats=out)

    # --- API (Lab UI et pages du site)

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

    @app.get("/api/comptes/exercices/{module}/indices/{n}")
    def exercise_hint(module: str, n: int, user=Depends(require_user), db=Depends(get_db)):
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

    @app.post("/api/comptes/exercices/{module}/reussite")
    def exercise_success(module: str, user=Depends(require_user), db=Depends(get_db), _=Depends(same_origin)):
        check_module(module)
        ex = exercise_row(db, user, module)
        if not ex.reussi_le:
            ex.reussi_le = utcnow()
        db.commit()
        return {"reussi": True, "indices": ex.indices}

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
    return create_app(Settings.from_env())

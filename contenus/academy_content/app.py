"""Service Contenus : site étudiant, API publique des modules, espace d'administration."""

import hashlib
import hmac
import logging
import os
import time
from pathlib import Path

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError

from .auth import COOKIE_NAME, SESSION_MAX_AGE, AuthError, Sessions, same_origin, verify_admin_token
from .model import (
    MAX_FILE_BYTES,
    MODULE_ID_RE,
    ContentError,
    ParcoursDef,
    Qcm,
    list_module_ids,
    list_parcours_ids,
    load_module,
    load_parcours,
    module_files,
)
from .render import code_files, lab_link, render_cours, render_markdown
from .store import ContentStore, StoreError
from .verification import Busy, InvalidStudent

log = logging.getLogger("contenus")
HERE = Path(__file__).parent
TEMPLATE_MODULE = HERE / "modele"

INTERNAL_HEADER = "X-Academy-Interne"

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'; object-src 'none'")


# --- Contenu (lecture) ---------------------------------------------------------------

def _module_or_404(root, module_id):
    try:
        return load_module(root, module_id)
    except ContentError:
        raise HTTPException(404, "Module introuvable") from None


def _parcours_list(root):
    out = []
    for pid in list_parcours_ids(root):
        try:
            p = load_parcours(root, pid)
        except ContentError:
            continue
        mods = []
        for ref in p.modules:
            try:
                m = load_module(root, ref.id)
                mods.append({"id": m.id, "titre": m.en_tete.titre, "resume": m.en_tete.resume,
                             "duree": m.en_tete.duree, "coef": ref.coef})
            except ContentError:
                continue
        out.append({"id": p.id, "titre": p.titre, "description": p.description, "modules": mods})
    return out


def _parcours_of(root, module_id):
    for p in _parcours_list(root):
        ids = [m["id"] for m in p["modules"]]
        if module_id in ids:
            i = ids.index(module_id)
            return p, (p["modules"][i - 1] if i > 0 else None), (p["modules"][i + 1] if i + 1 < len(ids) else None), i + 1
    return None, None, None, None


def _public_qcm(module):
    return [
        {"id": q.id, "question": q.question, "multiple": len(q.bonnes) > 1,
         "choix": [c.texte for c in q.choix]}
        for q in module.qcm.questions
    ]


def correct_qcm(module, reponses):
    """Note sur 20. Les bonnes réponses ne sont jamais renvoyées ; l'explication seulement si juste."""
    details, justes = [], 0
    for q in module.qcm.questions:
        choisis = reponses.get(q.id) or []
        try:
            choisis = {int(c) for c in choisis}
        except (TypeError, ValueError):
            choisis = set()
        juste = choisis == q.bonnes
        justes += juste
        details.append({"id": q.id, "juste": juste, "explication": q.explication if juste else ""})
    total = len(module.qcm.questions)
    return {"note": round(20 * justes / total, 1), "sur": 20, "justes": justes, "total": total,
            "questions": details}


def _text_files(base, prefix=""):
    files = []
    if not base.is_dir():
        return files
    for rel in module_files(base):
        p = base / rel
        if p.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append({"path": prefix + rel, "content": content, "executable": rel.endswith(".sh")})
    return files


# --- Application ----------------------------------------------------------------------

class QcmAnswers(BaseModel):
    reponses: dict[str, list[int]] = {}


class FileBody(BaseModel):
    content: str


class NewModule(BaseModel):
    id: str
    titre: str


class PreviewBody(BaseModel):
    module: str
    markdown: str


class VerifyBody(BaseModel):
    etudiant: str


class RestoreBody(BaseModel):
    sha: str


def create_app(store: ContentStore, runner, secret: str, cookie_secure=True, tests_enabled=True, verifier=None):
    app = FastAPI(title="Contenus ROS Academy", docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.globals["lab_link"] = lab_link
    internal_token = hmac.new(secret.encode(), b"contenus-interne", hashlib.sha256).hexdigest()

    def internal(request: Request):
        """Routes appelées par le service Comptes seulement (Caddy les bloque aussi depuis l'extérieur)."""
        if not hmac.compare_digest(request.headers.get(INTERNAL_HEADER, ""), internal_token):
            raise HTTPException(403, "Route interne")

    sessions = Sessions(secret)
    app.mount("/static/contenus", StaticFiles(directory=str(HERE / "static")), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith(("/admin", "/api/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    def page(request, name, status=200, **ctx):
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if request.url.path.startswith(("/api/", "/admin/api/")):
            return JSONResponse({"erreur": exc.detail}, status_code=exc.status_code)
        if exc.status_code == 401:
            # Comptes vérifie que l'adresse est administratrice et renvoie vers /admin/login
            return RedirectResponse("/compte/admin", status_code=303)
        return page(request, "erreur.html", exc.status_code, titre="Page introuvable" if exc.status_code == 404 else "Erreur",
                    message=exc.detail)

    published = lambda: store.published_dir  # noqa: E731
    draft = lambda: store.draft_dir  # noqa: E731

    # --- Site étudiant

    def module_page(request, root, module_id, apercu=False):
        module = _module_or_404(root, module_id)
        parcours, prev, nxt, numero = _parcours_of(root, module_id)
        return page(
            request, "module.html",
            module=module, cours_html=render_cours(module.cours, module.id),
            enonce_html=render_markdown(module.exercice.enonce), qcm=_public_qcm(module),
            parcours=parcours, prev=prev, next=nxt, numero=numero, apercu=apercu,
        )

    @app.get("/", response_class=HTMLResponse)
    def accueil(request: Request):
        return page(request, "accueil.html", parcours=_parcours_list(published()))

    @app.get("/parcours/{parcours_id}/", response_class=HTMLResponse)
    def parcours_page(request: Request, parcours_id: str):
        for p in _parcours_list(published()):
            if p["id"] == parcours_id:
                return page(request, "parcours.html", parcours=p,
                            total_coef=sum(m["coef"] for m in p["modules"]))
        raise HTTPException(404, "Parcours introuvable")

    @app.get("/modules/{module_id}/", response_class=HTMLResponse)
    def module_public(request: Request, module_id: str):
        return module_page(request, published(), module_id)

    # --- API publique (utilisée par la page du module et par le Lab UI)

    @app.get("/api/contenus/modules/{module_id}")
    def api_module(module_id: str):
        m = _module_or_404(published(), module_id)
        return {"id": m.id, "titre": m.en_tete.titre, "resume": m.en_tete.resume, "duree": m.en_tete.duree}

    @app.get("/api/contenus/modules/{module_id}/lab")
    def api_lab(module_id: str):
        _module_or_404(published(), module_id)
        return {"files": _text_files(published() / "modules" / module_id / "lab")}

    @app.get("/api/contenus/modules/{module_id}/cours-fichiers")
    def api_course_files(module_id: str):
        m = _module_or_404(published(), module_id)
        return {"files": [{"path": p, "content": c} for p, c in code_files(m.cours).items()]}

    @app.get("/api/contenus/modules/{module_id}/exercice")
    def api_exercise(module_id: str):
        m = _module_or_404(published(), module_id)
        base = published() / "modules" / module_id / "exercice"
        hidden = ("solution/", "explication.md", "indices.md")
        files = [f for f in _text_files(base) if not f["path"].startswith(hidden)]
        return {"enonce_html": render_markdown(m.exercice.enonce), "files": files, "indices": len(m.exercice.indices)}

    @app.get("/api/contenus/parcours")
    def api_parcours():
        return {"parcours": _parcours_list(published())}

    # Routes internes : indices, explication et correction du QCM passent par Comptes,
    # qui applique les règles (indices comptés, explication après réussite, 2 tentatives).

    @app.get("/api/contenus/modules/{module_id}/indices/{n}", dependencies=[Depends(internal)])
    def api_hint(module_id: str, n: int):
        m = _module_or_404(published(), module_id)
        if not 1 <= n <= len(m.exercice.indices):
            raise HTTPException(404, "Indice introuvable")
        return {"n": n, "html": render_markdown(m.exercice.indices[n - 1])}

    @app.get("/api/contenus/modules/{module_id}/explication", dependencies=[Depends(internal)])
    def api_explanation(module_id: str):
        m = _module_or_404(published(), module_id)
        return {"html": render_markdown(m.exercice.explication)}

    @app.post("/api/contenus/modules/{module_id}/verifier", dependencies=[Depends(internal)])
    def api_verify(module_id: str, body: VerifyBody):
        """check.sh officiel sur le workspace de l'étudiant, hors de son conteneur (appelé par Comptes)."""
        _module_or_404(published(), module_id)
        if verifier is None:
            raise HTTPException(503, "Vérification indisponible")
        try:
            return verifier(published() / "modules" / module_id, module_id, body.etudiant).as_dict()
        except InvalidStudent:
            raise HTTPException(400, "Étudiant invalide") from None
        except Busy:
            raise HTTPException(429, "Le serveur de vérification est occupé : réessayez dans un instant") from None

    @app.get("/api/contenus/modules/{module_id}/qcm")
    def api_qcm(module_id: str):
        return {"questions": _public_qcm(_module_or_404(published(), module_id))}

    @app.post("/api/contenus/modules/{module_id}/qcm", dependencies=[Depends(internal)])
    def api_qcm_correct(module_id: str, body: QcmAnswers):
        return correct_qcm(_module_or_404(published(), module_id), body.reponses)

    # --- Administration : connexion

    def admin_user(request: Request):
        admin = sessions.read(request.cookies.get(COOKIE_NAME))
        if not admin:
            raise HTTPException(401, "Connexion requise")
        return admin

    def admin_write(request: Request, admin=Depends(admin_user)):
        # Le cookie est SameSite=Strict ; on vérifie en plus l'origine de toute écriture.
        if not same_origin(request.headers.get("origin"), request.headers.get("host")):
            raise HTTPException(403, "Requête refusée (origine inconnue)")
        return admin

    @app.get("/admin/api/verifier")
    def admin_verify(request: Request):
        """Pour Caddy (forward_auth) : la requête vient-elle de l'administrateur ? (journaux, Grafana)"""
        admin = sessions.read(request.cookies.get(COOKIE_NAME))
        if not admin:
            return RedirectResponse("/compte/admin", status_code=302)
        return Response(status_code=204, headers={"X-Academy-Admin": admin})

    @app.get("/admin/login")
    def admin_login(request: Request, token: str = ""):
        try:
            admin = verify_admin_token(token, secret)
        except AuthError as exc:
            log.warning("Connexion admin refusée : %s", exc)
            return page(request, "erreur.html", 403, titre="Lien de connexion invalide",
                        message="Ce lien a expiré ou ne donne pas accès à l'administration.")
        response = RedirectResponse("/admin/", status_code=303)
        response.set_cookie(COOKIE_NAME, sessions.issue(admin), max_age=SESSION_MAX_AGE, path="/admin",
                            httponly=True, secure=cookie_secure, samesite="strict")
        return response

    @app.get("/admin/logout")
    def admin_logout():
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/admin")
        return response

    # --- Administration : pages

    @app.get("/admin/", response_class=HTMLResponse)
    def admin_home(request: Request, admin=Depends(admin_user)):
        return page(request, "admin/tableau.html", admin=admin, tests_enabled=tests_enabled)

    @app.get("/admin/guide/", response_class=HTMLResponse)
    def admin_guide(request: Request, admin=Depends(admin_user)):
        guide = render_markdown((HERE / "guide.md").read_text(encoding="utf-8"))
        return page(request, "admin/guide.html", admin=admin, guide_html=guide)

    @app.get("/admin/modules/{module_id}/", response_class=HTMLResponse)
    def admin_module(request: Request, module_id: str, admin=Depends(admin_user)):
        if module_id not in store.module_ids():
            raise HTTPException(404, "Module introuvable")
        return page(request, "admin/editeur.html", admin=admin, module_id=module_id)

    @app.get("/admin/parcours/{parcours_id}/", response_class=HTMLResponse)
    def admin_parcours(request: Request, parcours_id: str, admin=Depends(admin_user)):
        if parcours_id not in store.parcours_ids():
            raise HTTPException(404, "Parcours introuvable")
        return page(request, "admin/parcours.html", admin=admin, parcours_id=parcours_id)

    @app.get("/admin/apercu/modules/{module_id}/", response_class=HTMLResponse)
    def admin_preview_page(request: Request, module_id: str, admin=Depends(admin_user)):
        return module_page(request, draft(), module_id, apercu=True)

    # --- Administration : API JSON

    def store_call(fn, *args):
        try:
            return fn(*args)
        except StoreError as exc:
            raise HTTPException(400, str(exc)) from None

    def module_errors(module_id):
        try:
            load_module(draft(), module_id)
            return []
        except ContentError as exc:
            return [str(e) for e in exc.erreurs]

    @app.get("/admin/api/etat")
    def api_state(admin=Depends(admin_user)):
        changed = set(store.changed_modules())
        modules = []
        for mid in store.module_ids():
            try:
                titre = load_module(draft(), mid).en_tete.titre
            except ContentError:
                titre = mid
            modules.append({"id": mid, "titre": titre, "modifie": mid in changed, "erreurs": module_errors(mid)})
        parcours = []
        for pid in store.parcours_ids():
            try:
                data = store.read_parcours(pid)
            except StoreError:
                continue
            parcours.append({"id": pid, "titre": data.get("titre", pid),
                             "modules": [m.get("id") for m in data.get("modules", [])]})
        return {"modules": modules, "parcours": parcours, "a_publier": store.has_unpublished_changes(),
                "publication": _publication_json(store.publication), "tests": tests_enabled}

    @app.post("/admin/api/modules")
    def api_create_module(body: NewModule, admin=Depends(admin_write)):
        if not MODULE_ID_RE.fullmatch(body.id):
            raise HTTPException(400, "Identifiant invalide : deux chiffres, un tiret, des minuscules (ex. 06-parametres)")
        store_call(store.create_module, body.id, body.titre, TEMPLATE_MODULE)
        return {"id": body.id}

    @app.delete("/admin/api/modules/{module_id}")
    def api_delete_module(module_id: str, admin=Depends(admin_write)):
        store_call(store.delete_module, module_id)
        return {"ok": True}

    @app.get("/admin/api/modules/{module_id}/fichiers")
    def api_files(module_id: str, admin=Depends(admin_user)):
        return {"fichiers": store_call(store.list_files, module_id), "erreurs": module_errors(module_id)}

    @app.get("/admin/api/modules/{module_id}/fichier")
    def api_read(module_id: str, chemin: str, admin=Depends(admin_user)):
        return {"chemin": chemin, "contenu": store_call(store.read_file, module_id, chemin)}

    @app.put("/admin/api/modules/{module_id}/fichier")
    def api_write(module_id: str, chemin: str, body: FileBody, admin=Depends(admin_write)):
        sha = store_call(store.write_file, module_id, chemin, body.content)
        return {"commit": sha, "erreurs": module_errors(module_id)}

    @app.delete("/admin/api/modules/{module_id}/fichier")
    def api_delete(module_id: str, chemin: str, admin=Depends(admin_write)):
        store_call(store.delete_file, module_id, chemin)
        return {"erreurs": module_errors(module_id)}

    @app.get("/admin/api/modules/{module_id}/qcm")
    def api_qcm_read(module_id: str, admin=Depends(admin_user)):
        text = store_call(store.read_file, module_id, "qcm.yaml")
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            raise HTTPException(400, "qcm.yaml n'est pas un YAML valide : corrigez-le dans l'éditeur de fichiers") from None
        return data if isinstance(data, dict) else {"questions": []}

    @app.put("/admin/api/modules/{module_id}/qcm")
    def api_qcm_write(module_id: str, body: dict, admin=Depends(admin_write)):
        try:
            qcm = Qcm.model_validate(body)
        except ValidationError as exc:
            msgs = [f"{'.'.join(str(p) for p in e['loc'])} : {e['msg'].removeprefix('Value error, ')}" for e in exc.errors()]
            raise HTTPException(400, " ; ".join(msgs)) from None
        text = yaml.safe_dump(qcm.model_dump(exclude_defaults=False), allow_unicode=True, sort_keys=False, width=100)
        sha = store_call(store.write_file, module_id, "qcm.yaml", text)
        return {"commit": sha, "erreurs": module_errors(module_id)}

    @app.post("/admin/api/apercu")
    def api_preview(body: PreviewBody, admin=Depends(admin_write)):
        if not MODULE_ID_RE.fullmatch(body.module):
            raise HTTPException(400, "identifiant de module invalide")
        return {"html": render_cours(body.markdown, body.module)}

    @app.get("/admin/api/parcours/{parcours_id}")
    def api_parcours_read(parcours_id: str, admin=Depends(admin_user)):
        return store_call(store.read_parcours, parcours_id)

    @app.put("/admin/api/parcours/{parcours_id}")
    def api_parcours_write(parcours_id: str, body: dict, admin=Depends(admin_write)):
        try:
            d = ParcoursDef.model_validate(body)
        except ValidationError as exc:
            msgs = [f"{'.'.join(str(p) for p in e['loc'])} : {e['msg'].removeprefix('Value error, ')}" for e in exc.errors()]
            raise HTTPException(400, " ; ".join(msgs)) from None
        unknown = [m.id for m in d.modules if m.id not in store.module_ids()]
        if unknown:
            raise HTTPException(400, f"module inconnu : {', '.join(unknown)}")
        sha = store_call(store.write_parcours, parcours_id, d.model_dump())
        return {"commit": sha}

    @app.post("/admin/api/publication")
    def api_publish(admin=Depends(admin_write)):
        store_call(store.publish_in_background, runner)
        return _publication_json(store.publication)

    @app.get("/admin/api/publication")
    def api_publication(admin=Depends(admin_user)):
        return _publication_json(store.publication)

    @app.get("/admin/api/historique")
    def api_history(admin=Depends(admin_user)):
        published_sha = store.head("publie")
        return {"commits": [{"sha": c.sha, "date": c.date, "message": c.message, "publie": c.sha == published_sha}
                            for c in store.history()]}

    @app.post("/admin/api/historique/restaurer")
    def api_restore(body: RestoreBody, admin=Depends(admin_write)):
        return {"commit": store_call(store.restore, body.sha)}

    return app


def _publication_json(pub):
    return {
        "etat": pub.etat, "commit": pub.commit, "module_en_cours": pub.module_en_cours,
        "duree": round((pub.fin or time.time()) - pub.debut) if pub.debut else 0,
        "erreurs": pub.erreurs,
        "rapports": [{"module": r.module, "ok": r.ok, "resume": r.resume(), "journal": r.journal[-20000:]}
                     for r in pub.rapports],
    }


def app_from_env():
    """Point d'entrée de production (uvicorn academy_content.app:app_from_env --factory)."""
    logging.basicConfig(level=logging.INFO)
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32 or secret.startswith("remplacer"):
        raise SystemExit("JWT_SECRET doit faire au moins 32 caractères")
    store = ContentStore(
        os.environ.get("CONTENT_ROOT", "/srv/contenus"),
        seed=os.environ.get("CONTENT_SEED", "/srv/seed"),
        remote=os.environ.get("CONTENT_GIT_REMOTE") or None,
    )
    image = os.environ.get("ROS_LAB_IMAGE", "ros-lab:0.1.0")
    tests_enabled = os.environ.get("MODULE_TESTS", "docker") != "off"
    if tests_enabled:
        from .testing import run_module_tests

        def runner(module_dir):
            return run_module_tests(module_dir, image=image)
    else:
        log.warning("MODULE_TESTS=off : les modules sont publiés SANS être testés (développement uniquement)")
        from .testing import Rapport

        def runner(module_dir):
            return Rapport(module=module_dir.name, ok=True, journal="tests désactivés (MODULE_TESTS=off)")
    from .verification import make_slots, verify_exercise

    slots = make_slots(int(os.environ.get("VERIFICATIONS_MAX", "4")))

    def verifier(module_dir, module_id, student):
        return verify_exercise(module_dir, module_id, student, image=image, slots=slots)

    return create_app(store, runner, secret, cookie_secure=os.environ.get("COOKIE_SECURE", "1") != "0",
                      tests_enabled=tests_enabled, verifier=verifier)

"""Formules d'abonnement et limites de ressources des conteneurs ros-lab."""

import hashlib
import hmac
import json
import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanLimits:
    cpu: float
    mem: str
    pids: int


PLANS = {
    "free": PlanLimits(cpu=1.0, mem="2G", pids=256),
    "pro": PlanLimits(cpu=2.0, mem="4G", pids=512),
}
DEFAULT_PLAN = "free"


def limits_for(plan):
    """Retourne les limites de la formule ; toute valeur inconnue donne `free`."""
    if isinstance(plan, str) and plan in PLANS:
        return PLANS[plan]
    log.warning("Formule inconnue %r, application de %s", plan, DEFAULT_PLAN)
    return PLANS[DEFAULT_PLAN]


def apply_limits(spawner, auth_state):
    """auth_state_hook de JupyterHub : fixe les limites avant le démarrage."""
    plan = (auth_state or {}).get("plan", DEFAULT_PLAN)
    limits = limits_for(plan)
    spawner.cpu_limit = limits.cpu
    spawner.mem_limit = limits.mem
    spawner.extra_host_config = {**spawner.extra_host_config, "pids_limit": limits.pids}


# --- Quota de minutes : le service Comptes décide avant chaque démarrage

INTERNAL_HEADER = "X-Academy-Interne"
STUDENT_RE = re.compile(r"^u\d+$")


def comptes_token(secret):
    """Secret dérivé partagé avec Comptes pour sa route interne (jamais le secret lui-même)."""
    return hmac.new(secret.encode(), b"comptes-interne", hashlib.sha256).hexdigest()


async def _tornado_fetch(url, headers):
    from tornado.httpclient import AsyncHTTPClient

    r = await AsyncHTTPClient().fetch(url, headers=headers, request_timeout=5, raise_error=False)
    return r.code, r.body


def make_quota_hook(comptes_url, secret, fetch=_tornado_fetch):
    """pre_spawn_hook : refuse le démarrage d'un étudiant dont le quota du mois est épuisé.

    Sans ce contrôle, un étudiant garderait la main sur son serveur par l'API du Hub
    (son cookie reste valable) et pourrait le relancer après l'arrêt pour quota.
    Comptes injoignable : le démarrage est accepté (le relevé de Comptes arrête de
    toute façon un serveur hors quota à la minute suivante).
    """
    base = comptes_url.rstrip("/")
    headers = {INTERNAL_HEADER: comptes_token(secret)}

    async def hook(spawner):
        from tornado import web

        name = spawner.user.name
        if not STUDENT_RE.fullmatch(name):
            return  # comptes de test ou d'administration : pas de quota
        try:
            code, body = await fetch(f"{base}/api/comptes/interne/lab/{name}", headers)
        except Exception as exc:  # noqa: BLE001
            log.warning("Quota de %s non vérifié (Comptes injoignable) : %s", name, exc)
            return
        if code == 200 and json.loads(body).get("autorise") is False:
            raise web.HTTPError(403, "Quota de lab épuisé pour ce mois-ci")
        if code != 200:
            log.warning("Quota de %s non vérifié (Comptes a répondu %s)", name, code)

    return hook

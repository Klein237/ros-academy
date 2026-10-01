"""Formules d'abonnement et limites de ressources des conteneurs ros-lab."""

import logging
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

"""Minutes de lab, arrêt à quota épuisé, file d'attente quand le Hub est plein."""

import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .db import QueueTicket, UsageTick, User, utcnow

HUB_NAME_RE = re.compile(r"^u(\d+)$")
QUEUE_TTL = timedelta(seconds=45)


def month_start(now):
    return datetime(now.year, now.month, 1)


def minutes_used(db, user, now=None):
    now = now or utcnow()
    return db.scalar(select(func.count()).select_from(UsageTick)
                     .where(UsageTick.user_id == user.id, UsageTick.minute >= month_start(now))) or 0


def minutes_left(db, user, settings, now=None):
    """Minutes restantes ce mois-ci ; None si la formule est sans limite."""
    quota = settings.plan_minutes.get(user.formule, settings.plan_minutes["free"])
    if quota is None:
        return None
    return max(0, quota - minutes_used(db, user, now))


def record_minute(db, hub, settings, now=None):
    """Relevé d'une minute : +1 minute par serveur prêt, arrêt des serveurs dont le quota est épuisé.

    Idempotent : relancé deux fois dans la même minute, il ne compte rien de plus.
    Renvoie (nombre de serveurs actifs, noms arrêtés).
    """
    now = now or utcnow()
    minute = now.replace(second=0, microsecond=0)
    servers = hub.running_servers()
    stopped = []
    for name, ready in servers.items():
        m = HUB_NAME_RE.fullmatch(name)
        if not m or not ready:
            continue
        user = db.get(User, int(m.group(1)))
        if not user:
            continue
        try:
            db.add(UsageTick(user_id=user.id, minute=minute))
            db.commit()
        except IntegrityError:
            db.rollback()  # minute déjà comptée
        left = minutes_left(db, user, settings, now)
        if left is not None and left <= 0:
            hub.stop(name)
            stopped.append(name)
    return len(servers), stopped


# --- File d'attente

def _purge(db, now):
    db.execute(delete(QueueTicket).where(QueueTicket.vu_le < now - QUEUE_TTL))


def join_queue(db, user, now=None):
    now = now or utcnow()
    _purge(db, now)
    ticket = db.scalar(select(QueueTicket).where(QueueTicket.user_id == user.id))
    if ticket:
        ticket.vu_le = now
    else:
        ticket = QueueTicket(ticket=secrets.token_urlsafe(24), user_id=user.id, cree_le=now, vu_le=now)
        db.add(ticket)
    db.commit()
    return ticket


def queue_position(db, ticket, now=None):
    """Position (1 = premier) parmi les tickets encore vivants ; met à jour le battement."""
    now = now or utcnow()
    _purge(db, now)
    row = db.get(QueueTicket, ticket)
    if not row:
        return None
    row.vu_le = now
    db.commit()
    ahead = db.scalar(select(func.count()).select_from(QueueTicket).where(QueueTicket.cree_le < row.cree_le)) or 0
    return ahead + 1


def leave_queue(db, ticket):
    db.execute(delete(QueueTicket).where(QueueTicket.ticket == ticket))
    db.commit()

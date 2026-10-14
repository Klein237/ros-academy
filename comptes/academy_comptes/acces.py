"""Accès aux parcours : achat (12 mois), accès offert par l'administrateur, parcours offerts.

Tant que l'accès payant n'est pas activé (ACCES_PAYANT=0, la bêta), tout compte connecté a accès
à tout, avec le quota de minutes de la formule gratuite. Une fois activé :
- un parcours s'ouvre par un achat ou un accès offert (« * » : tous les parcours) encore valable ;
- un parcours marqué « offert » (Docker pour la robotique) s'ouvre avec un certificat valide ;
- le lab est ouvert, sans limite de minutes, à qui a accès à au moins un parcours.
"""

import calendar
from datetime import datetime

from sqlalchemy import select

from .db import Access, Certificate

TOUS = "*"


def add_months(d: datetime, months: int) -> datetime:
    """Même jour, `months` mois plus tard (dernier jour du mois s'il n'existe pas : 31/01 → 28/02)."""
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))


def active_rows(db, user, now):
    rows = db.scalars(select(Access).where(Access.user_id == user.id, Access.retire_le.is_(None))
                      .order_by(Access.debut))
    return [a for a in rows if a.debut <= now and (a.fin is None or a.fin > now)]


def has_certificate(db, user):
    return db.scalar(select(Certificate.code).where(Certificate.user_id == user.id,
                                                    Certificate.revoque_le.is_(None)).limit(1)) is not None


def accessible(db, user, settings, now, offerts=()):
    """Parcours ouverts au compte : TOUS, ou l'ensemble de leurs identifiants (vide : aucun)."""
    if not settings.acces_payant:
        return TOUS
    ids = {a.parcours_id for a in active_rows(db, user, now)}
    if TOUS in ids:
        return TOUS
    if offerts and has_certificate(db, user):
        ids |= set(offerts)
    return ids


def header_value(parcours):
    """En-tête X-Academy-Acces lu par Contenus : « * » ou la liste des parcours ouverts."""
    return TOUS if parcours == TOUS else ",".join(sorted(parcours))


def can_open(parcours, parcours_ids):
    """Un module ouvert si l'un des parcours qui le contiennent est accessible."""
    return parcours == TOUS or any(p in parcours for p in parcours_ids)


def plan(db, user, settings, now):
    """Formule du lab : celle du compte pendant la bêta (« free » : quota de minutes) ; ensuite « pro »
    avec un accès valable ou un certificat (qui ouvre les parcours offerts), sinon « aucune » (pas de lab)."""
    if not settings.acces_payant:
        return user.formule if user.formule in settings.plan_minutes else "free"
    return "pro" if active_rows(db, user, now) or has_certificate(db, user) else "aucune"


def purchase_end(db, user, parcours_id, now, months):
    """Fin d'un nouvel achat : 12 mois, prolongés depuis la fin d'un achat encore valable du même parcours."""
    start = now
    for a in active_rows(db, user, now):
        if a.parcours_id == parcours_id and a.origine == "achat" and a.fin and a.fin > start:
            start = a.fin
    return add_months(start, months)

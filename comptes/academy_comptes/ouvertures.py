"""Ouvertures des modules : le cours (page du module) et le lab (ouvert depuis le module).

Une ligne par (étudiant, module, quoi) : première et dernière ouverture, et leur nombre. Assez pour voir
où un étudiant décroche, même quand il n'a ni tenté le QCM ni vérifié l'exercice.
"""

from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from .db import ModuleOpening, utcnow

COURS, LAB = "cours", "lab"


def record(db, user, module, quoi, now=None):
    now = now or utcnow()
    row = db.get(ModuleOpening, (user.id, module, quoi))
    if row:
        row.derniere, row.nombre = now, row.nombre + 1
    else:
        db.add(ModuleOpening(user_id=user.id, module=module, quoi=quoi, premiere=now, derniere=now, nombre=1))
    db.commit()


def module_of_lab_link(suite):
    """« /lab/?module=05-noeud&exercice=1 » → « 05-noeud » ; None si le lien ne vient pas d'un module."""
    values = parse_qs(urlsplit(suite or "").query).get("module")
    return values[0] if values else None


def by_user(db, ids):
    """{user_id: {module: {"cours": ModuleOpening, "lab": ModuleOpening}}}"""
    out = {}
    if ids:
        for o in db.scalars(select(ModuleOpening).where(ModuleOpening.user_id.in_(ids))):
            out.setdefault(o.user_id, {}).setdefault(o.module, {})[o.quoi] = o
    return out

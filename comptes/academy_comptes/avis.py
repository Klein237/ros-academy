"""Avis des étudiants sur les modules : demandés à la fin de chaque module, lus par les formateurs."""

import csv
import io
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select

from .db import ModuleFeedback, User, utcnow

NOTES = range(1, 6)
DIFFICULTES = {"trop_facile": "trop facile", "adaptee": "adaptée", "trop_difficile": "trop difficile"}
COMMENTAIRE_MAX = 2000


class InvalidFeedback(ValueError):
    pass


def save(db, user, module, note, difficulte, commentaire):
    """Enregistre (ou remplace) l'avis du compte sur le module."""
    if note not in NOTES:
        raise InvalidFeedback("La note va de 1 à 5.")
    if difficulte not in DIFFICULTES:
        raise InvalidFeedback("Difficulté inconnue.")
    commentaire = (commentaire or "").strip()
    if len(commentaire) > COMMENTAIRE_MAX:
        raise InvalidFeedback(f"Commentaire trop long ({COMMENTAIRE_MAX} caractères au plus).")
    row = db.get(ModuleFeedback, (user.id, module))
    if row is None:
        row = ModuleFeedback(user_id=user.id, module=module)
        db.add(row)
    row.note, row.difficulte, row.commentaire, row.modifie_le = note, difficulte, commentaire, utcnow()
    db.commit()
    return row


def as_json(row):
    if row is None:
        return None
    return {"note": row.note, "difficulte": row.difficulte, "commentaire": row.commentaire,
            "modifie_le": row.modifie_le.isoformat(timespec="seconds") + "Z"}


@dataclass
class Summary:
    nombre: int = 0
    moyenne: float | None = None
    difficultes: dict = None  # {clé: nombre}
    commentaires: int = 0


def summaries(db, modules, excluded_emails=frozenset()):
    """Par module : nombre d'avis, note moyenne, répartition des difficultés, commentaires écrits."""
    notes, diffs, comments = defaultdict(list), defaultdict(lambda: dict.fromkeys(DIFFICULTES, 0)), defaultdict(int)
    rows = db.execute(select(ModuleFeedback, User.email).join(User, User.id == ModuleFeedback.user_id)
                      .where(ModuleFeedback.module.in_(modules))).all()
    for row, email in rows:
        if email in excluded_emails:
            continue
        notes[row.module].append(row.note)
        diffs[row.module][row.difficulte] = diffs[row.module].get(row.difficulte, 0) + 1
        comments[row.module] += bool(row.commentaire)
    return {m: Summary(len(notes[m]), round(sum(notes[m]) / len(notes[m]), 1) if notes[m] else None,
                       diffs[m], comments[m]) for m in modules}


def listing(db, module=None, excluded_emails=frozenset(), limit=500):
    """Avis les plus récents d'abord, avec le compte qui l'a donné."""
    q = select(ModuleFeedback, User).join(User, User.id == ModuleFeedback.user_id)
    if module:
        q = q.where(ModuleFeedback.module == module)
    rows = db.execute(q.order_by(ModuleFeedback.modifie_le.desc()).limit(limit)).all()
    return [(row, user) for row, user in rows if user.email not in excluded_emails]


def _cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def to_csv(rows, titres):
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["module", "titre", "email", "nom", "note", "difficulté", "commentaire", "date"])
    for row, user in rows:
        w.writerow([_cell(v) for v in (row.module, titres.get(row.module, ""), user.email, user.nom, row.note,
                                       DIFFICULTES.get(row.difficulte, row.difficulte), row.commentaire,
                                       row.modifie_le.strftime("%Y-%m-%d %H:%M"))])
    return buf.getvalue()

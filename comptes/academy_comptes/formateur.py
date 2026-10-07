"""Tableau de bord formateur : progression des étudiants et points de blocage, par module."""

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select

from . import grading
from .db import Exercise, QcmAttempt, SessionRow, UsageTick, User
from .quotas import month_start

STUCK_AFTER = 3  # vérifications ratées à partir desquelles un étudiant est « bloqué »
ACTIVE_DAYS = 7


@dataclass
class ModuleProgress:
    module: dict  # {id, titre, coef}
    tentatives: list  # notes de QCM
    indices: int = 0
    verifications: int = 0
    reussi_le: datetime | None = None
    grade: grading.ModuleGrade | None = None

    @property
    def commence(self):
        return bool(self.tentatives or self.indices or self.verifications or self.reussi_le)

    @property
    def bloque(self):
        return not self.reussi_le and self.verifications >= STUCK_AFTER


@dataclass
class Student:
    user: User
    modules: list = field(default_factory=list)  # [ModuleProgress], dans l'ordre du parcours
    finale: float | None = None
    derniere_activite: datetime | None = None
    minutes_mois: int = 0

    @property
    def termines(self):
        return sum(1 for m in self.modules if m.grade and m.grade.termine)


@dataclass
class ModuleStats:
    module: dict
    commences: int
    reussis: int
    bloques: int
    verifications_avant_reussite: float | None
    indices: tuple  # étudiants ayant demandé l'indice 1, 2, 3
    qcm_moyen: float | None
    note_moyenne: float | None

    def taux(self, n):
        return round(100 * n / self.commences) if self.commences else 0


def _mean(values):
    values = list(values)
    return round(sum(values) / len(values), 1) if values else None


def students(db, parcours, admin_emails, now):
    """Tous les étudiants (administrateurs exclus), avec leur progression sur le parcours."""
    users = [u for u in db.scalars(select(User).order_by(User.id)) if u.email not in admin_emails]
    ids = [u.id for u in users]
    if not ids:
        return []
    notes = defaultdict(list)
    for a in db.scalars(select(QcmAttempt).where(QcmAttempt.user_id.in_(ids))):
        notes[(a.user_id, a.module)].append(a.note)
    exercises = {(e.user_id, e.module): e for e in db.scalars(select(Exercise).where(Exercise.user_id.in_(ids)))}
    last = defaultdict(list)
    for uid, t in db.execute(select(SessionRow.user_id, func.max(SessionRow.cree_le)).group_by(SessionRow.user_id)):
        last[uid].append(t)
    for uid, t in db.execute(select(UsageTick.user_id, func.max(UsageTick.minute)).group_by(UsageTick.user_id)):
        last[uid].append(t)
    for uid, t in db.execute(select(QcmAttempt.user_id, func.max(QcmAttempt.cree_le)).group_by(QcmAttempt.user_id)):
        last[uid].append(t)
    for uid, t in db.execute(select(Exercise.user_id, func.max(Exercise.reussi_le)).group_by(Exercise.user_id)):
        last[uid].append(t)
    minutes = dict(db.execute(select(UsageTick.user_id, func.count()).where(UsageTick.minute >= month_start(now))
                              .group_by(UsageTick.user_id)).all())
    out = []
    for u in users:
        st = Student(user=u, minutes_mois=minutes.get(u.id, 0),
                     derniere_activite=max((t for t in last[u.id] if t), default=None))
        weighted = []
        for m in parcours["modules"] if parcours else []:
            ex = exercises.get((u.id, m["id"]))
            mp = ModuleProgress(module=m, tentatives=notes[(u.id, m["id"])], indices=ex.indices if ex else 0,
                                verifications=(ex.verifications or 0) if ex else 0,
                                reussi_le=ex.reussi_le if ex else None)
            mp.grade = grading.grade_of(m, mp.tentatives, bool(mp.reussi_le), mp.indices)
            st.modules.append(mp)
            if grading.counts(m):
                weighted.append((m["coef"], mp.grade))
        st.finale = grading.final_grade(weighted)
        out.append(st)
    return out


def module_stats(all_students, parcours):
    stats = []
    for i, m in enumerate(parcours["modules"] if parcours else []):
        rows = [s.modules[i] for s in all_students]
        started = [r for r in rows if r.commence]
        done = [r for r in rows if r.reussi_le]
        stats.append(ModuleStats(
            module=m,
            commences=len(started),
            reussis=len(done),
            bloques=sum(1 for r in rows if r.bloque),
            verifications_avant_reussite=_mean(r.verifications for r in done if r.verifications),
            indices=tuple(sum(1 for r in rows if r.indices >= n) for n in (1, 2, 3)),
            qcm_moyen=_mean(max(r.tentatives) for r in rows if r.tentatives),
            note_moyenne=_mean(r.grade.note for r in rows if r.grade and r.grade.termine),
        ))
    return stats


def overview(all_students, labs_en_cours, now):
    active_since = now - timedelta(days=ACTIVE_DAYS)
    return {
        "inscrits": len(all_students),
        "actifs": sum(1 for s in all_students if s.derniere_activite and s.derniere_activite >= active_since),
        "labs": labs_en_cours,
        "minutes": sum(s.minutes_mois for s in all_students),
        "pro": sum(1 for s in all_students if s.user.formule == "pro"),
        "termines": sum(1 for s in all_students if s.finale is not None),
    }


def matches(student, query):
    q = (query or "").strip().lower()
    return not q or q in student.user.email.lower() or q in (student.user.nom or "").lower()


def _cell(value):
    """Une cellule qui commence par = + - @ serait lue comme une formule par le tableur."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _fr(x):
    return "" if x is None else f"{x:.2f}".replace(".", ",")


def to_csv(all_students, parcours):
    buf = io.StringIO()
    buf.write("﻿")  # BOM : accents corrects à l'ouverture dans un tableur
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    modules = parcours["modules"] if parcours else []
    w.writerow(["id", "email", "nom", "formule", "inscrit le", "dernière activité", "minutes ce mois",
                "modules terminés", "note finale"] + [f"{m['id']} note" for m in modules]
               + [f"{m['id']} indices" for m in modules] + [f"{m['id']} vérifications" for m in modules])
    for s in all_students:
        w.writerow([_cell(v) for v in [
            s.user.id, s.user.email, s.user.nom, s.user.formule, s.user.cree_le.strftime("%Y-%m-%d"),
            s.derniere_activite.strftime("%Y-%m-%d %H:%M") if s.derniere_activite else "", s.minutes_mois,
            s.termines, _fr(s.finale)]
            + [_fr(m.grade.note) if m.grade and m.grade.termine else "" for m in s.modules]
            + [m.indices for m in s.modules] + [m.verifications for m in s.modules]])
    return buf.getvalue()

"""Droits des utilisateurs (RGPD) : export de leurs données et suppression du compte."""

import json
import time
from collections import Counter

from sqlalchemy import delete, select

from . import certificats
from .db import (Access, Answer, Certificate, Exercise, Identity, LoginToken, ModuleFeedback, QcmAttempt, Question,
                 QuestionVote, UsageTick, User)

def _iso(d):
    return d.isoformat(timespec="seconds") + "Z" if d else None


def export_data(db, user):
    """Toutes les données personnelles du compte, lisibles (JSON). Les fichiers du lab restent
    dans le lab (téléchargeables depuis son explorateur de fichiers)."""
    minutes = Counter(t.minute.strftime("%Y-%m") for t in db.scalars(select(UsageTick).where(UsageTick.user_id == user.id)))
    return {
        "compte": {
            "email": user.email,
            "nom": user.nom,
            "formule": user.formule,
            "statut": user.statut,
            "cree_le": _iso(user.cree_le),
            "connexions": sorted(i.fournisseur for i in db.scalars(select(Identity).where(Identity.user_id == user.id))),
        },
        "acces": [{"parcours": a.parcours_id, "origine": a.origine, "debut": _iso(a.debut), "fin": _iso(a.fin),
                   "retire_le": _iso(a.retire_le), "montant_centimes": a.montant_centimes}
                  for a in db.scalars(select(Access).where(Access.user_id == user.id).order_by(Access.debut))],
        "minutes_de_lab_par_mois": dict(sorted(minutes.items())),
        "qcm": [{"module": q.module, "note": q.note, "le": _iso(q.cree_le)}
                for q in db.scalars(select(QcmAttempt).where(QcmAttempt.user_id == user.id).order_by(QcmAttempt.cree_le))],
        "exercices": [{"module": e.module, "indices": e.indices, "verifications": e.verifications,
                       "reussi_le": _iso(e.reussi_le)}
                      for e in db.scalars(select(Exercise).where(Exercise.user_id == user.id).order_by(Exercise.module))],
        "avis": [{"module": a.module, "note": a.note, "difficulte": a.difficulte, "commentaire": a.commentaire,
                  "le": _iso(a.modifie_le)}
                 for a in db.scalars(select(ModuleFeedback).where(ModuleFeedback.user_id == user.id)
                                     .order_by(ModuleFeedback.module))],
        "questions": [{"module": q.module, "titre": q.titre, "texte": q.texte, "privee": q.prive, "le": _iso(q.cree_le)}
                      for q in db.scalars(select(Question).where(Question.user_id == user.id).order_by(Question.cree_le))],
        "reponses": [{"question": a.question_id, "texte": a.texte, "le": _iso(a.cree_le)}
                     for a in db.scalars(select(Answer).where(Answer.user_id == user.id).order_by(Answer.cree_le))],
        "meme_question": sorted(v.question_id for v in db.scalars(select(QuestionVote).where(QuestionVote.user_id == user.id))),
        "certificats": [{"numero": certificats.format_code(c.code), "parcours": c.parcours_titre, "nom": c.nom,
                         "note": c.note, "mention": c.mention, "emis_le": _iso(c.emis_le),
                         "revoque": c.revoque_le is not None}
                        for c in db.scalars(select(Certificate).where(Certificate.user_id == user.id))],
    }


def export_json(db, user):
    return json.dumps(export_data(db, user), ensure_ascii=False, indent=2)


def delete_account(db, user, hub):
    """Supprime le compte : lab (Hub et dossier personnel), puis toutes les lignes en base, accès
    achetés compris. Les paiements et leurs reçus restent chez Stripe (obligation comptable), sans
    lien avec un compte ici.
    """
    hub.delete_user(user.hub_name)  # arrête le lab ; le Hub efface le dossier personnel
    db.execute(delete(LoginToken).where(LoginToken.email == user.email))
    db.delete(user)  # sessions, identités, notes, minutes, certificats : ON DELETE CASCADE
    db.commit()


def wait_until(predicate, timeout, step=1.0, sleep=time.sleep):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        sleep(step)
    return predicate()

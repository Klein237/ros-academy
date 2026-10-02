"""Droits des utilisateurs (RGPD) : export de leurs données et suppression du compte."""

import json
import time
from collections import Counter

from sqlalchemy import delete, select

from . import certificats
from .billing import PAYING
from .db import Certificate, Exercise, Identity, LoginToken, QcmAttempt, UsageTick, User

class DeletionRefused(Exception):
    """Suppression impossible pour l'instant (message présentable)."""


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
            "cree_le": _iso(user.cree_le),
            "connexions": sorted(i.fournisseur for i in db.scalars(select(Identity).where(Identity.user_id == user.id))),
            "abonnement": {
                "statut": user.abonnement_statut,
                "fin": _iso(user.abonnement_fin),
                "resilie": user.abonnement_resilie,
            } if user.stripe_subscription_id else None,
        },
        "minutes_de_lab_par_mois": dict(sorted(minutes.items())),
        "qcm": [{"module": q.module, "note": q.note, "le": _iso(q.cree_le)}
                for q in db.scalars(select(QcmAttempt).where(QcmAttempt.user_id == user.id).order_by(QcmAttempt.cree_le))],
        "exercices": [{"module": e.module, "indices": e.indices, "verifications": e.verifications,
                       "reussi_le": _iso(e.reussi_le)}
                      for e in db.scalars(select(Exercise).where(Exercise.user_id == user.id).order_by(Exercise.module))],
        "certificats": [{"numero": certificats.format_code(c.code), "parcours": c.parcours_titre, "nom": c.nom,
                         "note": c.note, "mention": c.mention, "emis_le": _iso(c.emis_le),
                         "revoque": c.revoque_le is not None}
                        for c in db.scalars(select(Certificate).where(Certificate.user_id == user.id))],
    }


def export_json(db, user):
    return json.dumps(export_data(db, user), ensure_ascii=False, indent=2)


def delete_account(db, user, hub):
    """Supprime le compte : lab (Hub et dossier personnel), puis toutes les lignes en base.

    Refusé tant qu'un abonnement est en cours (il continuerait d'être facturé). Les factures
    restent chez Stripe (obligation comptable), sans lien avec un compte ici.
    """
    if user.stripe_subscription_id and user.abonnement_statut in PAYING and not user.abonnement_resilie:
        raise DeletionRefused("Votre abonnement pro est en cours : résiliez-le d'abord (Mon abonnement), "
                              "puis supprimez votre compte.")
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

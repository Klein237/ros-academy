"""Profils publics des formateurs : chacun modifie le sien, la page « Qui sommes-nous » les affiche."""

import re

from sqlalchemy import select

from .db import TrainerProfile, User, utcnow

# Tant qu'aucun formateur n'a publié son profil, la page présente l'équipe fondatrice
EQUIPE_PAR_DEFAUT = [
    {"nom": "Ivan", "titre": "", "linkedin": "https://www.linkedin.com/in/ivan-tk0122/"},
    {"nom": "Yves Thoukam", "titre": "", "linkedin": "https://www.linkedin.com/in/yves-thoukam-a57635207/"},
    {"nom": "Franklin Yangoua", "titre": "", "linkedin": "https://www.linkedin.com/in/franklin-yangoua/"},
]

# Un profil LinkedIn, en https : jamais d'autre schéma (javascript:, data:…) dans un lien public
LINKEDIN_RE = re.compile(r"^https://([a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_%\-]+/?$")


class ProfileError(ValueError):
    pass


def initiales(nom):
    mots = [m for m in re.split(r"[\s\-]+", nom.strip()) if m]
    return "".join(m[0].upper() for m in mots[:2]) or "?"


def get(db, user):
    return db.get(TrainerProfile, user.id)


def save(db, user, nom, titre, linkedin, visible):
    nom, titre, linkedin = " ".join(nom.split()), " ".join(titre.split()), linkedin.strip()
    if len(nom) > 80:
        raise ProfileError("Le nom fait 80 caractères au plus.")
    if len(titre) > 120:
        raise ProfileError("Le titre fait 120 caractères au plus.")
    if linkedin and not LINKEDIN_RE.match(linkedin):
        raise ProfileError("Le lien LinkedIn doit ressembler à https://www.linkedin.com/in/votre-profil/")
    if visible and not nom:
        raise ProfileError("Indiquez votre nom pour apparaître sur la page « Qui sommes-nous ».")
    row = db.get(TrainerProfile, user.id)
    if row is None:
        row = TrainerProfile(user_id=user.id)
        db.add(row)
    row.nom, row.titre, row.linkedin, row.visible, row.modifie_le = nom, titre, linkedin, bool(visible), utcnow()
    db.commit()
    return row


def public(db, staff_emails):
    """Profils affichés : visibles et dont l'auteur fait encore partie de l'équipe, du plus ancien au plus récent."""
    rows = db.execute(select(TrainerProfile, User.email).join(User, User.id == TrainerProfile.user_id)
                      .where(TrainerProfile.visible.is_(True)).order_by(TrainerProfile.cree_le, TrainerProfile.user_id))
    return [{"nom": p.nom, "titre": p.titre, "linkedin": p.linkedin} for p, email in rows if email in staff_emails]


def team(db, staff_emails):
    membres = public(db, staff_emails) or EQUIPE_PAR_DEFAUT
    return [{**m, "initiales": initiales(m["nom"])} for m in membres]

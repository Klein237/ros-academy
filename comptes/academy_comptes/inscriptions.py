"""Inscriptions par vagues (phase de test) et équipe des formateurs.

Un nombre de places limite les comptes actifs ; au-delà, un nouveau compte attend sur la liste
d'attente qu'un formateur l'invite (à la main, ou en ouvrant une vague). Sans nombre de places,
toute inscription est acceptée. Les administrateurs (ADMIN_EMAILS) et les formateurs ne prennent
pas de place et ne passent jamais par la liste d'attente.
"""

from sqlalchemy import func, select

from .db import Reglage, Trainer, User, utcnow

NOUVEAU = "nouveau"  # adresse pas encore confirmée : statut décidé à la première connexion
ACTIF = "actif"
ATTENTE = "en_attente"
DESINSCRIT = "desinscrit"
PLACES = "inscriptions_places"
PLACES_MAX = 100000


def is_admin(settings, email):
    return email in settings.admin_emails


def trainer_emails(db):
    return {t.email for t in db.scalars(select(Trainer))}


def staff_emails(db, settings):
    """Administrateurs et formateurs : accès au tableau de bord, jamais sur la liste d'attente."""
    return set(settings.admin_emails) | trainer_emails(db)


def is_staff(db, settings, email):
    return is_admin(settings, email) or db.get(Trainer, email) is not None


def places(db):
    """Nombre de places de la phase de test ; None : sans limite."""
    row = db.get(Reglage, PLACES)
    return int(row.valeur) if row and row.valeur else None


def set_places(db, n):
    row = db.get(Reglage, PLACES) or Reglage(cle=PLACES)
    row.valeur = "" if n is None else str(n)
    db.merge(row)
    db.commit()


def occupied(db, settings):
    """Places prises : comptes actifs à l'adresse confirmée, administrateurs et formateurs exclus."""
    staff = staff_emails(db, settings)
    emails = db.scalars(select(User.email).where(User.statut == ACTIF, User.email_verifie_le.is_not(None)))
    return sum(1 for e in emails if e not in staff)


def free(db, settings):
    """Places libres ; None : sans limite."""
    n = places(db)
    return None if n is None else max(0, n - occupied(db, settings))


def waiting(db):
    """Liste d'attente, dans l'ordre d'arrivée."""
    return list(db.scalars(select(User).where(User.statut == ATTENTE).order_by(User.attente_depuis, User.id)))


def waiting_count(db):
    return db.scalar(select(func.count()).select_from(User).where(User.statut == ATTENTE))


def position(db, user):
    """Rang sur la liste d'attente (1 : le prochain invité)."""
    if user.statut != ATTENTE:
        return None
    return 1 + db.scalar(select(func.count()).select_from(User).where(
        User.statut == ATTENTE, (User.attente_depuis < user.attente_depuis)
        | ((User.attente_depuis == user.attente_depuis) & (User.id < user.id))))


def admit(db, settings, user):
    """À la connexion : place un nouveau compte (actif ou sur la liste d'attente). Vrai s'il vient
    d'entrer sur la liste d'attente (à prévenir par e-mail)."""
    if is_staff(db, settings, user.email):
        if user.statut != ACTIF:
            user.statut, user.attente_depuis = ACTIF, None
            db.commit()
        return False
    if user.statut != NOUVEAU:
        return False
    if free(db, settings) == 0:
        user.statut, user.attente_depuis = ATTENTE, utcnow()
    else:
        user.statut = ACTIF
    db.commit()
    return user.statut == ATTENTE


def activate(db, user):
    user.statut, user.attente_depuis = ACTIF, None
    db.commit()


def unsubscribe(db, user):
    user.statut, user.attente_depuis = DESINSCRIT, None
    db.commit()


def open_wave(db, settings, extra):
    """Ajoute `extra` places (0 : seulement les places libérées), puis invite les premiers de la
    liste d'attente sur les places libres. Renvoie les comptes activés."""
    n = places(db)
    if n is None:  # sans limite : toute la liste d'attente entre
        invited = waiting(db)
    else:
        set_places(db, min(PLACES_MAX, max(n, occupied(db, settings)) + extra))
        invited = waiting(db)[:free(db, settings)]
    for user in invited:
        user.statut, user.attente_depuis = ACTIF, None
    db.commit()
    return invited

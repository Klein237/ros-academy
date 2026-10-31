"""Profils publics des formateurs : chacun modifie le sien, la page « Qui sommes-nous » les affiche."""

import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError
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


PHOTO_MAX_OCTETS = 5 * 1024 * 1024
PHOTO_COTE = 320  # carré, affiché à 104 px (net sur écran haute densité)
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


class ProfileError(ValueError):
    pass


def prepare_photo(data):
    """Photo envoyée → carré WebP de PHOTO_COTE px. Réencoder retire les métadonnées (EXIF, GPS) et
    tout contenu caché : seuls les pixels passent."""
    if len(data) > PHOTO_MAX_OCTETS:
        raise ProfileError("La photo fait 5 Mo au plus.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in PHOTO_FORMATS:
                raise ProfileError("La photo doit être au format JPEG, PNG ou WebP.")
            if im.width * im.height > 40_000_000:
                raise ProfileError("La photo est trop grande (40 mégapixels au plus).")
            im = ImageOps.exif_transpose(im).convert("RGB")
            im = ImageOps.fit(im, (PHOTO_COTE, PHOTO_COTE), Image.Resampling.LANCZOS, centering=(0.5, 0.4))
            out = io.BytesIO()
            im.save(out, "WEBP", quality=85, method=6)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as exc:
        if isinstance(exc, ProfileError):
            raise
        raise ProfileError("Ce fichier n'est pas une image lisible (JPEG, PNG ou WebP).") from None


def initiales(nom):
    mots = [m for m in re.split(r"[\s\-]+", nom.strip()) if m]
    return "".join(m[0].upper() for m in mots[:2]) or "?"


def get(db, user):
    return db.get(TrainerProfile, user.id)


def save(db, user, nom, titre, linkedin, visible, photo=None, retirer_photo=False):
    nom, titre, linkedin = " ".join(nom.split()), " ".join(titre.split()), linkedin.strip()
    if len(nom) > 80:
        raise ProfileError("Le nom fait 80 caractères au plus.")
    if len(titre) > 120:
        raise ProfileError("Le titre fait 120 caractères au plus.")
    if linkedin and not LINKEDIN_RE.match(linkedin):
        raise ProfileError("Le lien LinkedIn doit ressembler à https://www.linkedin.com/in/votre-profil/")
    if visible and not nom:
        raise ProfileError("Indiquez votre nom pour apparaître sur la page « Qui sommes-nous ».")
    webp = prepare_photo(photo) if photo else None
    row = db.get(TrainerProfile, user.id)
    if row is None:
        row = TrainerProfile(user_id=user.id, photo_version=0)
        db.add(row)
    row.nom, row.titre, row.linkedin, row.visible, row.modifie_le = nom, titre, linkedin, bool(visible), utcnow()
    if webp:
        row.photo, row.photo_version = webp, (row.photo_version or 0) + 1
    elif retirer_photo:
        row.photo = None
    db.commit()
    return row


def public(db, staff_emails):
    """Profils affichés : visibles et dont l'auteur fait encore partie de l'équipe, du plus ancien au plus récent."""
    rows = db.execute(select(TrainerProfile, User.email).join(User, User.id == TrainerProfile.user_id)
                      .where(TrainerProfile.visible.is_(True)).order_by(TrainerProfile.cree_le, TrainerProfile.user_id))
    return [{"nom": p.nom, "titre": p.titre, "linkedin": p.linkedin, "photo": photo_url(p)}
            for p, email in rows if email in staff_emails]


def photo_url(profile):
    return f"/compte/equipe/photos/{profile.user_id}.webp?v={profile.photo_version}" if profile and profile.photo else ""


def photo_visible(db, profile, staff_emails, viewer):
    """La photo d'un profil publié est publique ; sinon, seul son auteur la voit (aperçu)."""
    if not profile or not profile.photo:
        return False
    if viewer is not None and viewer.id == profile.user_id:
        return True
    owner = db.get(User, profile.user_id)
    return bool(profile.visible and owner and owner.email in staff_emails)


def team(db, staff_emails):
    membres = public(db, staff_emails) or EQUIPE_PAR_DEFAUT
    return [{"photo": "", **m, "initiales": initiales(m["nom"])} for m in membres]

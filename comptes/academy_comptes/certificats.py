"""Certificats de fin de parcours : émission figée, page publique et PDF vérifiable."""

import io
import json
import re
import secrets
from dataclasses import dataclass

from sqlalchemy import select

from . import grading
from .db import Certificate, utcnow

# Base 32 sans 0/O, 1/I/L : se recopie sans erreur depuis un papier
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LEN = 16
CODE_RE = re.compile(rf"^[{ALPHABET}]{{{CODE_LEN}}}$")
# lettres (accents compris), espaces, apostrophes, traits d'union et points ; commence par une lettre
NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ '’.\-])*$")
NAME_MIN, NAME_MAX = 2, 80


class CertificateError(Exception):
    """Refus présentable à l'étudiant."""


@dataclass
class Eligibility:
    ok: bool
    finale: float | None
    raison: str = ""
    modules: list = None  # [{titre, coef, note}]


def mention(note):
    if note >= 16:
        return "Très bien"
    if note >= 14:
        return "Bien"
    if note >= 12:
        return "Assez bien"
    return ""


def new_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))


def format_code(code):
    """« ABCD-EFGH-JKMN-PQRS » : plus lisible sur le papier."""
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def normalize_code(raw):
    code = (raw or "").upper().replace("-", "").replace(" ", "")
    return code if CODE_RE.fullmatch(code) else None


def clean_name(raw):
    name = " ".join((raw or "").split())
    if not NAME_MIN <= len(name) <= NAME_MAX or not NAME_RE.fullmatch(name):
        raise CertificateError("Indiquez votre nom tel qu'il doit figurer sur le certificat "
                               f"({NAME_MIN} à {NAME_MAX} caractères : lettres, espaces, apostrophes, traits d'union).")
    return name


def eligibility(parcours, notes_and_exercises, note_min):
    """notes_and_exercises : {module_id: (notes de QCM, réussi, indices)}."""
    weighted, modules = [], []
    for m in parcours["modules"]:
        notes, reussi, indices = notes_and_exercises.get(m["id"], ([], False, 0))
        g = grading.grade_of(m, notes, reussi, indices)
        if not grading.counts(m):
            continue  # bonus : hors certificat
        weighted.append((m["coef"], g))
        modules.append({"titre": m["titre"], "coef": m["coef"], "note": g.note})
    finale = grading.final_grade(weighted)
    if finale is None:
        return Eligibility(False, None, "Terminez tous les modules du parcours (QCM passé, et exercice réussi quand le module en a un).", modules)
    if finale < note_min:
        note_min_txt = f"{note_min:g}".replace(".", ",")
        return Eligibility(False, finale, f"Le certificat demande une note finale d'au moins {note_min_txt} / 20.",
                           modules)
    return Eligibility(True, finale, "", modules)


def existing(db, user_id, parcours_id):
    return db.scalar(select(Certificate).where(Certificate.user_id == user_id, Certificate.parcours_id == parcours_id))


def issue(db, user, parcours, elig, name):
    if existing(db, user.id, parcours["id"]):
        raise CertificateError("Vous avez déjà un certificat pour ce parcours.")
    if not elig.ok:
        raise CertificateError(elig.raison)
    cert = Certificate(code=new_code(), user_id=user.id, parcours_id=parcours["id"],
                       parcours_titre=parcours["titre"][:200], nom=clean_name(name), note=round(elig.finale, 2),
                       mention=mention(elig.finale), modules_json=json.dumps(elig.modules, ensure_ascii=False),
                       emis_le=utcnow())
    db.add(cert)
    db.commit()
    return cert


def modules(cert):
    return json.loads(cert.modules_json)


def fr(x, digits=2):
    return f"{x:.{digits}f}".replace(".", ",")


MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]


def date_fr(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def render_pdf(cert, verify_url):
    """Certificat A4 paysage ; polices standard (accents et « » compris), QR code vers la page de vérification."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    accent, ink, muted = HexColor("#0f766e"), HexColor("#1c232b"), HexColor("#5c6773")
    buf = io.BytesIO()
    w, h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(w, h), invariant=1)
    c.setTitle(f"Certificat RoboForge — {cert.nom}")
    c.setAuthor("RoboForge")
    c.setSubject(cert.parcours_titre)

    c.setStrokeColor(accent)
    c.setLineWidth(3)
    c.rect(28, 28, w - 56, h - 56)
    c.setLineWidth(0.8)
    c.rect(36, 36, w - 72, h - 72)

    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, h - 82, "ROBOFORGE")
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(w / 2, h - 130, "Certificat de réussite")
    c.setFillColor(muted)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 165, "décerné à")
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(w / 2, h - 205, cert.nom)
    c.setFillColor(muted)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 238, "pour avoir terminé le parcours")
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(w / 2, h - 264, cert.parcours_titre)
    result = f"Note finale : {fr(cert.note)} / 20" + (f" — mention {cert.mention}" if cert.mention else "")
    c.setFont("Helvetica", 14)
    c.drawCentredString(w / 2, h - 292, result)

    # détail des modules, sur deux colonnes si besoin
    mods = modules(cert)
    c.setFont("Helvetica", 10)
    c.setFillColor(muted)
    top, col_w = h - 330, 330
    per_col = max(1, (len(mods) + 1) // 2) if len(mods) > 4 else len(mods)
    cols = 1 if len(mods) <= 4 else 2
    x0 = w / 2 - (col_w * cols) / 2
    for i, m in enumerate(mods):
        col, row = divmod(i, per_col)
        x, y = x0 + col * col_w, top - row * 15
        c.drawString(x + 10, y, f"{m['titre'][:46]} (coef. {m['coef']:g})")
        c.drawRightString(x + col_w - 10, y, f"{fr(m['note'])} / 20")

    # pied : date, code, adresse et QR code de vérification
    c.setFillColor(ink)
    c.setFont("Helvetica", 11)
    c.drawString(60, 92, f"Délivré le {date_fr(cert.emis_le)}")
    c.drawString(60, 76, f"Certificat n° {format_code(cert.code)}")
    c.setFillColor(muted)
    c.setFont("Helvetica", 9)
    c.drawString(60, 58, f"Vérifier ce certificat : {verify_url}")
    qr = QrCodeWidget(verify_url)
    x1, y1, x2, y2 = qr.getBounds()
    size = 84
    d = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    d.add(qr)
    renderPDF.draw(d, c, w - 60 - size, 48)
    c.showPage()
    c.save()
    return buf.getvalue()

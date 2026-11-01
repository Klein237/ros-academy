"""Tableau de bord « Mon apprentissage » : temps passé dans le lab, questions, badges, graphique."""

from datetime import datetime, timedelta

from sqlalchemy import select

from .db import Answer, Question, UsageTick, utcnow

SEMAINES = 8
# objet en verre de chaque parcours (contenus/academy_content/static/icones/) ; les autres : le graphe de nœuds
ICONES = {"ros2-fondamentaux": "robot", "bras-robotique": "bras", "docker-robotique": "conteneur", "tests-logiciel": "bouclier"}


def icone(parcours_id):
    return ICONES.get(parcours_id, "noeuds")


def week_start(d):
    """Lundi 0 h de la semaine de d."""
    return datetime(d.year, d.month, d.day) - timedelta(days=d.weekday())


def weekly_minutes(db, user, now=None, weeks=SEMAINES):
    """Minutes de lab des `weeks` dernières semaines (lundi → dimanche), la plus ancienne d'abord."""
    debut = week_start(now or utcnow()) - timedelta(weeks=weeks - 1)
    comptes = [0] * weeks
    for minute in db.scalars(select(UsageTick.minute).where(UsageTick.user_id == user.id, UsageTick.minute >= debut)):
        i = (minute - debut).days // 7
        if 0 <= i < weeks:
            comptes[i] += 1
    return [{"debut": debut + timedelta(weeks=i), "minutes": m} for i, m in enumerate(comptes)]


MOIS = 12
NOMS_MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def month_start(d):
    return datetime(d.year, d.month, 1)


def add_months(d, n):
    m = d.month - 1 + n
    return datetime(d.year + m // 12, m % 12 + 1, 1)


def monthly_minutes(db, user, now=None, months=MOIS):
    """Minutes de lab des `months` derniers mois, le plus ancien d'abord. Le quota reste mensuel ; l'historique,
    lui, se garde : rien n'est effacé d'un mois à l'autre."""
    debut = add_months(month_start(now or utcnow()), -(months - 1))
    comptes = [0] * months
    for minute in db.scalars(select(UsageTick.minute).where(UsageTick.user_id == user.id, UsageTick.minute >= debut)):
        i = (minute.year - debut.year) * 12 + minute.month - debut.month
        if 0 <= i < months:
            comptes[i] += 1
    out = []
    for i, m in enumerate(comptes):
        d = add_months(debut, i)
        libelle = NOMS_MOIS[d.month - 1] + (f" {d.year % 100:02d}" if d.month == 1 or i == 0 else "")
        out.append({"debut": d, "minutes": m, "libelle": libelle, "mois": f"{NOMS_MOIS[d.month - 1]} {d.year}"})
    return out


def chart(semaines, largeur=560, hauteur=180, marge=24):
    """Barres du graphique, calculées ici : la page n'a pas le droit aux styles en ligne (CSP)."""
    pas = largeur / len(semaines)
    barre = pas * 0.56
    plus = max((s["minutes"] for s in semaines), default=0)
    out = []
    for i, s in enumerate(semaines):
        h = 0 if not s["minutes"] else max(2.0, (hauteur - marge) * s["minutes"] / plus)
        derniere = i == len(semaines) - 1
        out.append({
            "x": round(i * pas + (pas - barre) / 2, 1), "largeur": round(barre, 1), "y": round(hauteur - h, 1),
            "hauteur": round(h, 1), "minutes": s["minutes"], "derniere": derniere,
            "zone_x": round(i * pas, 1), "zone_largeur": round(pas, 1), "centre": round(i * pas + pas / 2, 1),
            "etiquette": f"{s['minutes']} min" if s["minutes"] and (derniere or s["minutes"] == plus) else "",
            "date": s.get("libelle") or s["debut"].strftime("%d/%m"),
            "periode": s.get("mois") or f"Semaine du {s['debut'].strftime('%d/%m')}",
        })
    return {"barres": out, "largeur": largeur, "hauteur": hauteur, "total": sum(s["minutes"] for s in semaines)}


def my_questions(db, user):
    """Questions de l'étudiant : combien, combien ont une réponse de l'équipe, et la dernière à relire."""
    qs = list(db.scalars(select(Question).where(Question.user_id == user.id).order_by(Question.activite_le.desc())))
    if not qs:
        return {"total": 0, "repondues": 0, "derniere": None}
    repondues = set(db.scalars(select(Answer.question_id).where(
        Answer.question_id.in_([q.id for q in qs]), Answer.equipe.is_(True), Answer.masquee_le.is_(None))))
    return {"total": len(qs), "repondues": len(repondues), "derniere": qs[0]}


def badges(progression):
    """Un badge par module noté du parcours : validé, en cours ou à venir (les bonus restent à part)."""
    out = []
    for i, r in enumerate(progression["modules"], 1):
        if r["module"].get("bonus"):
            continue
        out.append({"numero": i, "titre": r["module"]["titre"], "etat": r["etat"], "id": r["module"]["id"]})
    return out

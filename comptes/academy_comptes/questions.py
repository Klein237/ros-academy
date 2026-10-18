"""Questions et réponses sur les modules : l'étudiant bloqué demande, l'équipe (et les autres étudiants)
répondent, et la réponse reste pour ceux qui suivent.

Une question est visible des étudiants qui ont accès au module, sauf si elle est privée (son auteur et
l'équipe seulement). L'équipe peut masquer un message ; un étudiant peut le signaler.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select

from .db import Answer, Exercise, Question, QuestionVote, Reglage, User, utcnow

TITRE_MAX = 150
TEXTE_MAX = 5000
QUESTIONS_PAR_JOUR = 10
REPONSES_PAR_JOUR = 40
ATTENTE_ALERTE = timedelta(hours=24)  # au-delà, la question est en rouge dans le tableau de bord
DIGEST = "questions_digest"
DIGEST_INTERVALLE = timedelta(hours=1)


class InvalidPost(ValueError):
    pass


def first_name(user):
    """Seul le prénom est affiché (premier mot du nom), jamais l'adresse."""
    if user is None:
        return "Ancien étudiant"
    words = (user.nom or "").split()
    return words[0][:40] if words else "Étudiant"


def _clean(text, maximum, label):
    text = (text or "").strip()
    if not text:
        raise InvalidPost(f"{label} est vide.")
    if len(text) > maximum:
        raise InvalidPost(f"{label} est trop long ({maximum} caractères au plus).")
    return text


def _today_count(db, model, user):
    since = utcnow() - timedelta(days=1)
    return db.scalar(select(func.count()).select_from(model).where(model.user_id == user.id, model.cree_le > since))


def ask(db, user, module, titre, texte, prive=False, solution=False, joindre_verification=False):
    if _today_count(db, Question, user) >= QUESTIONS_PAR_JOUR:
        raise InvalidPost("Vous avez posé beaucoup de questions aujourd'hui : réessayez demain.")
    journal = ""
    if joindre_verification:
        ex = db.get(Exercise, (user.id, module))
        journal = (ex.dernier_journal or "") if ex else ""
    q = Question(user_id=user.id, module=module, titre=_clean(titre, TITRE_MAX, "Le titre"),
                 texte=_clean(texte, TEXTE_MAX, "La question"), prive=bool(prive), solution=bool(solution),
                 journal=journal[-4000:])
    db.add(q)
    db.commit()
    return q


def answer(db, user, question, texte, solution, equipe):
    if _today_count(db, Answer, user) >= REPONSES_PAR_JOUR:
        raise InvalidPost("Vous avez beaucoup répondu aujourd'hui : réessayez demain.")
    a = Answer(question_id=question.id, user_id=user.id, texte=_clean(texte, TEXTE_MAX, "La réponse"),
               solution=bool(solution), equipe=bool(equipe))
    db.add(a)
    question.activite_le = utcnow()
    db.commit()
    return a


def can_see(question, user, staff):
    if staff:
        return True
    if question.masquee_le is not None:
        return False
    return not question.prive or question.user_id == user.id


def listing(db, module, viewer, staff):
    """Questions du module visibles par ce compte, les plus récemment actives d'abord."""
    rows = db.scalars(select(Question).where(Question.module == module).order_by(Question.activite_le.desc()))
    return [q for q in rows if can_see(q, viewer, staff)]


def _iso(d):
    return d.isoformat(timespec="seconds") + "Z" if d else None


def as_json(db, questions, viewer, staff):
    ids = [q.id for q in questions]
    answers = {}
    for a in db.scalars(select(Answer).where(Answer.question_id.in_(ids)).order_by(Answer.cree_le)) if ids else []:
        if staff or a.masquee_le is None:
            answers.setdefault(a.question_id, []).append(a)
    votes, mine = votes_of(db, ids, viewer)
    user_ids = {q.user_id for q in questions} | {a.user_id for lst in answers.values() for a in lst if a.user_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    out = []
    for q in questions:
        lst = sorted(answers.get(q.id, []), key=lambda a: (not a.equipe, not a.validee, a.cree_le))
        item = {
            "id": q.id, "titre": q.titre, "texte": q.texte, "auteur": first_name(users.get(q.user_id)),
            "moi": q.user_id == viewer.id, "prive": q.prive, "solution": q.solution,
            "resolue": q.resolue_le is not None, "cree_le": _iso(q.cree_le),
            "reponse_equipe": any(a.equipe for a in lst),
            "meme": votes.get(q.id, 0), "moi_meme": q.id in mine,
            "reponses": [{
                "id": a.id, "texte": a.texte, "auteur": first_name(users.get(a.user_id)), "equipe": a.equipe,
                "validee": a.validee, "solution": a.solution, "moi": a.user_id == viewer.id,
                "cree_le": _iso(a.cree_le),
                **({"masquee": a.masquee_le is not None, "signalements": a.signalements} if staff else {}),
            } for a in lst],
        }
        if staff:
            item.update(journal=q.journal, masquee=q.masquee_le is not None, signalements=q.signalements)
        out.append(item)
    return out


def votes_of(db, question_ids, viewer=None):
    """{question: nombre de « J'ai la même question »}, et les questions où ce compte l'a dit."""
    if not question_ids:
        return {}, set()
    counts = dict(db.execute(select(QuestionVote.question_id, func.count()).where(
        QuestionVote.question_id.in_(question_ids)).group_by(QuestionVote.question_id)).all())
    mine = set(db.scalars(select(QuestionVote.question_id).where(
        QuestionVote.question_id.in_(question_ids), QuestionVote.user_id == viewer.id))) if viewer else set()
    return counts, mine


def same_question(db, user, question, valeur):
    """« J'ai la même question » (ou le retirer). Pas sur sa propre question."""
    if question.user_id == user.id:
        raise InvalidPost("C'est votre propre question.")
    row = db.get(QuestionVote, (user.id, question.id))
    if valeur and row is None:
        db.add(QuestionVote(user_id=user.id, question_id=question.id))
    elif not valeur and row is not None:
        db.delete(row)
    db.commit()


def followers(db, question):
    """Comptes à prévenir d'une réponse de l'équipe : ceux qui ont la même question."""
    return list(db.scalars(select(User).join(QuestionVote, QuestionVote.user_id == User.id)
                           .where(QuestionVote.question_id == question.id)))


def unanswered(db, staff_emails):
    """Questions sans réponse de l'équipe ni résolution, la plus ancienne d'abord (tableau de bord)."""
    answered = select(Answer.question_id).where(Answer.equipe.is_(True))
    rows = db.execute(select(Question, User).join(User, User.id == Question.user_id)
                      .where(Question.resolue_le.is_(None), Question.masquee_le.is_(None),
                             Question.id.not_in(answered))
                      .order_by(Question.cree_le)).all()
    return [(q, u) for q, u in rows if u.email not in staff_emails]


def reported(db):
    """Messages signalés et encore visibles, pour la modération."""
    qs = list(db.scalars(select(Question).where(Question.signalements > 0, Question.masquee_le.is_(None))))
    ans = list(db.scalars(select(Answer).where(Answer.signalements > 0, Answer.masquee_le.is_(None))))
    return qs, ans


def digest_due(db, now):
    """Récapitulatif aux formateurs : au plus une fois par heure, s'il y a de nouvelles questions.
    Renvoie le nombre de nouvelles questions à annoncer (0 : rien à envoyer)."""
    row = db.get(Reglage, DIGEST)
    last = None
    if row and row.valeur:
        try:
            last = datetime.fromisoformat(row.valeur)
        except ValueError:
            last = None
    if last and now - last < DIGEST_INTERVALLE:
        return 0
    since = last or now - DIGEST_INTERVALLE
    count = db.scalar(select(func.count()).select_from(Question).where(Question.cree_le > since,
                                                                       Question.masquee_le.is_(None)))
    if count:
        db.merge(Reglage(cle=DIGEST, valeur=now.isoformat()))
        db.commit()
    return count

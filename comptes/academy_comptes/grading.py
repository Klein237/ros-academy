"""Notation (spec) : module sur 20 = 50 % QCM + 50 % exercice ; note finale pondérée.

Un module sans exercice (cours théorique) est noté sur son seul QCM. Les modules bonus
sont suivis et notés, mais ne comptent pas dans la note finale du parcours.
"""

from dataclasses import dataclass

HINT_PENALTY = 0.15
MAX_HINTS = 3
MAX_QCM_ATTEMPTS = 2


@dataclass(frozen=True)
class ModuleGrade:
    qcm: float | None  # meilleure tentative sur 20, None si aucune
    exercice: float | None  # sur 20 ; None pour un module sans exercice
    note: float  # sur 20
    termine: bool


def exercise_score(reussi, indices):
    """100 % sans indice, −15 % par indice (3 au plus) ; 0 tant que l'exercice n'est pas réussi."""
    if not reussi:
        return 0.0
    return 20.0 * (1 - HINT_PENALTY * min(max(indices, 0), MAX_HINTS))


def module_grade(qcm_notes, reussi, indices, avec_exercice=True):
    best = max(qcm_notes) if qcm_notes else None
    if not avec_exercice:
        return ModuleGrade(qcm=best, exercice=None, note=round(best or 0.0, 2), termine=best is not None)
    exercice = exercise_score(reussi, indices)
    note = 0.5 * (best or 0.0) + 0.5 * exercice
    return ModuleGrade(qcm=best, exercice=exercice, note=round(note, 2), termine=bool(reussi) and best is not None)


def grade_of(module, qcm_notes, reussi, indices):
    """Note d'un module du parcours (dictionnaire de l'API Contenus : exercice, bonus…)."""
    return module_grade(qcm_notes, reussi, indices, avec_exercice=module.get("exercice", True))


def counts(module):
    """Vrai si le module compte dans la note finale (les bonus n'y comptent pas)."""
    return not module.get("bonus", False)


def final_grade(weighted):
    """weighted : [(coef, ModuleGrade)] ; None tant qu'un module n'est pas terminé."""
    if not weighted or not all(g.termine for _, g in weighted):
        return None
    total = sum(coef for coef, _ in weighted)
    return round(sum(coef * g.note for coef, g in weighted) / total, 2)

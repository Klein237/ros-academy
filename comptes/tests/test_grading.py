import pytest

from academy_comptes.grading import counts, exercise_score, final_grade, grade_of, module_grade


@pytest.mark.parametrize("indices, expected", [(0, 20.0), (1, 17.0), (2, 14.0), (3, 11.0), (5, 11.0)])
def test_hint_penalty(indices, expected):
    assert exercise_score(True, indices) == pytest.approx(expected)


def test_exercise_not_done_is_zero():
    assert exercise_score(False, 0) == 0


def test_module_grade_keeps_best_attempt():
    g = module_grade([12.0, 16.0], True, 1)
    assert g.qcm == 16.0 and g.exercice == pytest.approx(17.0)
    assert g.note == pytest.approx(16.5) and g.termine


def test_module_not_finished_without_qcm_or_success():
    assert not module_grade([], True, 0).termine
    assert not module_grade([20.0], False, 0).termine
    assert module_grade([20.0], False, 0).note == 10.0


def test_final_grade_weighted_by_coefficients():
    a = module_grade([20.0], True, 0)  # 20
    b = module_grade([10.0], True, 2)  # 0.5*10 + 0.5*14 = 12
    assert final_grade([(1, a), (3, b)]) == pytest.approx((20 + 3 * 12) / 4)


def test_final_grade_needs_every_module():
    assert final_grade([(1, module_grade([20.0], True, 0)), (1, module_grade([], False, 0))]) is None
    assert final_grade([]) is None


def test_course_module_is_graded_on_its_qcm():
    """Module de cours, sans exercice : la note est celle du QCM, terminé dès le QCM passé."""
    g = grade_of({"id": "03-cours", "exercice": False}, [12.0, 15.0], False, 0)
    assert g.exercice is None and g.note == 15.0 and g.termine
    assert not grade_of({"id": "03-cours", "exercice": False}, [], False, 0).termine
    # ancien format (sans la clé) : module avec exercice
    assert grade_of({"id": "02-b"}, [20.0], False, 0).note == 10.0


def test_bonus_modules_do_not_count():
    assert counts({"id": "02-b"}) and not counts({"id": "12-qos", "bonus": True})

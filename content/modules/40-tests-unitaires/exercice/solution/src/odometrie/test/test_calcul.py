import math

import pytest

from odometrie.calcul import integrer, normaliser, vitesses_roues


def test_immobile():
    assert integrer((1.0, 2.0, 0.5), 0.0, 0.0, 0.1) == (1.0, 2.0, 0.5)


def test_tout_droit_selon_x():
    assert integrer((0.0, 0.0, 0.0), 1.0, 0.0, 2.0) == pytest.approx((2.0, 0.0, 0.0))


def test_tout_droit_selon_y():
    assert integrer((0.0, 0.0, math.pi / 2), 1.0, 0.0, 2.0) == pytest.approx((0.0, 2.0, math.pi / 2))


def test_rotation_sur_place_tient_compte_de_dt():
    assert integrer((0.0, 0.0, 0.0), 0.0, 0.5, 2.0) == pytest.approx((0.0, 0.0, 1.0))


def test_angle_ramene_dans_moins_pi_pi():
    _, _, theta = integrer((0.0, 0.0, 3.0), 0.0, 1.0, 1.0)
    assert theta == pytest.approx(4.0 - 2 * math.pi)


@pytest.mark.parametrize("angle, attendu", [(math.pi, math.pi), (-math.pi, math.pi), (3 * math.pi, math.pi),
                                            (0.0, 0.0), (-3 * math.pi / 2, math.pi / 2)])
def test_normaliser(angle, attendu):
    assert normaliser(angle) == pytest.approx(attendu)


def test_vitesses_roues_en_virage():
    assert vitesses_roues(1.0, 2.0, 0.5) == pytest.approx((0.5, 1.5))


def test_vitesses_roues_tout_droit():
    assert vitesses_roues(0.3, 0.0, 0.5) == pytest.approx((0.3, 0.3))

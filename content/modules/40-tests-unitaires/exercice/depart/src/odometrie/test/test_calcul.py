from odometrie.calcul import integrer


def test_immobile():
    assert integrer((1.0, 2.0, 0.5), 0.0, 0.0, 0.1) == (1.0, 2.0, 0.5)

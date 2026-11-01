## Indice 1

Un test avec `v = 0` et `w = 0` ne vérifie ni `cos`, ni `sin`, ni `dt`. Faites bouger le robot : tout droit face à x, puis face à y (`theta = pi / 2`), et comparez avec `pytest.approx`.

## Indice 2

Choisissez des valeurs qui distinguent : avec `dt = 1`, oublier `dt` ne change rien ; avec `dt = 2`, si. Pour `vitesses_roues`, un virage (`w` non nul) montre si les roues sont inversées et si l'on prend bien la moitié de l'entraxe.

## Indice 3

Testez les limites de l'angle : partir de `theta = 3.0` et tourner de 1 rad doit donner `4.0 - 2 * pi`, pas `4.0`. Et `normaliser(math.pi)` doit valoir `math.pi`, comme `normaliser(-math.pi)`. `@pytest.mark.parametrize` vous permet de tester plusieurs angles en un seul test.

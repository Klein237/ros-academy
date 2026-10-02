## Indice 1

Comparez l'orientation que publie TF2 (`ros2 run tf2_ros tf2_echo odom base_link`, ligne « RPY (radian) ») avec le `theta` du service `get_pose`, après un virage. Quel rapport y a-t-il entre les deux ?

## Indice 2

La position est juste, seule la rotation est fausse, et l'erreur grandit avec l'angle : le problème est dans la conversion de `theta` en quaternion, `yaw_to_quaternion`.

## Indice 3

Un quaternion décrit une rotation par son **demi-angle** : pour un angle `θ` autour de `z`, `z = sin(θ/2)` et `w = cos(θ/2)`. Avec `sin(θ)` et `cos(θ)`, la rotation publiée vaut `2θ` : après un quart de tour, TF2 croit le robot tourné de 180°.

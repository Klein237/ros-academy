## Indice 1

Dans la Vue 3D, bougez les curseurs un par un. Lequel plie le bras hors du plan des autres ? L'axe de rotation d'une articulation est l'axe de son repère qui reste immobile pendant le mouvement.

## Indice 2

Cherchez où chaque segment reçoit son axe : `grep -n "axe" src/bras_description/urdf/bras.urdf.xacro`. Épaule, coude et poignet doivent tourner autour du même axe, pour que le bras se plie dans un seul plan.

## Indice 3

Le coude est déclaré avec `axe="1 0 0"` : il tourne autour de `x`, et l'avant-bras penche sur le côté. Remplacez par `axe="0 1 0"`, comme l'épaule et le poignet, recompilez et relancez.

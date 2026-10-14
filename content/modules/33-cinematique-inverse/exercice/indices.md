## Indice 1

Testez la fonction sans ROS, par la cinématique directe : `position_pince(*angles_pour(0.30, 0.10, 0.15))` doit redonner la cible. Puis comparez chaque angle à ce que vous attendez : la tourelle, le coude, l'épaule, le poignet.

## Indice 2

La tourelle (`atan2(y, x)`) et le coude (loi des cosinus) sont justes. Regardez l'épaule : elle doit viser le poignet, à la distance horizontale `u` et à la hauteur `v`, avec un angle mesuré **depuis la verticale**.

## Indice 3

`atan2(a, b)` donne l'angle entre l'axe de `b` et la direction `(b, a)`. Pour un angle mesuré depuis la verticale, il faut `atan2(u, v)` ; le code utilise `atan2(v, u)`, l'angle depuis l'horizontale. Inversez les deux arguments.

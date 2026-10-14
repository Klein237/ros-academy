## Indice 1

L'écart n'apparaît que lorsque le coude ou le poignet sont pliés. Placez l'épaule à 0,5 rad et le coude à 0,8 rad : de quel angle l'avant-bras est-il incliné par rapport à la verticale ?

## Indice 2

Le coude mesure l'angle de l'avant-bras **par rapport au bras**, pas par rapport à la verticale. Regardez les angles passés à `sin` et `cos` dans `position_pince`.

## Indice 3

Les angles doivent se cumuler : l'avant-bras penche de `q1 + q2`, la pince de `q1 + q2 + q3`. Remplacez `sin(q2)` par `sin(q1 + q2)`, `sin(q3)` par `sin(q1 + q2 + q3)`, et de même pour les cosinus.

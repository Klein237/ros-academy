## Ce qui se passait

`position_pince` utilisait `sin(q2)` et `sin(q3)` (et les cosinus) comme si chaque angle se mesurait depuis la verticale. Or chaque articulation est portée par le segment précédent : l'angle du coude se mesure par rapport au bras, celui du poignet par rapport à l'avant-bras. L'inclinaison réelle de l'avant-bras est `q1 + q2`, celle de la pince `q1 + q2 + q3`. Tant que le coude et le poignet restaient à 0, l'erreur ne se voyait pas.

## Comment le diagnostiquer

- Testez des poses où **une seule** articulation bouge, puis deux : l'erreur apparaît dès qu'une articulation porte une autre articulation pliée ;
- comparez à une référence indépendante : `tf2_echo base_link tool0`, que `robot_state_publisher` calcule depuis l'URDF.

## Comment l'éviter

- Gardez le calcul dans une fonction pure, et testez-la sur des poses dont le résultat se calcule à la main (tout à 0 ; épaule à 90° ; épaule et coude à 90°) ;
- un test qui compare la formule à TF2 sur quelques poses au hasard attrape aussi une description et une formule qui ont divergé.

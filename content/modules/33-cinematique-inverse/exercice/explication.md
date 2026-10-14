## Ce qui se passait

L'angle de l'épaule commençait par `atan2(v, u)` : l'angle de la direction du poignet mesuré depuis l'**horizontale**. Or tous les angles du bras se mesurent depuis la **verticale** (bras tendu vers le haut quand ils sont nuls). Il fallait `atan2(u, v)`, son complément à π/2. L'épaule était donc mal orientée ; le poignet, qui compense pour que la pince pointe vers le bas, héritait de l'erreur, et la pince arrivait loin de la cible. Pour certaines cibles, l'angle faux dépassait même une butée, et le nœud refusait une cible pourtant à portée.

## Comment le diagnostiquer

- Testez la cinématique inverse par la directe : `position_pince(*angles_pour(x, y, z))` doit redonner `(x, y, z)`, sans lancer ROS ;
- vérifiez un cas simple à la main : une cible juste devant l'épaule, à sa hauteur, demande une épaule proche de π/2, pas de 0 ;
- relisez chaque `atan2` en vous demandant depuis quel axe l'angle est mesuré.

## Comment l'éviter

- Écrivez les conventions en tête du module (ici : « les angles se mesurent depuis la verticale ») et respectez-les partout ;
- ajoutez un test qui tire des angles au hasard dans les butées, calcule la position par la directe, puis vérifie que l'inverse y ramène la pince.

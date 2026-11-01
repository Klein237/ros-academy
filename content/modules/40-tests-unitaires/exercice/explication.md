## Ce qui se passait

Le test du robot immobile passait sur le calcul correct, mais aussi sur les six versions buggées : avec `v = 0`, `w = 0`, aucune formule n'est vraiment utilisée. Une suite de tests ne vaut que par les bugs qu'elle attrape.

## Ce qui attrape chaque mutant

- **cos et sin inversés** : avancer tout droit face à x, la position doit changer sur x et pas sur y ;
- **dt oublié pour l'angle** : tourner sur place avec `dt = 2`, l'angle doit valoir `w * 2` ;
- **angle jamais normalisé** : dépasser `pi` en tournant, l'angle doit revenir côté négatif ;
- **-pi au lieu de pi** : `normaliser(math.pi)` doit valoir `math.pi`, la borne incluse de l'intervalle ;
- **roues inversées**, **entraxe entier** : un virage avec `v = 1`, `w = 2`, `entraxe = 0.5` donne `(0.5, 1.5)`.

## À retenir

- testez chaque paramètre avec une valeur qui le distingue ;
- testez les limites, là où se cachent les bugs ;
- un test qui ne peut pas échouer ne protège de rien : les mutants le montrent.

## Des tests qui n'attrapent rien

Le package `odometrie` calcule la pose du robot de livraison. Le calcul, dans `src/odometrie/odometrie/calcul.py`, est **correct**. Mais sa suite de tests, `src/odometrie/test/test_calcul.py`, ne contient qu'un test : le robot immobile. Elle laisserait passer presque n'importe quel bug.

```bash
cd ~/ws/40-tests-unitaires-exercice/src/odometrie
python3 -m pytest test       # 1 passed… mais que prouve-t-il ?
```

Votre mission : écrire des tests qui **passent sur le calcul correct** et qui **attrapent les bugs**. Pour le vérifier, la vérification lance vos tests sur six versions de `calcul.py` modifiées avec un bug, des « mutants » : chacune doit faire échouer au moins un de vos tests. Elle vous dit lesquelles passent encore.

Ce que doivent faire les trois fonctions :

- `integrer(pose, v, w, dt)` : x et y avancent de `v * dt` selon l'angle de départ (`cos` pour x, `sin` pour y), l'angle tourne de `w * dt` et reste dans `]-pi, pi]` ;
- `normaliser(angle)` : ramène un angle dans `]-pi, pi]`, donc `pi` reste `pi` et `-pi` devient `pi` ;
- `vitesses_roues(v, w, entraxe)` : la roue gauche va à `v - w * entraxe / 2`, la droite à `v + w * entraxe / 2`.

Seuls vos tests sont évalués : ne modifiez pas `calcul.py`. Quand c'est prêt, cliquez sur **Vérifier**.

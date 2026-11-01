## Indice 1

Le test du cours n'envoie qu'une commande lente, `0.2`, sous la limite : il ne vérifie jamais que la vitesse est bornée. Envoyez une commande trop rapide, `1.0`, et vérifiez la réponse avec `self.assertAlmostEqual`.

## Indice 2

Le test lance le limiteur avec `vitesse_max` à `0.3`, alors que la valeur par défaut du nœud est `0.5`. Une commande de `1.0` doit donc donner `0.3`, pas `0.5` : c'est ce qui prouve que le paramètre est bien lu. Écrivez les vitesses avec un point (`1.0`, pas `1`) : un paramètre ou un champ de message `float` refuse un entier.

## Indice 3

Pensez aux symétries et aux autres champs : une marche arrière trop rapide, `-1.0`, doit donner `-0.3`. Et une commande qui tourne, `envoyer(0.1, 0.8)`, doit garder `angular.z` à `0.8`. Chaque vérification peut être une méthode `test_…` de la classe `TestLimiteur`, qui réutilise `envoyer()`.

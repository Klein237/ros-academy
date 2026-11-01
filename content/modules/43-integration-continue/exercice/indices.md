## Indice 1

Regardez la clé `on` : quels événements déclenchent le workflow ? Une pull request ouverte vers `main` en fait-elle partie ? Puis regardez la première étape : sur une machine neuve, où se trouve le code du dépôt ?

## Indice 2

Faites l'expérience vous-même : cassez un test (un `assert False` dans `src/odometrie/test/`), lancez `colcon test`, puis `echo $?` pour voir son code de sortie. Que vaut-il ? Une étape GitHub Actions échoue seulement si une commande renvoie un code non nul.

## Indice 3

Il manque une ligne à la clé `on` (`pull_request:`), une étape au début des `steps` (`- uses: actions/checkout@v4`), et une commande après `colcon test`, qui lit les résultats des tests et renvoie une erreur si l'un a échoué. N'oubliez pas de retirer votre test cassé.

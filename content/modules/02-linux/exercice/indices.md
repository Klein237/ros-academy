## Indice 1
Regardez les droits du fichier avec `ls -l demarrer_robot.sh` : la première colonne indique qui peut le lire (`r`), l'écrire (`w`) et l'exécuter (`x`). Pour lancer un script avec `./`, il faut le droit `x`.

## Indice 2
`chmod +x demarrer_robot.sh` ajoute le droit d'exécution. Relancez le script : un nouveau message apparaît. Il dit quel fichier manque, et à partir de quoi le créer (`ls config`).

## Indice 3
Copiez l'exemple sous le nom attendu, `cp config/robot.env.exemple config/robot.env`, puis remplacez `a-changer` par `livreur-01` dans `config/robot.env` : avec l'éditeur du lab, ou en une commande, `sed -i 's/a-changer/livreur-01/' config/robot.env`. Relancez `./demarrer_robot.sh`.

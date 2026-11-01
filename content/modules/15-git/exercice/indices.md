## Indice 1

Commencez par l'historique : `git log --oneline` liste les commits, du plus récent au plus ancien. Lequel pourrait toucher au topic ? `git show <identifiant>` montre les lignes qu'il a changées.

## Indice 2

Le commit « Harmonise le nom des topics » a remplacé `bavardage` par `bavardages`. Créez la branche avant de corriger : `git switch -c correction`. Deux façons de corriger : modifier `TOPIC` dans `talker.py` puis `git add` et `git commit`, ou annuler ce commit avec `git revert <identifiant>`.

## Indice 3

Une fois le commit fait sur `correction` : `git switch main`, puis `git merge correction`. `git status` doit dire *nothing to commit, working tree clean* et `git log --oneline` montrer toujours les quatre commits de l'équipe, plus le vôtre. Vérifiez avec `colcon build`, `source install/setup.bash` et `ros2 topic echo /bavardage`.

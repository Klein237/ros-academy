## Ce qui se passait

Le troisième commit, « Harmonise le nom des topics », a renommé la constante `TOPIC` de `bavardage` en `bavardages`. Le nœud publiait donc sur `/bavardages`, et personne n'écoutait ce topic. Le commit suivant, « Numérote les messages », était correct : il fallait annuler le premier sans perdre le second.

## Comment le retrouver

- `git log --oneline` : quatre commits, dont un seul dont le message parle de topic ;
- `git show <identifiant>` : la ligne `-TOPIC = 'bavardage'` remplacée par `+TOPIC = 'bavardages'` ;
- `ros2 topic list` pendant que le nœud tourne confirme : `/bavardages` existe, `/bavardage` non.

## Comment corriger proprement

- `git switch -c correction`, puis soit `git revert <identifiant>` (un commit qui fait l'inverse du commit fautif), soit la correction à la main suivie de `git add` et `git commit` ;
- `git switch main` et `git merge correction` ;
- jamais `git reset --hard HEAD~2` : il aurait aussi effacé la numérotation des messages, et réécrit un historique que l'équipe partage.

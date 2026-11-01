## Ce qui se passait

Le workflow avait trois défauts :

- **déclenché seulement par les push sur `main`** : une pull request n'était jamais testée, l'erreur n'apparaissait qu'après la fusion ;
- **pas d'`actions/checkout`** : sur la machine neuve de GitHub, le dossier de travail est vide ; il faut récupérer le code avant de compiler ;
- **`colcon test` seul** : il se termine avec le code 0 même quand des tests échouent. L'étape restait verte, quels que soient les tests.

## La correction

```yaml
on:
  push:
    branches: [main]
  pull_request:
```

puis `- uses: actions/checkout@v4` en première étape, et dans l'étape des tests :

```bash
colcon test
colcon test-result --verbose
```

`colcon test-result` lit les résultats enregistrés par `colcon test` et renvoie un code non nul si un test a échoué : l'étape, donc le job, devient rouge. `--verbose` affiche le détail de l'échec dans le journal.

## À retenir

- testez chaque pull request, avant la fusion ;
- une étape échoue seulement si une commande renvoie un code non nul : vérifiez ce que renvoient vos commandes ;
- cassez un test exprès pour vérifier que votre CI le voit.

## Une CI qui laisse tout passer

Le dépôt du robot de livraison contient le package `odometrie` et ses tests, et un workflow d'intégration continue : `.github/workflows/ci.yml`. L'équipe le croit fiable, parce qu'il est toujours vert. Mais vendredi, une modification qui cassait un test a été fusionnée, et la CI n'a rien signalé.

```bash
cd ~/ws/43-integration-continue-exercice
cat .github/workflows/ci.yml
```

Votre mission : corriger ce workflow pour qu'il fasse vraiment son travail. Il doit :

- se déclencher à chaque `push` sur `main` **et** à chaque **pull request** ;
- **récupérer le code** du dépôt avant de compiler ;
- réussir sur le code actuel, dont tous les tests passent ;
- **échouer** dès qu'un test du package échoue.

La vérification lit votre workflow, puis exécute ses étapes `run`, dans l'ordre, avec `bash -e`, comme GitHub Actions : une fois sur le code actuel, une fois avec un test cassé exprès ajouté au package. Les étapes qui installent des dépendances (`apt-get`, `rosdep`) sont sautées, car le lab n'a pas Internet et tout y est déjà installé. Quand c'est prêt, cliquez sur **Vérifier**.

## La supervision n'affiche rien

Sur l'ordinateur du robot, l'équipe lance le robot et sa supervision :

```text
$ docker compose up
[+] Running 2/2
 ✔ Container livraison-robot-1        Started
 ✔ Container livraison-supervision-1  Started
robot-1  | [etat-1] [INFO] [etat]: Robot de livraison prêt : livreur-01
```

Le robot démarre, mais la supervision, qui devrait afficher son état chaque seconde, reste muette. Pourtant, les deux services utilisent la même image, sont tous deux en `network_mode: host` et partagent la mémoire de l'hôte (`ipc: host`).

Le fichier est dans `~/ws/22-docker-compose-exercice/compose.yaml`. Trouvez pourquoi la supervision ne reçoit rien, corrigez, puis cliquez sur **Vérifier** : il simule `docker compose up` à partir de votre fichier.

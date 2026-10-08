## Ce qui se passait

Le chien de garde arrête le robot quand la dernière commande reçue date de plus de `cmd_timeout`. Mais `self.derniere_commande` était mise à jour dans `step()`, la fonction du minuteur, 20 fois par seconde, et non dans `on_commande()`, la fonction de rappel de l'abonnement. La condition `self.consigne is not None` était toujours vraie, car `consigne` est initialisée avec un `Twist()`. Résultat : pour le chien de garde, une commande venait toujours d'arriver, et `garde_node` republiait indéfiniment la dernière consigne reçue.

La date doit être celle de la **réception** de la commande :

```python
def on_commande(self, msg):
    self.consigne = msg
    self.derniere_commande = self.get_clock().now()
```

## Comment le diagnostiquer

- le journal : le message « Aucune commande depuis 0.5 s » n'apparaissait jamais, alors que « Commandes reçues » s'affichait dès le démarrage, avant toute commande ;
- `ros2 topic echo /cmd_vel --field linear.x` : la couche de sécurité publiait toujours 0.2 après l'arrêt des commandes ;
- `ros2 topic hz /cmd_vel_brut` : plus aucun message en entrée, alors que la sortie continuait.

## Comment l'éviter

- Un chien de garde se **teste** en coupant volontairement la source des commandes, en simulation puis sur banc, avant chaque essai au sol ;
- la date d'un événement se prend là où l'événement arrive : dans la fonction de rappel, pas dans une boucle ;
- `None` est une valeur initiale plus sûre qu'un message vide quand on veut savoir si quelque chose a déjà été reçu.

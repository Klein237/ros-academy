## Indice 1

Lisez le journal du lancement : le message « Aucune commande depuis 0.5 s : arrêt du robot » apparaît-il ? Et regardez ce que publie la couche de sécurité une fois les commandes arrêtées : `ros2 topic echo /cmd_vel --field linear.x`.

## Indice 2

Le chien de garde compare l'heure actuelle à `self.derniere_commande`. Cherchez à quels endroits cette date est mise à jour. Est-ce bien à la réception d'une commande ?

## Indice 3

`self.derniere_commande` est mise à jour dans `step()`, à chaque tour du minuteur (et `self.consigne` n'est jamais `None`) : pour le chien de garde, une commande vient toujours d'arriver. Elle doit être mise à jour dans `on_commande()`, et seulement là.

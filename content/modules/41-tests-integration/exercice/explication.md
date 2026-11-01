## Ce qui se passait

Le test du cours attrapait deux bugs : un topic de sortie renommé (aucune réponse sur `/cmd_vel`) et un nœud qui quitte avec une erreur (le test après l'arrêt vérifie les codes de sortie). Mais il n'envoyait qu'une commande lente : borner la vitesse, lire le paramètre ou recopier la rotation n'étaient jamais vérifiés.

## Ce qui attrape chaque mutant

- **topic renommé** : n'importe quel test actif, faute de réponse sur `/cmd_vel` ;
- **paramètre ignoré** : `envoyer(1.0, 0.0)` doit donner `0.3`, la valeur passée au lancement, et pas `0.5`, celle par défaut ;
- **marche arrière jamais bornée** : `envoyer(-1.0, 0.0)` doit donner `-0.3` ;
- **rotation perdue** : `envoyer(0.1, 0.8)` doit garder `angular.z` à `0.8` ;
- **code de sortie 1** : `assertExitCodes(proc_info)`, dans la classe `post_shutdown_test`.

## À retenir

- un test d'intégration voit ce qu'un test unitaire ne voit pas : les noms de topics, les paramètres de lancement, l'arrêt du nœud ;
- lancez le nœud avec des paramètres différents de ses valeurs par défaut, sinon un paramètre ignoré passe inaperçu ;
- vérifiez toujours les codes de sortie après l'arrêt.

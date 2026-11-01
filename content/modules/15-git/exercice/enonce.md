## Le robot ne publie plus

L'équipe du robot de livraison travaille dans un dépôt Git. Depuis les derniers commits, le nœud `talker` démarre, mais plus rien n'arrive sur `/bavardage` :

```bash
cd ~/ws/15-git-exercice
source install/setup.bash
ros2 run demo_pkg talker          # dans un terminal
ros2 topic echo /bavardage        # dans un autre : rien
```

Votre mission, comme dans une vraie équipe :

1. retrouvez dans l'historique le commit qui a cassé le robot ;
2. créez une branche `correction` et corrigez-y le problème par un **nouveau commit**, sans effacer l'historique ;
3. revenez sur `main` et fusionnez la branche `correction` ;
4. vérifiez que tout est commité (`git status`), puis cliquez sur **Vérifier**.

Attention : les autres changements de l'équipe (la fréquence de 2 Hz, la numérotation des messages) doivent être conservés.

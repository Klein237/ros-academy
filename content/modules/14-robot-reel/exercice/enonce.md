## Le robot continue sans commande

Avant le premier essai sur le vrai robot, un collègue a écrit `garde_node`, la couche de sécurité placée devant `diff_drive_node`. Les limites de vitesse et l'arrêt d'urgence fonctionnent. Mais pendant un essai en simulation, la téléopération a planté… et le robot a continué tout droit, jusqu'au mur :

```bash
ros2 launch my_pkg robot_securise.launch.py
ros2 topic pub -r 10 -t 20 /cmd_vel_brut geometry_msgs/msg/Twist "{linear: {x: 0.2}}"
# 2 s de commandes, puis plus rien… et le robot roule toujours
```

Le chien de garde devait l'arrêter une demi-seconde après la dernière commande.

Le workspace de l'exercice est `~/ws/14-robot-reel-exercice` (déjà compilé). Trouvez pourquoi le chien de garde ne se déclenche jamais, corrigez `garde_node`, puis cliquez sur **Vérifier**.

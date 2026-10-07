## Le robot reste immobile

Un collègue a écrit `diff_drive_node` pour le robot de l'équipe. Le nœud démarre sans erreur, `/odom` est bien publié… mais quand on envoie une commande de vitesse, le robot ne bouge pas :

```bash
ros2 run my_pkg diff_drive_node
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}}"
```

La position reste à `x: 0.0` et le robot ne bouge pas dans la vue 2D.

Le workspace de l'exercice est `~/ws/05-noeud-exercice` (déjà compilé). Trouvez la cause avec les outils de ROS 2, corrigez-la, puis cliquez sur **Vérifier**.

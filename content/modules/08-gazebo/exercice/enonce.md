## Le robot tourne à l'envers

Le robot simulé apparaît bien dans la salle, avance et recule normalement avec la vue 2D… mais la flèche **←** (tourner à gauche) le fait tourner **à droite**, et **→** à gauche. Pareil en ligne de commande :

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{angular: {z: 0.5}}"
# z > 0 : rotation vers la gauche (sens trigonométrique)… le robot tourne dans le sens des aiguilles d'une montre
```

La description URDF est la même qu'au module précédent, et `check_urdf` ne trouve rien à redire.

Le workspace de l'exercice est `~/ws/08-gazebo-exercice` (déjà compilé). Trouvez pourquoi le robot simulé tourne à l'envers, corrigez, puis cliquez sur **Vérifier**.

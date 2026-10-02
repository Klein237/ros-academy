## Le robot tourne à l'envers

Le robot simulé apparaît bien dans la salle et avance normalement. Dans la **vue 2D** du lab, la flèche **←** le fait tourner à gauche, comme prévu… Pourtant, dans la fenêtre de Gazebo (`gui:=true`, sur le Bureau), il tourne **à droite**. Et dans RViz2 (*Fixed Frame* `odom`), les murs vus par le laser **tournent** au lieu de rester en place.

En ligne de commande, le simulateur donne la position réelle du robot sur `/verite_terrain` :

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{angular: {z: 0.5}}"
# z > 0 : rotation vers la gauche (sens trigonométrique)
ros2 topic echo /verite_terrain --field pose.pose.orientation.z
# … la valeur diminue : le robot réel tourne dans le sens des aiguilles d'une montre
```

La description URDF est la même qu'au module précédent, et `check_urdf` ne trouve rien à redire.

Le workspace de l'exercice est `~/ws/08-gazebo-exercice` (déjà compilé). Trouvez pourquoi le robot simulé tourne à l'envers alors que son odométrie dit le contraire, corrigez, puis cliquez sur **Vérifier**.

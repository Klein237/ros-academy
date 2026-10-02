## Ce qui se passait

Dans `my_robot.gazebo.xacro`, le plugin `gazebo_ros_diff_drive` avait `<left_joint>right_wheel_joint</left_joint>` et `<right_joint>left_wheel_joint</right_joint>`. Pour tourner à gauche (`angular.z > 0`), il accélère la roue qu'il croit à droite… qui était à gauche : le robot tournait à droite. En ligne droite, les deux roues reçoivent la même vitesse, donc rien ne se voyait. L'URDF lui-même est juste : `check_urdf` ne lit pas les balises `<gazebo>`.

## Comment le diagnostiquer

- Testez séparément l'avance et la rotation : un défaut qui n'apparaît qu'en virage met en cause ce qui **distingue** les deux roues ;
- `ros2 topic echo /joint_states` pendant une rotation : la roue qui tourne le plus vite doit être, pour `z > 0`, la roue **droite** ;
- dans RViz2 (*Fixed Frame* `odom`), la flèche du robot tourne dans le mauvais sens par rapport à la commande.

## Comment l'éviter

- Gardez les mêmes noms partout (`left_wheel_joint` côté gauche, `y > 0` dans l'URDF) et relisez les plugins avec l'URDF ouvert à côté ;
- un test simple, comme cette vérification, à chaque modification de la description : une commande de rotation positive doit augmenter le cap du robot.

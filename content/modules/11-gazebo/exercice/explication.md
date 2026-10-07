## Ce qui se passait

Dans `my_robot.gazebo.xacro`, le système `DiffDrive` avait `<left_joint>right_wheel_joint</left_joint>` et `<right_joint>left_wheel_joint</right_joint>`. Pour tourner à gauche (`angular.z > 0`), il accélère la roue qu'il croit à droite… qui était à gauche : le robot tournait à droite. Son odométrie, calculée avec les mêmes roues inversées, annonçait pourtant une rotation à gauche : la vue 2D, qui lit `/odom`, était trompée. En ligne droite, les deux roues reçoivent la même vitesse, donc rien ne se voyait. L'URDF lui-même est juste : `check_urdf` ne lit pas les balises `<gazebo>`.

## Comment le diagnostiquer

- Testez séparément l'avance et la rotation : un défaut qui n'apparaît qu'en virage met en cause ce qui **distingue** les deux roues ;
- `ros2 topic echo /joint_states` pendant une rotation : la roue qui tourne le plus vite doit être, pour `z > 0`, la roue **droite** ;
- comparez `/odom` et `/verite_terrain` : l'odométrie est calculée à partir des roues **telles que DiffDrive les croit placées**, elle annonce donc une rotation à gauche pendant que le robot réel (la vérité terrain du simulateur) tourne à droite. Sur un vrai robot, pas de vérité terrain : c'est la caméra ou le laser qui trahit le défaut.

## Comment l'éviter

- Gardez les mêmes noms partout (`left_wheel_joint` côté gauche, `y > 0` dans l'URDF) et relisez les plugins avec l'URDF ouvert à côté ;
- un test simple, comme cette vérification, à chaque modification de la description : une commande de rotation positive doit augmenter le cap du robot.

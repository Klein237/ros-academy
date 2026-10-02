## Ce qui se passait

Le nœud s'abonnait au topic `cmd_vell` au lieu de `cmd_vel`. Pour ROS 2, ce sont deux topics différents : publier sur `/cmd_vel` n'a aucun effet sur un abonné à `/cmd_vell`, et **aucune erreur n'est affichée**. Un topic existe dès qu'un nœud le déclare, même mal orthographié.

## Comment le diagnostiquer

- `ros2 node info /diff_drive_node` liste les topics auxquels le nœud est abonné : `/cmd_vell` apparaît ;
- `ros2 topic info /cmd_vel` montre *Subscription count: 0* : personne n'écoute ;
- `ros2 topic list` fait apparaître le topic fantôme `/cmd_vell`.

## Comment l'éviter

- Réutilisez des noms standard (`cmd_vel`, `odom`) et définissez-les une seule fois, dans une constante ou un paramètre ;
- après chaque nouveau nœud, vérifiez le câblage avec `ros2 node info` ou `rqt_graph`.

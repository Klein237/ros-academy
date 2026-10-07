## Indice 1

Les deux nœuds tournent (`ros2 node list`). Sont-ils reliés ? `ros2 node info /patrouille_node` et `ros2 node info /diff_drive_node` : regardez le topic `/cmd_vel` des deux côtés, et ce qui est écrit après son nom.

## Indice 2

`ros2 topic list -t` affiche le type de chaque topic. Combien de types voyez-vous pour `/cmd_vel` ? `ros2 topic info -v /cmd_vel` dit quel nœud utilise lequel.

## Indice 3

La patrouille publie des `geometry_msgs/msg/TwistStamped` (une vitesse avec un en-tête, comme dans Nav2 pour Jazzy) ; le robot s'abonne à des `geometry_msgs/msg/Twist`. Deux types différents sur un même nom ne se parlent pas. Faites publier à la patrouille des `Twist`, sans en-tête : `cmd.linear.x` au lieu de `cmd.twist.linear.x`.

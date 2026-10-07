## Ce qui se passait

La patrouille publiait des `geometry_msgs/msg/TwistStamped` sur `/cmd_vel` ; le robot s'y abonne avec des `geometry_msgs/msg/Twist`. Pour ROS 2, un éditeur et un abonné ne sont reliés que si le **nom** et le **type** correspondent : ici, deux types différents se partageaient le même nom, et aucun message ne passait. Rien ne le signale, ni au lancement ni ensuite.

`TwistStamped` ajoute un en-tête (date et repère) à la vitesse. Nav2 l'utilise par défaut depuis Jazzy : un exemple repris de sa documentation publie donc des `TwistStamped`, alors que beaucoup de robots, dont le nôtre, attendent encore des `Twist`. La correction : publier des `Twist`, avec `cmd.linear.x` au lieu de `cmd.twist.linear.x`.

## Comment le diagnostiquer

Avec la méthode du cours :

1. `ros2 node list` : les deux nœuds tournent ;
2. `ros2 topic list -t` affiche `/cmd_vel [geometry_msgs/msg/Twist, geometry_msgs/msg/TwistStamped]` : deux types pour un même topic, c'est toujours une erreur ;
3. `ros2 topic info -v /cmd_vel` montre l'éditeur en `TwistStamped` et l'abonné en `Twist` ;
4. `ros2 topic echo /cmd_vel` et `ros2 topic hz /cmd_vel` refusent le topic : `Cannot echo topic '/cmd_vel', as it contains more than one type`.

## Comment l'éviter

- Avant de brancher un nœud sur un topic existant, `ros2 topic list -t` ou `ros2 interface show` pour connaître le type attendu ;
- en reprenant un exemple, vérifiez pour quelle distribution et quel robot il a été écrit ;
- quand deux conventions coexistent, un petit nœud de conversion (`TwistStamped` → `Twist`) vaut mieux que de modifier tous les clients.

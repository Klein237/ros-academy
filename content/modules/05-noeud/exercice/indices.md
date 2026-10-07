## Indice 1

Le nœud reçoit-il vraiment les messages ? Comparez ce que le nœud déclare avec ce que vous publiez : `ros2 node info /diff_drive_node`.

## Indice 2

`ros2 topic list` affiche-t-il un topic inattendu, avec un abonné mais aucun éditeur ? `ros2 topic info /cmd_vel` indique combien d'abonnés écoutent `/cmd_vel`.

## Indice 3

Le nœud s'abonne à `cmd_vell` (deux « l ») : il n'entendra jamais les messages publiés sur `cmd_vel`. Corrigez le nom dans `create_subscription`, recompilez avec `colcon build`, relancez le nœud.

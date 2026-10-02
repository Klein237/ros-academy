## Indice 1

Le nœud propose-t-il vraiment un service ? Listez les services actifs pendant qu'il tourne : `ros2 service list -t`.

## Indice 2

`ros2 node info /diff_drive_node` affiche la section *Service Servers* : comparez le nom qui y figure avec celui que vous appelez.

## Indice 3

Le service est déclaré sous le nom `getpose` au lieu de `get_pose` dans `create_service`. Corrigez le nom, recompilez avec `colcon build`, relancez le nœud et rappelez le service.

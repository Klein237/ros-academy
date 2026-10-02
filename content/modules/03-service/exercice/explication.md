## Ce qui se passait

Le serveur était déclaré avec `create_service(GetPose, 'getpose', …)`. Le client appelait `/get_pose` : pour ROS 2, ce service n'existe pas. `ros2 service call` attend alors indéfiniment qu'il apparaisse, sans erreur.

## Comment le diagnostiquer

- `ros2 service list -t` liste les services réellement proposés, avec leur type : `/getpose [my_interface/srv/GetPose]` ;
- `ros2 node info /diff_drive_node` montre les *Service Servers* du nœud ;
- un type identique sous un nom proche est un signe de faute de frappe.

## Comment l'éviter

- Partagez les noms de services entre serveur et clients (constante, paramètre, fichier de lancement) au lieu de les recopier ;
- côté client, utilisez `wait_for_service(timeout_sec=…)` et affichez une erreur claire plutôt que d'attendre sans fin.

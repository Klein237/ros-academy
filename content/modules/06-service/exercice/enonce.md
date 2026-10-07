## « waiting for service to become available… »

L'équipe navigation a besoin de la position du robot à la demande. Le service `get_pose` a été ajouté à `diff_drive_node`, le workspace compile sans erreur, le nœud démarre… mais l'appel reste bloqué :

```bash
ros2 run my_pkg diff_drive_node
ros2 service call /get_pose my_interface/srv/GetPose
# waiting for service to become available...
```

Le workspace de l'exercice est `~/ws/06-service-exercice` (déjà compilé ; pensez à `source install/setup.bash`). Diagnostiquez avec les outils de ROS 2, corrigez, puis cliquez sur **Vérifier**.

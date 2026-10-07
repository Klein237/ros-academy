## Le robot ne part pas en patrouille

Un collègue a écrit `patrouille_node`, qui fait patrouiller le robot en carré, en partant d'un exemple trouvé dans la documentation de Nav2 pour Jazzy. Le fichier launch `patrouille.launch.py` démarre le robot et la patrouille. Tout semble normal :

```bash
ros2 launch my_pkg patrouille.launch.py
# [diff_drive_node-1] [INFO] [...] [diff_drive_node]: diff_drive_node prêt : vitesse max 0.3 m/s, tolérance 0.03 m
# [patrouille_node-2] [INFO] [...] [patrouille_node]: Patrouille démarrée
# [patrouille_node-2] [INFO] [...] [patrouille_node]: Étape : tout droit
# [patrouille_node-2] [INFO] [...] [patrouille_node]: Étape : virage
```

…mais le robot ne bouge pas : `ros2 service call /get_pose my_interface/srv/GetPose` répond toujours `x=0.0, y=0.0`.

Le workspace de l'exercice est `~/ws/13-debogage-exercice` (déjà compilé). Le robot, `diff_drive_node`, est aussi piloté par la téléopération et l'action `goto` : **ne modifiez pas** ce qu'il attend. Appliquez la méthode du cours pour trouver la panne, corrigez, puis cliquez sur **Vérifier**.

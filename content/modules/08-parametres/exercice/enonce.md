## Le robot roule trop vite

Pour la journée portes ouvertes, le robot doit rouler lentement : un collègue a préparé `config/robot.yaml` (vitesse maximale `0.15` m/s, tolérance d'arrivée `0.02` m) et le fichier launch qui le charge. Le lancement se passe sans aucune erreur :

```bash
ros2 launch my_pkg robot.launch.py
# [diff_drive_node-1] [INFO] [...] [diff_drive_node]: diff_drive_node prêt : vitesse max 0.5 m/s, tolérance 0.05 m
```

…mais le robot roule toujours à `0.5` m/s.

Le workspace de l'exercice est `~/ws/08-parametres-exercice` (déjà compilé). Trouvez pourquoi les valeurs du fichier ne sont pas appliquées, corrigez, puis cliquez sur **Vérifier**.

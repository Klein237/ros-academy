## L'obstacle est au mauvais endroit

Le robot publie maintenant ses repères, et `obstacle_locator` place sur la carte l'obstacle que voit le laser, 1 m devant lui. Tant que le robot roule tout droit, la position est juste. Mais après un virage, l'obstacle apparaît **sur le côté** du robot :

```bash
ros2 action send_goal /goto my_interface/action/Goto "{target: {x: 0.0, y: 1.0}}"
ros2 topic echo --once /obstacle
# point: x: -1.15  y: 1.0   ← le robot regarde vers y croissant : on attendait (0.0, 2.15)
```

`ros2 service call /get_pose my_interface/srv/GetPose` donne pourtant la bonne orientation (`theta ≈ 1.57`).

Le workspace de l'exercice est `~/ws/07-tf2-exercice` (déjà compilé). Comparez ce que publie TF2 avec la pose du robot, corrigez, puis cliquez sur **Vérifier**.

## La pince manque le colis

La caméra publie la position du colis sur `/cible`, le nœud `cinematique_inverse` calcule les angles, et le bras bouge, pince vers le bas. Mais il ne descend pas au bon endroit : selon les cibles, la pince arrive à plus de 10 cm du colis, ou le nœud refuse une cible pourtant à portée.

```bash
cd ~/ws/33-cinematique-inverse-exercice
colcon build --symlink-install && source install/setup.bash
ros2 launch bras_description display.launch.py jsp:=false
```

Dans un deuxième terminal :

```bash
cd ~/ws/33-cinematique-inverse-exercice && source install/setup.bash
ros2 run bras_controle cinematique_inverse
```

Puis envoyez la cible et regardez où arrive la pince (Vue 3D, `tf2_echo base_link tool0`) :

```bash
ros2 topic pub --once /cible geometry_msgs/msg/PointStamped \
  "{header: {frame_id: base_link}, point: {x: 0.30, y: 0.10, z: 0.15}}"
```

Le workspace de l'exercice est `~/ws/33-cinematique-inverse-exercice`. Trouvez l'erreur dans `bras_controle/cinematique.py`, corrigez-la, puis cliquez sur **Vérifier** : la vérification publie la cible (0,30 ; 0,10 ; 0,15) et attend que `tool0` y arrive, à 1 cm près.

## La pince n'est pas là où le superviseur la voit

Le superviseur du centre de tri journalise la position de la pince publiée sur `/position_pince`. Tant que le bras est tendu ou que seule l'épaule bouge, tout va bien ; dès que le coude ou le poignet se plient, la position journalisée s'écarte de plusieurs centimètres de celle que donne TF2.

```bash
cd ~/ws/32-cinematique-directe-exercice
colcon build --symlink-install && source install/setup.bash
ros2 launch bras_description display.launch.py jsp:=false
```

Dans un deuxième terminal :

```bash
cd ~/ws/32-cinematique-directe-exercice && source install/setup.bash
ros2 run bras_controle cinematique_directe
```

Le workspace de l'exercice est `~/ws/32-cinematique-directe-exercice`. Comparez `/position_pince` et `tf2_echo base_link tool0` pour quelques poses (Vue 3D, **Publier sur /joint_states**), trouvez l'erreur dans `bras_controle/cinematique.py`, puis cliquez sur **Vérifier** : la vérification publie la pose (tourelle 0,3 rad, épaule 0,5, coude 0,8, poignet −0,4) et compare `/position_pince` au calcul de référence, à 1 cm près.

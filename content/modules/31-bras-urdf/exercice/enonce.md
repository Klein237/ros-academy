## L'avant-bras part sur le côté

Un collègue a repris la description du bras pour la rendre plus générique : la macro `segment` reçoit maintenant l'axe de l'articulation en paramètre. `check_urdf` ne signale rien, mais dans la Vue 3D, quand on plie le coude, l'avant-bras ne reste pas dans le plan du bras : il part sur le côté. Et la pince n'est plus du tout là où le calcul l'attend.

```bash
cd ~/ws/31-bras-urdf-exercice
colcon build --symlink-install && source install/setup.bash
ros2 launch bras_description display.launch.py
```

Le workspace de l'exercice est `~/ws/31-bras-urdf-exercice`. Trouvez l'articulation mal décrite, corrigez-la, puis cliquez sur **Vérifier** : la vérification publie la pose (tourelle 0,3 rad, épaule 0,5, coude 0,8, poignet −0,4) et compare la position de `tool0` sur `/tf` au calcul de référence, à 1 cm près.

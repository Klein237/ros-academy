## « Failed to build tree »

Un stagiaire a terminé la description du robot. `xacro` produit bien un fichier, mais `robot_state_publisher` ne publie aucune transformation, et la vérification de la description échoue :

```bash
cd ~/ws/10-urdf-exercice
xacro src/my_robot_description/urdf/my_robot.urdf.xacro > ~/robot.urdf
check_urdf ~/robot.urdf
# Error:   Failed to build tree: child link [...] of joint [...] not found
```

Le workspace de l'exercice est `~/ws/10-urdf-exercice`. Lisez attentivement le message de `check_urdf`, corrigez la description, puis cliquez sur **Vérifier**.

## Ce qui se passait

Dans un package `ament_python`, un exécutable n'existe que s'il est déclaré dans `entry_points` → `console_scripts` de `setup.py`. La liste était vide : `colcon build` installait le package et son code, mais aucun exécutable. `ros2 run` trouvait donc le package (*Package not found* aurait signalé un `source` oublié) mais pas d'exécutable `talker`.

## Comment le diagnostiquer

- `ros2 pkg executables demo_pkg` ne renvoie rien ;
- `ls install/demo_pkg/lib/demo_pkg/` est vide ;
- comparez les deux erreurs possibles : *Package not found* (workspace non sourcé) et *No executable found* (exécutable non déclaré).

## Comment l'éviter

- Créez vos nœuds avec `ros2 pkg create … --node-name <nom>`, qui remplit `entry_points` ;
- après chaque nouveau nœud Python : ajout dans `setup.py`, `colcon build`, `ros2 pkg executables`.

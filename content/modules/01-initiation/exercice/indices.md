## Indice 1

Que propose réellement le package ? `ros2 pkg executables demo_pkg` liste les exécutables installés.

## Indice 2

Dans un package Python, les exécutables ne sont pas déduits des fichiers `.py` : ils sont déclarés dans un des fichiers du package. Lequel est lu par `colcon build` ?

## Indice 3

Dans `setup.py`, la liste `console_scripts` de `entry_points` est vide. Ajoutez-y `'talker = demo_pkg.talker:main',`, puis `colcon build` et `source install/setup.bash`.

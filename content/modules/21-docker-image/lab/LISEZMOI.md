# Lab du module « Écrire l'image de son robot »

- `src/livraison_bringup` : le package qui démarre le robot (`ros2 launch livraison_bringup robot.launch.py`).
- `Dockerfile` et `docker/ros_entrypoint.sh` : à créer en suivant le cours (bouton « Ouvrir dans le lab »).

Le lab n'a pas Docker. Pour construire l'image, copiez ce dossier sur une machine où Docker est installé,
puis, depuis ce dossier : `docker build -t livraison:dev .`

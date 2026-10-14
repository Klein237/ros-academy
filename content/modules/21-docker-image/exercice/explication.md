## Ce qui se passait

Le package était bien compilé et copié dans l'image, dans `/ws/install`. Mais un conteneur démarre comme un terminal neuf : aucun `setup.bash` n'est chargé. Le point d'entrée chargeait ROS 2 (l'underlay) et pas le workspace du robot (l'overlay). `ros2 launch` cherchait donc `livraison_bringup` uniquement dans `/opt/ros/jazzy`, où il n'est pas.

C'est exactement l'erreur *Package not found* du module « Organiser son code », quand on oublie `source install/setup.bash` dans un terminal : dans un conteneur, c'est le point d'entrée qui doit le faire.

## Comment le diagnostiquer

- `docker run --rm -it livraison:dev bash`, puis `ros2 pkg list | grep livraison` : rien ;
- `ls /ws/install` dans ce même terminal : le package est là ;
- `cat /ros_entrypoint.sh` : un seul `source`.

## Comment l'éviter

- Un point d'entrée de robot charge toujours, dans l'ordre : ROS, puis le workspace, puis `exec "$@"` ;
- `set -e` en tête du script : si un `source` échoue (chemin faux), le conteneur s'arrête avec un message clair ;
- testez l'image comme un utilisateur : `docker run --rm livraison:dev` en intégration continue, pas seulement `docker build`.

## Indice 1

L'image contient bien le package compilé. La question est donc : au démarrage du conteneur, qu'est-ce qui dit à ROS 2 de chercher aussi dans `/ws/install` ?

## Indice 2

Au démarrage, Docker lance `ENTRYPOINT` suivi de `CMD`, dans un environnement neuf où rien n'est sourcé. Lisez `docker/ros_entrypoint.sh` : quels `setup.bash` charge-t-il avant `exec "$@"` ?

## Indice 3

Le point d'entrée ne source que ROS (`/opt/ros/$ROS_DISTRO/setup.bash`), pas le workspace. Ajoutez `source /ws/install/setup.bash` juste après, avant `exec "$@"`.

## « Package 'livraison_bringup' not found »

Un collègue a écrit l'image du robot de livraison. La construction se passe bien, mais le conteneur s'arrête aussitôt :

```text
$ docker build -t livraison:dev .
 => [build 5/5] RUN . /opt/ros/$ROS_DISTRO/setup.sh && colcon build      12.4s
 => [robot 4/4] RUN useradd --create-home robot                            0.6s
 => exporting to image                                                     0.4s
$ docker run --rm livraison:dev
Package 'livraison_bringup' not found
```

Pourtant, `colcon build` a bien compilé le package, et `/ws/install` est copié dans l'image d'exécution. Les fichiers sont dans `~/ws/21-docker-image-exercice` : `Dockerfile`, `docker/ros_entrypoint.sh` et le package dans `src/`.

Trouvez pourquoi `ros2 launch` ne trouve pas le package au démarrage du conteneur, corrigez, puis cliquez sur **Vérifier** : il simule `docker run` à partir de votre `Dockerfile`.

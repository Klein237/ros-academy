## Ce qui se passait

Le service `robot` publiait bien sur `/etat`, dans le domaine 42. Le service `supervision` écoutait dans le domaine 24 : DDS sépare complètement les domaines, les deux conteneurs ne pouvaient pas se découvrir, même sur le même réseau et avec la même mémoire partagée. Deux chiffres inversés suffisent.

## Comment le diagnostiquer

- `docker compose exec supervision env | grep ROS` puis la même commande pour `robot` : les domaines diffèrent ;
- `docker compose exec supervision ros2 topic list` : seulement `/parameter_events` et `/rosout`, aucun topic du robot ;
- `docker compose config` affiche le fichier tel que Compose le comprend, ancres et `env_file` résolus.

## Comment l'éviter

- Écrivez `ROS_DOMAIN_ID` **une seule fois** : dans l'ancre commune (`x-ros`), ou dans un `robot.env` repris par `env_file` dans chaque service ;
- gardez un service de supervision ou un test qui vérifie, après chaque `docker compose up`, qu'un topic attendu arrive bien.

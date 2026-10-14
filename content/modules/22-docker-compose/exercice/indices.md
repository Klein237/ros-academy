## Indice 1

Réseau commun, mémoire partagée : deux des trois conditions de la découverte DDS sont réunies. Quelle est la troisième ?

## Indice 2

Comparez, service par service, les variables d'environnement du fichier. `docker compose exec supervision ros2 topic list` ne montrerait que `/parameter_events` et `/rosout`.

## Indice 3

`robot` est dans le domaine 42, `supervision` dans le domaine 24 : deux domaines différents ne se voient jamais. Mettez `ROS_DOMAIN_ID=42` aux deux services (mieux : une seule fois, dans l'ancre `x-ros` ou un `env_file`).

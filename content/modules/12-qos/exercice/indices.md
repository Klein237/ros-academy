## Indice 1

Relisez le tout début du journal du lancement, avant les « Aucune mesure » : un des deux nœuds a dit quelque chose une seule fois, au moment où il a découvert l'autre.

## Indice 2

`ros2 topic info -v /battery_state` affiche la QoS de l'éditeur et celle de l'abonné. Comparez leurs lignes `Reliability`. Si `ros2 topic echo` reçoit les mesures, c'est qu'il choisit une QoS compatible avec l'éditeur.

## Indice 3

Le pilote publie avec `qos_profile_sensor_data` (`BEST_EFFORT`) ; le superviseur s'abonne avec `10`, c'est-à-dire en `RELIABLE`. Un abonné ne peut pas exiger plus que ce que l'éditeur offre : abonnez-vous avec le même profil que le pilote.

## Ce qui se passait

Le pilote publie l'état de la batterie avec `qos_profile_sensor_data`, comme toute mesure de capteur : fiabilité `BEST_EFFORT`. Le superviseur s'abonnait avec `10`, le profil par défaut, donc en `RELIABLE`. L'éditeur **offre** « au mieux », l'abonné **demande** « tout, garanti » : la demande dépasse l'offre, DDS ne relie pas les deux, et **aucun message** ne passe. Les deux nœuds l'ont signalé une seule fois, au démarrage :

```text
[superviseur_node]: New publisher discovered on topic '/battery_state', offering incompatible QoS.
No messages will be received from it. Last incompatible policy: RELIABILITY
```

Dans le superviseur, on s'abonne avec le même profil que le pilote :

```python
from rclpy.qos import qos_profile_sensor_data
...
self.create_subscription(BatteryState, 'battery_state', self.on_battery, qos_profile_sensor_data)
```

## Comment le diagnostiquer

- l'avertissement `offering incompatible QoS` (ou `requesting incompatible QoS` côté éditeur), qui nomme la politique en cause ;
- `ros2 topic info -v /battery_state` : la ligne `Reliability` de l'éditeur et celle de l'abonné ;
- `ros2 topic echo` choisit une QoS compatible : s'il reçoit les messages et pas votre nœud, regardez la QoS de votre abonné.

## Comment l'éviter

- Abonnez-vous à un capteur avec `qos_profile_sensor_data` : un abonné `BEST_EFFORT` reçoit les éditeurs fiables comme les autres ;
- de façon générale, un abonné demande le minimum dont il a besoin ;
- avant d'intégrer le pilote d'un fabricant, `ros2 topic info -v` dit quelle QoS il offre.

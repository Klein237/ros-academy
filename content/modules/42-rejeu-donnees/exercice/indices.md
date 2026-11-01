## Indice 1

Rejouez l'enregistrement lentement (`--rate 0.2`) et regardez les distances des scans qui déclenchent un arrêt : `ros2 topic echo /scan --field ranges`. Quelle valeur, plus petite que le seuil de 0,5 m, revient alors qu'aucun obstacle n'est là ?

## Indice 2

La définition du message (`ros2 interface show sensor_msgs/msg/LaserScan`) précise que les distances inférieures à `range_min` ou supérieures à `range_max` doivent être ignorées. Le lidar du robot renvoie `0.0` quand le laser ne revient pas, et `inf` quand rien n'est à portée. `obstacle_proche()` reçoit ces deux bornes : `distance_min` et `distance_max`.

## Indice 3

Pour le test, parcourez les scans avec `enumerate(lire_scans(BAG))` : le scan numéro `i` est à `i / 10` secondes, et la personne traverse pour `40 <= i < 60`. Comparez `obstacle_proche(scan.ranges, scan.range_min, scan.range_max, 0.5)` à ce que vous attendez. Lancez-le avant de corriger : il doit échouer. Et pensez au scan où aucune mesure n'est valide.

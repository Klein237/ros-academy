## Indice 1

Comparez ce que le nœud a vraiment reçu avec le fichier : `ros2 param get /diff_drive_node max_linear_speed`. Le fichier est-il trouvé ? (Le lancement échouerait sinon.) Est-il lu ?

## Indice 2

Un fichier de paramètres ne s'applique pas à « tout le monde » : chaque bloc vise un nœud précis. Quel nœud vise ce fichier, et comment s'appelle le nœud lancé ?

## Indice 3

La clé de premier niveau du YAML doit être le nom exact du nœud, `diff_drive_node` (ou `/**` pour tous les nœuds). Avec `diff_drive:`, le bloc vise un nœud qui n'existe pas et ROS l'ignore sans rien dire.

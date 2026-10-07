## Ce qui se passait

Le fichier `config/robot.yaml` commençait par `diff_drive:` alors que le nœud s'appelle `diff_drive_node`. Dans un fichier de paramètres, la clé de premier niveau désigne le **nœud** auquel s'appliquent les valeurs : ce bloc visait un nœud `/diff_drive` qui n'existe pas. ROS n'en dit rien (le même fichier peut servir à plusieurs nœuds, dont certains ne sont pas lancés) : `diff_drive_node` démarrait avec ses valeurs par défaut, `0.5` m/s.

## Comment le diagnostiquer

- `ros2 param get /diff_drive_node max_linear_speed` : la valeur réelle, à comparer au fichier ;
- `ros2 param dump /diff_drive_node` produit un YAML au bon format : comparez sa première ligne à celle de votre fichier ;
- le message de démarrage du nœud, qui affiche ses réglages, aide beaucoup : prenez l'habitude de l'écrire.

## Comment l'éviter

- Générez le fichier avec `ros2 param dump` plutôt que de l'écrire à la main ;
- quand le fichier vise plusieurs nœuds d'un même launch, `/**:` évite de répéter les noms (et de les écrire mal) ;
- un test qui lance le fichier launch et vérifie une valeur avec `ros2 param get` attrape cette erreur avant la démonstration.

## Ce qui se passait

Le joint `chassis_joint` déclarait `<child link="chasis"/>`. Aucun link ne porte ce nom : l'URDF reste un XML valide (Xacro ne vérifie pas la cohérence), mais l'arbre cinématique ne peut pas être construit. Le link `chassis` se retrouve sans parent, ce qui donne **deux racines**, et `check_urdf` comme `robot_state_publisher` refusent la description.

## Comment le diagnostiquer

- `check_urdf` après chaque modification : il nomme le link ou le joint en cause ;
- la règle à vérifier : un URDF est un **arbre**, avec une seule racine (`base_link`), et chaque `child` d'un joint est un link déclaré ;
- `tf2_echo base_link chassis` reste muet quand la chaîne de repères est rompue.

## Comment l'éviter

- Factorisez les noms répétés avec Xacro : une macro qui reçoit le nom du link et l'utilise pour le link et son joint ne peut pas se tromper d'orthographe ;
- ajoutez `xacro … | check_urdf` aux tests automatiques du package.

## Indice 1

`check_urdf` construit un arbre : chaque joint relie un link *parent* à un link *child* qui doivent exister. Que dit exactement le message d'erreur ?

## Indice 2

Listez les links et les joints déclarés : `grep -n "link name\|child link\|parent link" src/my_robot_description/urdf/my_robot.urdf.xacro`. Chaque `child link="…"` doit correspondre à un `<link name="…">`.

## Indice 3

Le joint `chassis_joint` a pour enfant `chasis` (un seul « s ») alors que le link s'appelle `chassis`. Corrigez le nom dans la balise `<child>`, régénérez l'URDF avec `xacro` et relancez `check_urdf`.

## Indice 1

Le robot avance et recule correctement : les deux roues tournent. Seul le sens de rotation est inversé — et l'odométrie (`/odom`, celle de la vue 2D) ne s'en aperçoit pas. Quel élément décide quelle roue doit tourner plus vite pour un virage à gauche, **et** calcule l'odométrie à partir des roues ?

## Indice 2

C'est le système `DiffDrive` de Gazebo, dans `my_robot.gazebo.xacro`. Pour tourner à gauche, il fait tourner la roue **droite** plus vite que la gauche. Comment sait-il laquelle est la droite ?

## Indice 3

Les balises `<left_joint>` et `<right_joint>` sont inversées : `left_joint` doit nommer `left_wheel_joint` et `right_joint` `right_wheel_joint`. En ligne droite les deux roues reçoivent la même vitesse, d'où un défaut invisible tant que le robot ne tourne pas. Et comme DiffDrive calcule l'odométrie avec la même erreur, `/odom` reste d'accord avec la commande.

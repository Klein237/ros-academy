## Ce qui se passait

La macro `segment` reçoit l'axe de l'articulation en paramètre, et le coude était déclaré avec `axe="1 0 0"`. L'épaule et le poignet tournent autour de `y`, le coude autour de `x` : au lieu de plier le bras vers l'avant, le coude le faisait pencher sur le côté. La description reste un arbre valide, donc `check_urdf` et `robot_state_publisher` l'acceptent sans rien dire ; seule la géométrie est fausse, et la pince arrive à plus de 30 cm de la position attendue.

## Comment le diagnostiquer

- Dans la Vue 3D, bougez chaque articulation seule : un axe faux se voit tout de suite ;
- l'axe de rotation est l'axe du repère de l'enfant que le mouvement laisse immobile ;
- pour une pose connue, comparez `tf2_echo base_link tool0` à un calcul fait à la main : la tourelle à 0, `y` doit rester nul.

## Comment l'éviter

- Ne paramétrez que ce qui varie vraiment : les trois segments ont le même axe, il n'a rien à faire dans les paramètres de la macro ;
- ajoutez aux tests du package une pose de référence et la position de `tool0` attendue, comme le fait la vérification de cet exercice.

## Un test d'intégration qui laisse passer des bugs

Le package `limiteur` protège les moteurs du robot de livraison : il reçoit les commandes sur `/cmd_vel_brut` et publie sur `/cmd_vel` une commande dont la vitesse linéaire est bornée par le paramètre `vitesse_max`. Le nœud, dans `src/limiteur/limiteur/noeud.py`, est **correct**. Son test d'intégration, `src/limiteur/test/test_limiteur_launch.py`, est celui du cours : il vérifie qu'une commande lente passe telle quelle et que le nœud s'arrête proprement. C'est un bon début, mais il laisse passer des bugs.

```bash
cd ~/ws/41-tests-integration-exercice
source install/setup.bash
launch_test src/limiteur/test/test_limiteur_launch.py    # 2 tests réussis… lesquels de ces bugs verraient-ils ?
```

Votre mission : compléter ce test pour qu'il **passe sur le nœud correct** et qu'il **attrape les bugs**. La vérification lance vos tests sur cinq versions buggées du nœud, des « mutants » : chacune doit faire échouer au moins un de vos tests. Elle vous dit lesquelles passent encore.

Ce que doit faire le limiteur, lancé dans le test avec `vitesse_max` à `0.3` :

- publier sur `/cmd_vel` une réponse à chaque commande reçue sur `/cmd_vel_brut` ;
- borner la vitesse linéaire entre `-vitesse_max` et `+vitesse_max`, en marche avant comme en marche arrière ;
- recopier la vitesse de rotation `angular.z` sans la modifier ;
- s'arrêter proprement, avec le code de sortie 0.

Seuls vos tests sont évalués : ne modifiez pas `noeud.py`. Quand c'est prêt, cliquez sur **Vérifier**.

---
titre: Initiation à ROS 2
resume: Prendre en main un robot de livraison sans écrire de code — le démarrer, voir ses nœuds, lire sa position, lui donner des ordres — puis créer votre premier package.
duree: 1 h 30
---
# Initiation à ROS 2

> **La situation.** Vous rejoignez une équipe qui développe un petit robot de livraison à deux roues. Avant d'écrire la moindre ligne de code, on vous demande de le prendre en main : le démarrer, voir quels programmes tournent, lire sa position, lui envoyer des ordres, puis préparer votre propre espace de travail pour la suite.

**Dans ce module, vous allez :**

- démarrer le robot simulé et l'observer avec les outils en ligne de commande de ROS 2 ;
- comprendre les quatre façons dont les programmes d'un robot se parlent : **nœuds**, **topics**, **services** et **actions** ;
- créer, compiler et lancer votre premier **package** dans un **workspace**.

Nouveau sur ROS ? Lisez d'abord l'introduction [Découvrir ROS 2](/decouvrir/) : 20 minutes sur l'histoire de ROS, ses usages et les liens utiles.

## 1. Démarrer le robot

Votre lab est un vrai Ubuntu 24.04 avec **ROS 2 Jazzy**, dans votre navigateur : rien à installer. Chaque terminal charge ROS automatiquement — vérifiez-le :

```bash
echo $ROS_DISTRO
```

La réponse `jazzy` confirme que ROS est prêt. Démarrez maintenant le robot de livraison simulé :

```bash
academy-diffbot
```

Ouvrez la **vue 2D** du lab : le robot y apparaît, immobile. Ce terminal est désormais occupé par le robot ; pour la suite, ouvrez un deuxième terminal avec le bouton **+**.

## 2. Les nœuds : qui tourne dans le robot ?

Un robot n'est pas un seul gros programme, mais un ensemble de petits programmes qui coopèrent : les **nœuds**. Chacun réalise une tâche unique — lire un capteur, commander les moteurs, calculer la position… Un nœud appartient toujours à un package et se lance avec `ros2 run <package> <exécutable>`.

Commandes de base :

- `ros2 node list` : affiche les nœuds actifs ;
- `ros2 node info /nom_du_nœud` : affiche ce que le nœud publie, écoute, et les services et actions qu'il propose.

**Atelier :** dans le deuxième terminal, inspectez le robot :

```bash
ros2 node list
ros2 node info /academy_diffbot
```

`/academy_diffbot` écoute `/cmd_vel` (les ordres de vitesse) et publie `/odom` (sa position) : ce sont des **topics**.

## 3. Les topics : lire la position, envoyer un ordre

Les **topics** transportent des flux de messages, de manière **asynchrone** : des éditeurs (*publishers*) publient, des abonnés (*subscribers*) reçoivent, sans s'attendre. C'est le moyen idéal pour un capteur qui envoie une mesure 50 fois par seconde. Un topic peut avoir plusieurs éditeurs et abonnés ; on privilégie un seul éditeur par topic.

Commandes utiles :

- `ros2 topic list -t` : liste les topics actifs avec leur type de message ;
- `ros2 topic echo <topic> <type>` : affiche les messages en direct ;
- `ros2 topic info <topic>` : nombre d'éditeurs et d'abonnés, type de message ;
- `ros2 topic hz <topic>` : fréquence des messages ;
- `ros2 topic pub <topic> <type> 'données'` : publie un message.

**Atelier :** lisez la position du robot, puis donnez-lui un ordre de vitesse.

```bash
ros2 topic list -t
ros2 topic echo /odom nav_msgs/msg/Odometry --once
ros2 topic hz /odom
```

Arrêtez `hz` avec **Ctrl+C**, puis faites avancer le robot en tournant :

```bash
ros2 topic info /cmd_vel
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.4}}"
```

Le robot décrit un cercle dans la **vue 2D**. Arrêtez la publication avec **Ctrl+C** : par sécurité, le robot s'arrête de lui-même au bout d'une demi-seconde sans ordre. Les flèches de la vue 2D publient elles aussi sur `/cmd_vel` : c'est une télécommande.

## 4. Les services : poser une question

Un **service** fonctionne par **requête / réponse** : un client pose une question, le serveur répond, une seule fois. Contrairement à un topic, rien ne circule tant que personne ne demande. C'est le bon outil pour « quelle est ta position maintenant ? » ou « recalibre ce capteur » — dans le module 3, vous écrirez justement un service `get_pose` pour le robot.

Chaque service a un type, composé d'une partie requête et d'une partie réponse.

Commandes utiles :

- `ros2 service list -t` : liste les services actifs avec leurs types ;
- `ros2 interface show <type>` : affiche la structure de la requête et de la réponse ;
- `ros2 service call <service> <type> 'données_de_requête'` : envoie une requête et affiche la réponse.

**Atelier :** un serveur d'exemple additionne deux entiers. Lancez-le dans un troisième terminal, puis appelez-le :

```bash
ros2 run demo_nodes_py add_two_ints_server
```

```bash
ros2 service list -t
ros2 interface show example_interfaces/srv/AddTwoInts
ros2 service call /add_two_ints example_interfaces/srv/AddTwoInts "{a: 2, b: 40}"
```

## 5. Les actions : une mission longue

Livrer un colis à l'autre bout de l'entrepôt prend du temps : on veut suivre l'avancement, et pouvoir annuler en route. C'est le rôle des **actions**. Une action comporte trois messages : un **goal** (l'objectif), des **feedbacks** successifs (l'avancement) et un **résultat** (à la fin). Le client peut annuler un goal en cours : l'action est *préemptable*. Dans le module 4, vous écrirez une action `goto` qui envoie le robot vers un point.

Commandes utiles :

- `ros2 action list -t` : liste les actions disponibles et leurs types ;
- `ros2 interface show <type>` : affiche la structure goal / résultat / feedback ;
- `ros2 action info <nom_action>` : clients et serveurs de l'action ;
- `ros2 action send_goal <nom_action> <type> 'données_goal' --feedback` : envoie un goal et affiche les feedbacks ;
- **Ctrl+C** pendant `send_goal` : annule le goal en cours.

**Atelier :** un serveur d'exemple calcule la suite de Fibonacci, un terme par seconde — une « tâche longue » idéale pour observer les feedbacks :

```bash
ros2 run action_tutorials_py fibonacci_action_server
```

```bash
ros2 action list -t
ros2 action send_goal --feedback /fibonacci action_tutorials_interfaces/action/Fibonacci "{order: 8}"
```

Chaque feedback ajoute un terme ; le résultat arrive à la fin. Relancez avec `{order: 20}` puis interrompez avec **Ctrl+C** : le goal est annulé.

## 6. Votre espace de travail : workspace et package

Vous savez observer et commander le robot ; il est temps de préparer l'endroit où vous écrirez son code.

### Le workspace

Un **workspace** est le dossier où l'on écrit, compile et installe des packages. Il contient un sous-dossier `src` pour les sources ; après compilation avec `colcon`, les dossiers `build`, `install` et `log` apparaissent.

```bash
mkdir -p ~/ws/01-initiation/src
cd ~/ws/01-initiation
```

### Le package

Un **package** est l'unité d'organisation du code : un dossier qui regroupe tout ce qu'il faut pour une fonctionnalité donnée :

- du code source (nœuds en C++ ou en Python) ;
- des fichiers de configuration (paramètres, fichiers de lancement…) ;
- ses dépendances, déclarées dans `package.xml` ;
- ses instructions de compilation, dans `CMakeLists.txt` (C++) ou `setup.py` (Python).

Commandes utiles :

- `ros2 pkg list` : liste les packages disponibles ;
- `ros2 pkg executables <nom_du_package>` : liste les exécutables fournis par un package ;
- `ros2 pkg create` : crée un package (`ament_cmake` ou `ament_python`).

Créez votre premier package Python, avec un nœud d'exemple :

```bash
cd ~/ws/01-initiation/src
ros2 pkg create mon_premier_pkg --build-type ament_python --node-name mon_noeud
```

### La compilation

On compile avec [colcon](https://colcon.readthedocs.io/), depuis la racine du workspace, puis on **source** l'*overlay* du workspace pour que ROS trouve les nouveaux packages :

```bash
cd ~/ws/01-initiation
colcon build --symlink-install
source install/setup.bash
ros2 pkg executables mon_premier_pkg
ros2 run mon_premier_pkg mon_noeud
```

Sans `source install/setup.bash`, `ros2 run` répond *Package 'mon_premier_pkg' not found* : c'est l'erreur la plus fréquente des débutants. Ce `source` est à refaire dans chaque nouveau terminal.

## 7. Pour plus tard : installer ROS 2 chez vous

Dans ce parcours, le lab suffit. Pour travailler un jour sur votre propre machine ou sur un vrai robot, l'installation se fait sous Ubuntu 24.04 par paquets Debian, en suivant la [procédure officielle](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) : mettre à jour le système et installer les dépendances (curl, locales…), ajouter le dépôt ROS 2 et sa clé GPG, puis installer l'environnement complet (avec RViz et les tutoriels) :

```bash
sudo apt install ros-jazzy-desktop
```

Après l'installation, il faut **sourcer** la configuration de ROS dans chaque nouveau terminal :

```bash
source /opt/ros/jazzy/setup.bash
```

Ajoutez cette ligne à la fin de `~/.bashrc` pour qu'elle s'exécute à chaque ouverture de terminal — c'est ce que fait votre lab. Chaque distribution correspond à une version d'Ubuntu : Humble à la 22.04, Jazzy à la 24.04.

Pour chercher un package existant, consultez [index.ros.org](https://index.ros.org/) ; pour une question technique, [Robotics Stack Exchange](https://robotics.stackexchange.com/).

## 8. À retenir

| Concept | Rôle | Dans le robot de livraison | Commande clé |
|---|---|---|---|
| Nœud | Programme qui réalise une tâche | `/academy_diffbot` | `ros2 node info` |
| Topic | Flux asynchrone de messages | `/odom` (position), `/cmd_vel` (vitesse) | `ros2 topic echo`, `ros2 topic pub` |
| Service | Requête / réponse, une fois | « quelle est ta position ? » (module 3) | `ros2 service call` |
| Action | Mission longue, avec suivi et annulation | « va à ce point » (module 4) | `ros2 action send_goal --feedback` |
| Package | Unité d'organisation du code | votre `mon_premier_pkg` | `ros2 pkg create` |
| Workspace | Dossier de travail (`src`, `build`, `install`, `log`) | `~/ws/01-initiation` | `colcon build` puis `source install/setup.bash` |

**Et maintenant ?** L'exercice vous met face à une vraie panne de package, puis le module suivant vous fait écrire le premier nœud du robot.

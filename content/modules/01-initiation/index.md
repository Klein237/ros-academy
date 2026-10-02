---
titre: Initiation à ROS 2
resume: Les ressources officielles, l'installation, et les concepts clés — workspace, package, nœud, topic, service, action — essayés en ligne de commande.
duree: 1 h 30
---
# Initiation à ROS 2

**Les objectifs :**

- présenter les ressources officielles de ROS 2 ;
- connaître les prérequis et l'installation, pour travailler plus tard sur votre propre machine ;
- définir les concepts clés : workspace, package, nœud, topic, service, action ;
- les manipuler en ligne de commande dans votre lab.

## 1. Introduction et ressources officielles

Dans ce parcours, nous utilisons la distribution **Humble** de ROS 2, compatible avec Ubuntu 22.04. Il est possible d'opter pour une distribution plus récente, à condition de disposer de la version d'Ubuntu correspondante.

Ressources officielles à connaître :

- **Documentation** : [docs.ros.org](https://docs.ros.org/en/humble/) — installation, tutoriels, API ;
- **GitHub ROS 2** : [github.com/ros2](https://github.com/ros2) — les dépôts et la structure du projet ;
- **Metrics** : [metrics.ros.org](https://metrics.ros.org/) — l'usage de ROS par la communauté ;
- **Index des packages** : [index.ros.org](https://index.ros.org/) — rechercher un package et lire sa documentation ;
- **Forum et questions** : [Open Robotics Discourse](https://discourse.ros.org/) et [Robotics Stack Exchange](https://robotics.stackexchange.com/).

## 2. Prérequis et environnement

**Compétences utiles :** la ligne de commande Linux, et des bases de Python ou de C++ (recommandées, pas obligatoires).

**Dans ce parcours, rien à installer :** votre lab est un vrai Ubuntu 22.04 avec ROS 2 Humble, dans votre navigateur. Le terminal charge ROS automatiquement.

**Chez vous**, l'installation se fait par paquets Debian en suivant la [procédure officielle](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) : mettre à jour le système et installer les dépendances (curl, locales…), ajouter le dépôt ROS 2 et sa clé GPG, puis installer l'environnement complet (avec RViz et les tutoriels) :

```bash
sudo apt install ros-humble-desktop
```

Après l'installation, il faut **sourcer** la configuration de ROS dans chaque nouveau terminal :

```bash
source /opt/ros/humble/setup.bash
```

Astuce : ajoutez cette ligne à la fin de `~/.bashrc` pour qu'elle s'exécute à chaque ouverture de terminal. Dans votre lab, c'est déjà fait — vérifiez-le :

```bash
echo $ROS_DISTRO
```

## 3. Workspace et packages

### Le workspace

Un **workspace** est un dossier où l'on modifie, construit et installe des packages : c'est notre espace de travail. Il contient un sous-dossier `src` pour les sources des packages ; après compilation avec `colcon`, les dossiers `build`, `install` et `log` apparaissent.

```bash
mkdir -p ~/ws/01-initiation/src
cd ~/ws/01-initiation
```

### Le package

Un **package** est l'unité de base d'organisation du code. C'est un dossier qui contient tout ce qu'il faut pour une fonctionnalité donnée :

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

## 4. Les nœuds

Un **nœud** est l'élément fondamental d'un système ROS 2 : il réalise une tâche unique et modulaire (publier les données d'un capteur, commander un moteur…). Un nœud est toujours contenu dans un package et se lance avec `ros2 run <package> <exécutable>`.

Commandes de base :

- `ros2 node list` : affiche les nœuds actifs ;
- `ros2 node info /nom_du_nœud` : affiche les topics publiés et souscrits, les services et les actions du nœud.

**Atelier :** lancez le robot simulé du lab dans un terminal, puis inspectez-le depuis un deuxième terminal (bouton **+**) :

```bash
academy-diffbot
```

```bash
ros2 node list
ros2 node info /academy_diffbot
```

## 5. Topics : publish / subscribe

Les **topics** permettent l'échange de messages de manière **asynchrone**. Les éditeurs (*publishers*) publient des messages et les abonnés (*subscribers*) les reçoivent. Un topic peut avoir un ou plusieurs éditeurs et abonnés ; on privilégie un seul éditeur par topic.

Commandes utiles :

- `ros2 topic list` : liste les topics actifs ;
- `ros2 topic list -t` : affiche aussi le type de message de chaque topic ;
- `ros2 topic echo <topic>` : affiche en direct les messages d'un topic ;
- `ros2 topic info <topic>` : nombre d'éditeurs et d'abonnés, type de message ;
- `ros2 topic pub <topic> <type> 'données'` : publie un message ;
- `ros2 topic hz <topic>` : fréquence des messages.

**Atelier :** `academy-diffbot` écoute `/cmd_vel` et publie sa position sur `/odom`.

```bash
ros2 topic list -t
ros2 topic info /cmd_vel
ros2 topic hz /odom
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.4}}"
```

Le robot tourne en rond dans la **vue 2D**. Arrêtez la publication avec **Ctrl+C** : le robot s'arrête de lui-même au bout d'une demi-seconde sans commande. Les flèches de la vue 2D publient elles aussi sur `/cmd_vel`.

## 6. Services : requête / réponse

Un **service** offre une communication requête-réponse. Contrairement à un topic, qui diffuse un flux continu, un service ne fournit des données que lorsqu'un client l'appelle. Le service est **synchrone** : le client envoie une requête et attend la réponse. Chaque service a un type, composé d'une partie requête et d'une partie réponse.

Commandes utiles :

- `ros2 service list` : liste les services actifs ;
- `ros2 service list -t` : avec leurs types ;
- `ros2 service type <nom_du_service>` : affiche le type d'un service ;
- `ros2 interface show <type>` : affiche la structure de la requête et de la réponse ;
- `ros2 service call <service> <type> 'données_de_requête'` : envoie une requête.

**Atelier :** lancez un serveur qui additionne deux entiers, puis appelez-le :

```bash
ros2 run demo_nodes_py add_two_ints_server
```

```bash
ros2 service list -t
ros2 interface show example_interfaces/srv/AddTwoInts
ros2 service call /add_two_ints example_interfaces/srv/AddTwoInts "{a: 2, b: 40}"
```

## 7. Actions : tâches longues et préemptables

Les **actions** sont conçues pour les tâches longues (navigation, rotation, manipulation) qui demandent un suivi et la possibilité d'interrompre l'exécution. Une action comporte trois messages : un **goal** (objectif), des **feedbacks** successifs et un **résultat**.

Les actions sont construites à partir de topics et de services ; on y accède selon un modèle client / serveur : le client envoie le goal, le serveur renvoie des feedbacks réguliers puis un résultat. On peut annuler un goal en cours : l'action est *préemptable*.

Commandes utiles :

- `ros2 action list` / `ros2 action list -t` : liste les actions disponibles et leurs types ;
- `ros2 interface show <type>` : affiche la structure goal / résultat / feedback ;
- `ros2 action info <nom_action>` : clients et serveurs de l'action ;
- `ros2 action send_goal <nom_action> <type> 'données_goal' --feedback` : envoie un goal et affiche les feedbacks ;
- **Ctrl+C** pendant `send_goal` : annule le goal en cours.

**Atelier :** un serveur qui calcule la suite de Fibonacci, un terme par seconde :

```bash
ros2 run action_tutorials_py fibonacci_action_server
```

```bash
ros2 action list -t
ros2 action send_goal --feedback /fibonacci action_tutorials_interfaces/action/Fibonacci "{order: 8}"
```

Chaque feedback ajoute un terme à la suite ; le résultat arrive à la fin. Relancez avec `{order: 20}` puis interrompez avec **Ctrl+C**.

## 8. À retenir

| Concept | Rôle | Commande clé |
|---|---|---|
| Workspace | Dossier de travail (`src`, `build`, `install`, `log`) | `colcon build` puis `source install/setup.bash` |
| Package | Unité d'organisation du code | `ros2 pkg create`, `ros2 pkg executables` |
| Nœud | Processus qui réalise une tâche | `ros2 run`, `ros2 node info` |
| Topic | Flux asynchrone de messages | `ros2 topic echo`, `ros2 topic pub` |
| Service | Requête / réponse synchrone | `ros2 service call` |
| Action | Tâche longue avec feedback et annulation | `ros2 action send_goal --feedback` |

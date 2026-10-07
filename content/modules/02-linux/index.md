---
titre: Linux pour la robotique
resume: Les commandes de terminal que vous utiliserez dans tout le parcours — se déplacer, manipuler des fichiers, chercher, droits d'exécution, variables d'environnement, source et processus.
duree: 1 h 15
---
# Linux pour la robotique

> **La situation.** L'ordinateur embarqué du robot de livraison tourne sous Ubuntu, sans écran : on s'y connecte, on lance ses programmes et on lit ses journaux depuis un **terminal**. Avant de toucher à ROS 2, vous allez prendre l'habitude de ce terminal, avec les commandes qui reviendront à chaque module.

**Dans ce module, vous allez :**

- vous repérer dans l'arborescence de Linux et y manipuler des fichiers ;
- chercher dans des fichiers et enchaîner des commandes ;
- comprendre les droits d'un fichier et lancer un script ;
- comprendre les variables d'environnement et la commande `source`, au cœur de ROS 2 ;
- lancer, suivre et arrêter des programmes.

Les commandes de ce module s'essaient dans le lab : ouvrez-le à côté du cours, chaque bloc a un bouton « Lancer dans le lab ».

## L'essentiel en théorie

- **Linux** est le système d'exploitation de la plupart des robots ; ROS 2 Jazzy vise **Ubuntu 24.04**.
- Le **terminal** fait tourner un **shell** (ici `bash`), qui lit vos commandes : `programme options arguments`.
- Tout est rangé dans **un seul arbre** de dossiers qui part de `/`. Votre dossier personnel est `~`.
- Chaque fichier a des **droits** : lire (`r`), écrire (`w`), exécuter (`x`). Un script ne se lance avec `./` que s'il a le droit `x`.
- Les **variables d'environnement** (`PATH`, `ROS_DISTRO`…) configurent les programmes. `source` exécute un fichier **dans le shell courant**, pour y définir des variables : c'est ainsi qu'on « charge » ROS 2.
- Un programme lancé **occupe son terminal** jusqu'à ce qu'il s'arrête ; **Ctrl+C** l'interrompt. Un robot, c'est plusieurs programmes à la fois : plusieurs terminaux.

## 1. Linux, Ubuntu et le terminal

**Linux** est un système d'exploitation libre, comme Windows ou macOS. On le trouve dans les serveurs, les téléphones Android et la grande majorité des robots : il est gratuit, léger, modifiable, et fonctionne sans écran. **Ubuntu** est une distribution de Linux, c'est-à-dire Linux accompagné d'un ensemble cohérent de logiciels. Chaque version de ROS 2 vise une version d'Ubuntu : Jazzy, celle du parcours, vise **Ubuntu 24.04**, comme votre lab.

Le **terminal** est une fenêtre où l'on tape des commandes ; le programme qui les lit et les exécute s'appelle le **shell** (ici `bash`). Devant le curseur, l'**invite** rappelle où vous êtes :

```text
etudiant@lab:~/ws$
```

Elle se lit : l'utilisateur `etudiant`, sur la machine `lab`, dans le dossier `~/ws`. Le `$` attend votre commande.

Une commande s'écrit toujours `programme options arguments`, séparés par des espaces :

```bash
ls -l ~/ws
```

`ls` est le programme (lister), `-l` une option (format long), `~/ws` l'argument (quoi lister). Pour connaître les options d'une commande : `ls --help`, ou son manuel complet, `man ls` (on en sort avec **q**).

Deux réflexes font gagner un temps considérable :

- **Tab** complète le nom d'une commande ou d'un fichier ; deux fois **Tab** montre les possibilités ;
- **↑** et **↓** reprennent les commandes précédentes.

## 2. Se repérer dans l'arborescence

Linux range tout dans un **arbre unique** qui part de la **racine**, `/` :

| Dossier | Contenu |
|---|---|
| `/` | la racine de tout le système |
| `/home/etudiant` | votre dossier personnel, abrégé `~` |
| `/opt/ros/jazzy` | ROS 2 Jazzy, installé sur la machine |
| `/usr/bin` | les programmes du système (`ls`, `bash`, `python3`…) |
| `/tmp` | les fichiers temporaires, effacés au redémarrage |

Trois commandes pour se déplacer :

- `pwd` (*print working directory*) : où suis-je ?
- `ls` : qu'y a-t-il ici ? `ls -la` montre aussi les fichiers cachés (ceux dont le nom commence par un point) ;
- `cd dossier` : aller dans un dossier. `cd ..` remonte d'un niveau, `cd` seul ramène dans `~`, `cd -` revient au dossier précédent.

Un **chemin** désigne un fichier ou un dossier :

- **absolu** s'il part de la racine : `/home/etudiant/ws/02-linux` ;
- **relatif** s'il part du dossier courant : `journaux/robot.log`. Dans un chemin, `.` est le dossier courant et `..` le dossier parent.

**Atelier :** explorez le dossier d'entraînement du module.

```bash
cd ~/ws/02-linux
pwd
ls
ls -la entrepot
cd entrepot
cat plan.txt
cd ..
```

## 3. Fichiers et dossiers

| Commande | Effet |
|---|---|
| `mkdir -p a/b/c` | crée un dossier, et ses parents si besoin (`-p`) |
| `touch notes.txt` | crée un fichier vide (ou met sa date à jour) |
| `cp source destination` | copie un fichier ; `cp -r` copie un dossier entier |
| `mv source destination` | déplace ou renomme |
| `rm fichier` | supprime ; `rm -r dossier` supprime un dossier et tout son contenu |
| `cat fichier` | affiche un fichier en entier |
| `less fichier` | affiche un long fichier page par page (**q** pour sortir) |
| `head -n 5 fichier`, `tail -n 5 fichier` | les 5 premières ou dernières lignes |

**Attention :** `rm` ne passe pas par une corbeille. Ce qui est supprimé est perdu ; relisez toujours une commande `rm -r` avant de valider.

Pour modifier un fichier, le lab a son **éditeur** (panneau du haut) : ouvrez un fichier depuis l'arborescence, modifiez, **Ctrl+S**. Sur un vrai robot, sans écran, on utilise un éditeur dans le terminal : `nano fichier` (**Ctrl+O** pour enregistrer, **Ctrl+X** pour quitter).

**Atelier :** préparez une tournée de livraison.

```bash
cd ~/ws/02-linux
mkdir -p tournees/lundi
cp entrepot/livraisons.csv tournees/lundi/
mv tournees/lundi/livraisons.csv tournees/lundi/tournee.csv
ls -l tournees/lundi
head -n 3 tournees/lundi/tournee.csv
```

## 4. Chercher et enchaîner

`grep` cherche un texte dans des fichiers et affiche les lignes qui le contiennent :

```bash
cd ~/ws/02-linux
grep ERREUR journaux/robot.log
grep -c INFO journaux/robot.log
grep -rn "rayon-A3" .
```

`-c` compte les lignes, `-r` cherche dans tout un dossier, `-n` affiche les numéros de ligne. `find` cherche des fichiers par leur nom : `find . -name "*.csv"`.

La force du terminal est d'**enchaîner** les commandes :

- le **tube** `|` envoie la sortie d'une commande à l'entrée de la suivante ;
- `>` écrit la sortie dans un fichier (en l'écrasant), `>>` l'ajoute à la fin ;
- `2>&1` regroupe les messages d'erreur avec la sortie normale.

```bash
grep ERREUR journaux/robot.log | wc -l
grep WARN journaux/robot.log > alertes.txt
cat alertes.txt
```

Vous utiliserez souvent ce tube avec ROS 2, par exemple `ros2 topic list | grep cmd` pour retrouver un topic parmi des dizaines.

## 5. Droits et scripts

Chaque fichier appartient à un **propriétaire** et à un **groupe**, et porte des droits pour trois catégories : le propriétaire, le groupe, les autres. `ls -l` les affiche en tête de ligne :

```text
-rwxr-xr-x  1 etudiant etudiant  212 oct.  7 08:00 demarrer.sh
```

Après le premier caractère (`-` pour un fichier, `d` pour un dossier), trois groupes de trois lettres : `rwx` pour le propriétaire, `r-x` pour le groupe, `r-x` pour les autres. `r` = lire, `w` = écrire, `x` = exécuter (pour un dossier : y entrer).

Un **script** est un fichier texte qui contient des commandes. Sa première ligne, le *shebang*, dit quel programme doit l'interpréter : `#!/usr/bin/env bash` pour un script shell, `#!/usr/bin/env python3` pour Python. Pour le lancer avec `./script.sh`, il faut le droit d'exécution :

```bash
cd ~/ws/02-linux/scripts
ls -l bonjour.sh
chmod +x bonjour.sh
ls -l bonjour.sh
./bonjour.sh
```

Le `./` dit « le fichier `bonjour.sh` d'ici » : par sécurité, le shell ne cherche pas les programmes dans le dossier courant. Sans le droit `x`, il répond `Permission denied` ; `bash bonjour.sh` lance quand même le script, en demandant explicitement à `bash` de le lire.

Sur un vrai robot, certaines commandes d'administration (installer un logiciel, configurer le réseau) demandent les droits de l'administrateur, `root`, avec `sudo` devant la commande. Dans le lab, tout est déjà installé et `sudo` n'existe pas.

## 6. Variables d'environnement et `source`

Le shell garde des **variables d'environnement** : des réglages, transmis à tous les programmes qu'il lance. On lit une variable avec `$` devant son nom :

```bash
echo $HOME
echo $ROS_DISTRO
echo $PATH
env | grep ROS
```

- `HOME` : votre dossier personnel ;
- `PATH` : la liste des dossiers où le shell cherche les programmes, séparés par `:`. Quand vous tapez `ros2`, le shell le trouve parce que son dossier est dans `PATH` ;
- `ROS_DISTRO`, `ROS_DOMAIN_ID`… : les réglages de ROS 2.

On définit une variable pour les programmes lancés ensuite avec `export` ; elle n'existe que dans **ce** terminal, jusqu'à sa fermeture :

```bash
export ROBOT_NOM=livreur-01
echo "Je pilote $ROBOT_NOM"
```

Reste à comprendre la commande la plus importante du parcours, **`source`**. Lancer un script (`./script.sh`) le fait tourner dans un **nouveau** shell : les variables qu'il définit disparaissent avec lui. `source fichier` exécute au contraire le fichier **dans le shell courant** : ses variables restent. C'est pourquoi ROS 2 se charge ainsi :

```bash
source /opt/ros/jazzy/setup.bash
```

Ce fichier ajoute ROS 2 à `PATH` et définit ses variables. Plus tard, après avoir compilé vos propres packages, vous ferez de même avec `source install/setup.bash`. Pour ne pas le retaper dans chaque nouveau terminal, on ajoute la ligne à `~/.bashrc`, un script que `bash` exécute à chaque ouverture : c'est ce que fait votre lab, et c'est pourquoi `echo $ROS_DISTRO` y répond déjà `jazzy`.

## 7. Lancer, suivre et arrêter des programmes

Un programme lancé dans un terminal l'**occupe** jusqu'à ce qu'il se termine : c'est le cas de tous les programmes d'un robot, qui tournent en permanence. Lancez le robot simulé :

```bash
academy-diffbot
```

Le terminal ne rend plus la main : le robot tourne. Pour l'arrêter, **Ctrl+C** dans ce terminal. Pour faire autre chose en même temps, ouvrez un **deuxième terminal** (bouton **+**) : un robot réel, c'est souvent cinq ou six terminaux ouverts côte à côte.

Quelques outils pour gérer ces **processus** (les programmes en cours d'exécution) :

| Commande | Effet |
|---|---|
| **Ctrl+C** | interrompt le programme au premier plan |
| `commande &` | lance la commande en arrière-plan : le terminal reste disponible |
| `jobs`, `fg` | liste les tâches d'arrière-plan de ce terminal, en ramène une au premier plan |
| `ps aux \| grep nom` | retrouve un processus et son numéro (PID), même lancé ailleurs |
| `kill PID` | demande à un processus de s'arrêter |

```bash
academy-diffbot &
jobs
ps aux | grep diffbot
kill %1
```

`kill %1` arrête la tâche numéro 1 de `jobs` ; avec un PID, on écrit `kill 1234`.

## 8. Installer des logiciels

Sous Ubuntu, les logiciels s'installent par **paquets**, avec `apt`, en tant qu'administrateur :

```text
sudo apt update
sudo apt install ros-jazzy-turtlesim
```

`apt update` rafraîchit la liste des paquets disponibles, `apt install` télécharge et installe un paquet avec ses dépendances. Les paquets de ROS 2 suivent tous la même convention : `ros-<distribution>-<package>`, par exemple `ros-jazzy-nav2-bringup`. Pour du code Python hors de ROS, on utilise aussi `pip`. Dans le lab, rien à installer : tout ce dont le parcours a besoin y est déjà.

## 9. À retenir

| Besoin | Commande |
|---|---|
| Où suis-je, que contient ce dossier ? | `pwd`, `ls -la` |
| Se déplacer | `cd dossier`, `cd ..`, `cd` (retour dans `~`) |
| Créer, copier, déplacer, supprimer | `mkdir -p`, `cp -r`, `mv`, `rm -r` (sans corbeille !) |
| Lire un fichier | `cat`, `less`, `head`, `tail` |
| Chercher un texte, un fichier | `grep -rn`, `find . -name` |
| Enchaîner, enregistrer une sortie | `\|`, `>`, `>>` |
| Rendre un script exécutable, le lancer | `chmod +x script.sh`, `./script.sh` |
| Lire, définir une variable | `echo $NOM`, `export NOM=valeur` |
| Charger un environnement dans ce terminal | `source fichier` (ROS 2 : `source /opt/ros/jazzy/setup.bash`) |
| Arrêter un programme | **Ctrl+C**, `kill PID` |
| Installer un logiciel (hors lab) | `sudo apt install ros-jazzy-…` |

**Et maintenant ?** L'exercice vous met face à un script de démarrage qui refuse de se lancer. Ensuite, place à ROS 2 lui-même.

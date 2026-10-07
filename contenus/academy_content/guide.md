# Guide de rédaction des formations

Une **formation** (parcours) est une suite ordonnée de **modules**. Chaque module comprend un cours avec un lab guidé, un exercice construit autour d'une vraie panne, et un QCM. Un **module de cours** (notions, définitions) n'a pas d'exercice : il est noté sur son seul QCM. Tout s'édite ici ; les étudiants ne voient une modification qu'après une **publication réussie**.

## Les fichiers d'un module

| Fichier | Rôle |
|---|---|
| `index.md` | Le cours. Commence par un en-tête `titre`, `resume`, `duree` entre deux lignes `---`. |
| `qcm.yaml` | Le QCM (1 à 20 questions, 2 à 6 choix, au moins une bonne réponse). Le formulaire « QCM » l'édite pour vous. |
| `lab/` | Facultatif. Le workspace de départ du lab guidé, copié dans `~/ws/<module>` la première fois que l'étudiant ouvre le module. Jamais écrasé ensuite. |
| `exercice/` | Facultatif : sans ce dossier, le module est un cours, noté sur son QCM. S'il existe, tous les fichiers ci-dessous sont obligatoires. |
| `exercice/enonce.md` | La situation réelle : ce que l'étudiant observe, la commande qui échoue. |
| `exercice/depart/` | Le workspace de l'exercice, **avec le bug**. |
| `exercice/setup.sh` | Installe l'exercice dans `$WS` (en général : copier `depart/` puis `colcon build`). |
| `exercice/check.sh` | Code de sortie 0 = réussi. Ce qu'il affiche est montré à l'étudiant : écrivez des messages utiles. |
| `exercice/solution/` | Les fichiers corrigés, copiés par-dessus `$WS` pendant les tests. Jamais montrés aux étudiants. |
| `exercice/indices.md` | Exactement 3 indices, chacun sous un titre `## Indice n`, du plus vague au plus explicite. |
| `exercice/explication.md` | Affichée après la réussite : la cause, comment la diagnostiquer, comment l'éviter. |
| `lab_test.sh` | Facultatif : vérifie que les nœuds du lab guidé démarrent (lancé depuis le workspace compilé). |

L'identifiant d'un module a la forme `08-parametres` : deux chiffres, un tiret, des minuscules.

## Écrire le cours

- Un bloc de code annoté d'un chemin contient **un fichier complet** du lab guidé :

  ````text
  ```python fichier=src/my_pkg/my_pkg/diff_drive_node.py
  …
  ```
  ````

  Il reçoit un bouton « Ouvrir dans le lab », qui crée le fichier dans le workspace de l'étudiant s'il n'existe pas encore. Les tests de publication compilent `lab/` complété par ces fichiers : un cours dont le code ne compile plus n'est pas publié.
- Deux blocs `python` et `cpp` qui se suivent s'affichent en onglets Python / C++.
- Les autres blocs (`bash`, `xml`…) sont des exemples : ils ne sont ni testés ni copiés.

## Les schémas

Un schéma vaut souvent un long paragraphe. Placez-le dans le dossier `images/` du module (SVG de préférence, sinon PNG, JPG ou WebP ; nom en minuscules, chiffres, `-` et `_`), puis insérez-le dans le cours :

```text
![Le robot avance à la vitesse v et tourne à ω](images/vitesses.svg)
```

Le texte entre crochets est **obligatoire** : c'est ce que lit un lecteur d'écran, et ce qui s'affiche si l'image manque. La publication refuse une image absente, une image hors du dossier `images/` ou sans description.

Les schémas des cours livrés avec la plateforme sont générés par `scripts/schemas/generer.py`, avec un style commun : les couleurs du site, `x` en rouge et `y` en vert comme dans RViz, et un thème sombre intégré à chaque SVG. Pour modifier l'un de ces schémas, changez son script, puis relancez `python3 scripts/schemas/generer.py`.

## Écrire l'exercice

Les scripts reçoivent deux variables :

- `$EXERCICE` : le dossier `exercice/` du module, copié dans le conteneur (sans `solution/` ni `explication.md`) ;
- `$WS` : le workspace de l'exercice, `~/ws/<module>-exercice`.

Conseils, tirés des modules existants :

- n'utilisez pas `set -u` dans un script qui fait `source install/setup.bash` (colcon le refuse) ;
- lancez les nœuds avec `setsid ros2 run … &` et arrêtez tout le groupe à la fin : `trap 'kill -TERM -- -$NODE' EXIT` ; sans cela, des nœuds orphelins s'accumulent dans le conteneur de l'étudiant ;
- prenez un `ROS_DOMAIN_ID` dédié (`export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))`) : la vérification ne doit pas voir les nœuds que l'étudiant a laissés tourner ;
- mettez un `timeout` sur toute commande qui peut attendre indéfiniment (`ros2 service call`, `ros2 action send_goal`, `ros2 topic echo`) ;
- le bug doit faire échouer `check.sh` **pour la bonne raison** : lisez le journal des tests, pas seulement la coche.

## Le parcours et le catalogue

La page d'un parcours (tableau de bord → parcours) règle aussi sa place dans le catalogue :

- **Statut** : « Disponible » (au moins un module, page ouverte) ou « Bientôt » (annoncé sur l'accueil et le catalogue, sans lien ni module) ;
- **Niveau** : débutant, intermédiaire ou avancé — il range le parcours dans la feuille de route ;
- **Accroche** : une phrase pour la carte du catalogue ;
- **Ordre** : plus petit = plus haut dans le catalogue ;
- **Vous saurez** et **Prérequis** : une ligne par élément, affichés sur la page du parcours ;
- pour chaque module : son **coefficient** dans la note finale, sa **partie** (les modules consécutifs d'une même partie, « Les bases » par exemple, sont regroupés sur la page du parcours) et la case **Bonus** (module suivi et noté, mais hors note finale et hors certificat).

Pour ouvrir un nouveau parcours (Nav2, SLAM…), passez son statut à « Disponible » une fois ses premiers modules ajoutés.

## Publier

« Publier le brouillon » :

1. vérifie le format de toutes les formations ;
2. pour chaque module modifié, dans un conteneur ROS sans réseau : `setup.sh`, puis `check.sh` doit **échouer** (le bug est présent), puis `solution/` est appliquée et `check.sh` doit **réussir**, puis le lab guidé doit compiler et `lab_test.sh` passer ;
3. si tout passe, met la nouvelle version en ligne.

Chaque enregistrement est une version dans l'historique ; « Restaurer » ramène le brouillon à une version antérieure sans rien effacer.

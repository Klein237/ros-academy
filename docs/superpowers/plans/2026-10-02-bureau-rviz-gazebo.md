# Bureau graphique du lab (RViz, Gazebo) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** lancer RViz2, Gazebo et les outils graphiques de ROS depuis les terminaux du lab, et voir leurs fenêtres dans le navigateur, sans rien installer chez l'étudiant.

**Spec :** « RViz / Gazebo » (hors V1 ; la vue 2D couvrait les besoins de base).

**Architecture :**

- **Image `ros-lab`** :
  - paquets `ros-humble-rviz2`, `ros-humble-gazebo-ros-pkgs` (Gazebo classic 11, `gzserver` sans interface) et `ros-humble-joint-state-publisher-gui` ;
  - TigerVNC (`Xvnc`), openbox, websockify, Mesa (rendu OpenGL logiciel llvmpipe, sans GPU).
- **`academy-bureau PORT`** : écran `:1` (Xvnc, VNC sans mot de passe mais en local seulement), openbox, puis `websockify` sur le port donné. Il nettoie un verrou laissé par un écran mort et fonctionne avec la racine en lecture seule (sockets X dans le tmpfs `/tmp`).
- **jupyter-server-proxy** : entrée `bureau`, démarrée au premier accès à `/user/<nom>/bureau/`, authentifiée comme le reste du serveur.
- **`ros.sh`** : `DISPLAY=:1`, `LIBGL_ALWAYS_SOFTWARE=1` ; les programmes des terminaux s'affichent sur le bureau.
- **Lab UI** : bouton « Bureau (RViz, Gazebo) » ; le panneau prend la place de l'éditeur, terminaux dessous. Client noVNC 1.7.0 (npm, chargé à la première ouverture) intégré au Lab UI. Les pages servies sous `/user/` sont en CSP `sandbox` et ne peuvent pas exécuter le client noVNC du serveur. Le panneau reste mis à l'échelle et à la taille du panneau, avec reconnexion automatique à délai croissant et un bouton « Reconnecter ».
- **Cours** : module 05 (URDF) et module 07 (TF2) visualisés dans RViz dans le lab, au lieu de « sur votre machine ».

## Global Constraints

- Aucun port ni flux VNC exposé hors du proxy authentifié.
- Racine du conteneur en lecture seule : tout ce que le bureau écrit va dans `/tmp` (tmpfs) ou le dossier de l'étudiant.

### Task 1 : Image

- [x] Paquets, `academy-bureau`, proxy, environnement ; test d'image : écran démarré racine en lecture seule, fenêtre RViz2 créée et vivante, `gzserver` démarre.

### Task 2 : Lab UI

- [x] `DesktopPanel` (tests unitaires : connexion à la première ouverture, reconnexion à délai croissant, échec du jeton, fermeture, « Reconnecter ») ; bouton et mise en page.
- [x] E2E : `xsetroot` dans le terminal colore l'écran affiché dans le navigateur (toute la chaîne) ; `@rviz` : RViz2 dessine une fenêtre (CI, image réelle).

### Task 3 : Cours et documentation

- [x] Modules 05 et 07 ; README.

## Résultats

- Local, avec l'image ROS locale plus les paquets du bureau (RViz et Gazebo ne s'installent pas dans cet environnement, le dépôt ROS y est bloqué) :
  - écran virtuel, OpenGL 4.5 (llvmpipe), poignée de main WebSocket ;
  - e2e du bureau réussi ; capture vérifiée avec `glxgears` ;
  - Lab UI : 106 tests unitaires ; e2e : 23 réussis.
- RViz2, `joint_state_publisher_gui` et `gzserver` dans l'image réelle : vérifiés par la CI (test d'image et e2e `@rviz`).
- Suite prévue : un module « Simuler le robot dans Gazebo » (monde, plugins diff drive et laser, visualisation dans RViz).

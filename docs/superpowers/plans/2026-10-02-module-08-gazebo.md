# Module 08 — Simuler le robot dans Gazebo — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** faire rouler le robot de la description URDF (module 05) dans un monde simulé, avec ses roues motrices et un laser, et le visualiser dans RViz2 (bureau du lab) et dans la vue 2D.

**Contenu (coef 2) :**

- Gazebo (simulation : physique, capteurs) et RViz2 (affichage) ; ce qu'un URDF doit avoir pour Gazebo (collision, inertie).
- `my_robot.gazebo.xacro` : couleurs, frottements (roulette sans frottement), `gazebo_ros_diff_drive` (`/cmd_vel` → roues, `/odom`, TF `odom → base_link`), `gazebo_ros_joint_state_publisher`, laser `ray` (sans rendu) publié sur `/scan`.
- Monde SDF autonome (salle 4 × 4 m, caisse droit devant), sans modèle à télécharger.
- `gazebo.launch.py` : `gzserver` (interface en option `gui:=true`), `robot_state_publisher` (`use_sim_time`), `spawn_entity.py`.
- **Panne** : `<left_joint>` et `<right_joint>` inversés dans le plugin ; le robot avance normalement mais tourne à l'envers.

## Global Constraints

- Gazebo tourne sans interface (pas de GPU) ; rien ne demande Internet.
- `check.sh` et `lab_test.sh` utilisent un domaine ROS et un `GAZEBO_MASTER_URI` dédiés.

### Task 1 : Cours, lab, exercice, QCM

- [x] Fichiers complets du cours ; exercice (bug, solution, indices, explication) ; `lab_test.sh` (robot apparu, caisse à 0,90 m devant le laser, TF `odom → laser`).

### Task 2 : Parcours

- [x] `parcours.yaml`, e2e (liste des modules).

## Résultats

- Local (sans Gazebo) : description valide (`xacro`, `check_urdf` : 5 links, 3 plugins, dimensions calculées depuis l'URDF), format du contenu valide, exercice installé et compilé.
- Simulation (bug détecté, solution, lab) : vérifiée par la CI (image réelle).

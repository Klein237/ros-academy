# Isolation réseau des labs — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** un étudiant ne peut plus joindre le conteneur d'un autre étudiant. Jusqu'ici, tous les labs partageaient le réseau `ros-lab-net` : leurs ports n'étaient protégés que par le jeton Jupyter.

**Spec :** durcissement de l'hébergement (« Limites connues » du README de déploiement).

**Architecture (Hub) :**

- `RosLabSpawner` (sous-classe de DockerSpawner) : avant chaque démarrage, crée le réseau `ros-lab-<nom>` (`internal`, sans Internet) et y connecte le conteneur du Hub (alias `hub`) ; après l'arrêt, déconnecte le Hub et supprime le réseau. `network_name` est calculé par étudiant, y compris pour un serveur repris après un redémarrage du Hub.
- Sous-réseaux : une plage dédiée (`LAB_SUBNETS`, par défaut `10.213.0.0/16`) découpée en /28 ; le premier /28 libre (sans recouvrement avec les réseaux existants) est pris, avec nouvel essai si un autre démarrage l'a pris entre-temps. Les plages par défaut de Docker n'auraient permis qu'une trentaine de réseaux.
- Bridges nommés `rl-<n>` : une seule règle de pare-feu de l'hôte pour tous (`iptables -I INPUT -i rl-+ -j DROP`).
- Au démarrage du Hub (conteneur recréé après un plantage) : il rejoint les réseaux des labs encore en cours et supprime les réseaux orphelins.
- Les opérations Docker passent par le thread Docker de DockerSpawner (pas d'appel bloquant dans la boucle du Hub).

## Global Constraints

- Seul le Hub rejoint le réseau d'un étudiant ; aucun autre service.
- Aucun prérequis sur l'hôte (API Docker seule).

### Task 1 : Réseaux par étudiant

- [x] `rosacademy_hub/reseau.py` (création, sous-réseau libre, nettoyage, reprise au démarrage) et `spawner.py` ; tests unitaires avec un faux Docker (recouvrements, noms partiels `u1` / `u10`, plage épuisée, réseau encore utilisé, orphelins).

### Task 2 : Déploiement

- [x] `jupyterhub_config.py`, compose (`ros-lab-net` retiré, `LAB_SUBNETS`), `.env.example`, README.

### Task 3 : Tests réels

- [x] Intégration : un étudiant n'atteint ni l'adresse ni le nom du conteneur d'un autre (témoin : le Hub l'atteint, et l'étudiant atteint le Hub) ; réseau `internal` supprimé à l'arrêt.

## Résultats

- Hub : 67 tests unitaires ; intégration : 15 tests passent en local. `test_container_is_hardened_free_plan` échoue seulement en local, car l'image `ros-lab-local` contient `sudo` ; la CI utilise `ros-lab:0.1.0`.
- E2E Lab UI : 23 réussis.
- Charge à 35 sessions :
  - 1er passage : 34/35 (une route du proxy en échec sous charge, « Failed to add … to proxy ») ;
  - 2e passage : 35/35, démarrage médian 60 s (66 s avant ce changement) ;
  - à la fin, 0 réseau restant.
- Plantage du Hub (`docker kill`) pendant un lab : au redémarrage, le Hub rejoint le réseau et le lab reste utilisable. Un arrêt normal du Hub arrête les labs (`cleanup_servers`) et supprime leurs réseaux.
- Hors de ce plan : la limite de 1 Go par volume. Le pilote `local` de Docker ne monte pas d'image disque (`o=loop` refusé) ; il faut des quotas côté hôte.

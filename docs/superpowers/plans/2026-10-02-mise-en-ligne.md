# Mise en ligne : installation, RGPD, sauvegardes — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** ce qui manque, côté développement, pour ouvrir la plateforme au public : installer un serveur en une commande, respecter les obligations RGPD, et ne pas perdre de données.

### Task 1 : Installation

- [x] `scripts/installer-serveur.sh` (Ubuntu, rejouable) :
  - questions (domaine, administrateur, SMTP, mentions légales) ;
  - Docker ;
  - pare-feu des labs (service systemd) ;
  - image ROS ;
  - dossiers à quota ;
  - `deploy/.env` (secrets aléatoires, 600) ;
  - démarrage, vérifications et e-mail de test ;
  - sauvegarde quotidienne (timer systemd).
- [x] CI : le serveur de test est installé avec ce script ; tests des fonctions et shellcheck.

### Task 2 : RGPD

- [x] Pages mentions légales et confidentialité (éditeur, hébergeur et durée des sauvegardes lus dans `.env`), liées depuis le pied de page du site et des comptes.
- [x] « Télécharger mes données » (JSON) et « Supprimer mon compte ».
  - Suppression : confirmation par l'adresse e-mail ; refus pendant un abonnement ; le Hub arrête le lab puis supprime l'utilisateur, et `RosLabSpawner.delete_forever` efface le dossier ou le volume ; cascade en base.
  - Si le Hub est injoignable, rien n'est supprimé.
- [x] Tests : Comptes (export, suppression, refus, échec du Hub, pages, client Hub), Hub (effacement sans suivre les liens), e2e (lab ouvert, fichier écrit, compte supprimé, dossier effacé, utilisateur du Hub supprimé).

### Task 3 : Sauvegardes

- [x] `scripts/sauvegarder.sh` : base (`pg_dump -Fc`, relue), formations, dossiers des étudiants, `.env`, `SHA256SUMS`, rotation, copie rsync facultative ; restauration documentée.
- [x] Test réel local (projet Compose isolé : base restaurée, fichiers relus, rotation, droits) ; CI : sauvegarde puis restauration de la base de la pile complète.

## Écarts constatés

- `iptables-persistent` désinstalle `ufw` sur Ubuntu : la règle des labs est remise par un service systemd.
- E2E de suppression : sur la machine de test, Chromium voit disparaître l'interface réseau du lab supprimé (`ERR_NETWORK_CHANGED`) ; la confirmation est envoyée par le client HTTP de Playwright (le formulaire reste vérifié dans la page).

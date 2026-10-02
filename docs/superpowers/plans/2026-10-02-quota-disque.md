# Espace disque des étudiants (1 Go) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** un étudiant ne peut pas utiliser plus de 1 Go (et 200 000 fichiers) ni remplir le disque de l'hôte par un autre chemin.

**Spec :** « 1 Go par volume étudiant » ; « Limites connues » du README de déploiement.

**Choix :** quotas de projet **XFS** avec une **limite par défaut** pour tous les projets.
- Le pilote `local` de Docker ne monte pas d'image disque (`o=loop` refusé) : pas de taille par volume.
- Les quotas ext4 demandent `quotactl` (CAP_SYS_ADMIN, et `quotactl_fd` est filtré par seccomp dans les conteneurs) pour chaque nouvel étudiant ; ext4 n'a pas de limite par défaut.
- Avec XFS, la limite par défaut est posée une fois sur l'hôte ; le Hub n'a qu'à rattacher le dossier d'un nouvel étudiant à son projet (ioctl `FS_IOC_FSSETXATTR`, permis au propriétaire) : aucun droit supplémentaire.

**Architecture :**

- `scripts/preparer-hote.sh` (une fois, rejouable) : image creuse ou partition → XFS, montée par `/etc/fstab` avec `prjquota`, limite par défaut `bhard=1g ihard=200000`, dossier en `711`.
- Hub (`disque.py`, `RosLabSpawner`) : si `LAB_HOMES_DIR` est défini, vérifie au démarrage que c'est un XFS avec `prjquota` (sinon refus de démarrer), crée `LAB_HOMES_DIR/<nom>` (squelette `/etc/skel`, propriétaire 1000), rattaché au projet `10000 + id` avec héritage, et le monte en `/home/etudiant`. Sans `LAB_HOMES_DIR` : volumes Docker comme avant (développement).
- Contenus : la vérification des exercices monte ce dossier en lecture seule (au lieu du volume).
- `deploy/docker-compose.quotas.yml` (activé par `COMPOSE_FILE` dans `.env`) ; `scripts/migrer-volumes.sh` pour un déploiement existant.
- Conteneur du lab : racine en lecture seule, `/tmp` (512 Mo) et `/var/tmp` (64 Mo) en tmpfs (comptés dans la mémoire).

### Task 1 : Hub et Contenus

- [x] `disque.py` (numéros de projet, montage vérifié, création du dossier) ; spawner ; vérification par chemin ; tests unitaires.

### Task 2 : Hôte et déploiement

- [x] Scripts de préparation et de migration ; override compose ; `.env.example` ; README.

### Task 3 : Tests réels

- [x] Intégration : racine en lecture seule et `/tmp` borné ; avec `LAB_HOMES_DIR`, `df ~` affiche 1024M, une écriture de 1,1 Go échoue, la place libérée est réutilisable.
- [x] CI : l'hôte du job d'intégration est préparé par `preparer-hote.sh` (image XFS de 6 Go) ; toute la suite (intégration, e2e, charge) tourne avec les dossiers à quota.

## Résultats

- Hub : 73 tests unitaires ; Contenus : 106.
- Local (noyau sans quotas ni XFS : la limite n'y est pas testable) : ioctl de projet vérifiés sur ext4 (drapeau `P` posé) ; intégration 14 réussis (dont la racine en lecture seule) ; e2e 23 réussis avec la racine en lecture seule.
- La limite de 1 Go elle-même est vérifiée par la CI.

# Vérification des exercices hors du conteneur de l'étudiant — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** la réussite d'un exercice n'est enregistrée que si le `check.sh` **officiel** réussit sur le workspace de l'étudiant, dans un conteneur que l'étudiant ne contrôle pas. La note de l'exercice (50 % du module) ne peut plus être obtenue en déclarant la réussite ou en modifiant `check.sh`.

**Spec :** « Déroulé d'une session de lab », point *Triche* : *check.sh tourne dans le conteneur de l'étudiant et pourrait être modifié. Acceptable en V1 ; avant des certificats payants, la vérification sera lancée depuis l'extérieur du conteneur.*

**Architecture :**

- **Contenus** (qui a déjà la socket Docker et lance les tests des modules) : route interne `POST /api/contenus/modules/<id>/verifier` (en-tête `X-Academy-Interne`), corps `{"etudiant": "u42"}`. Elle crée un conteneur `ros-lab` neuf (sans réseau, non-root, `cap_drop ALL`, 1 vCPU / 2 Go / 256 processus), y monte **en lecture seule** le volume de l'étudiant (`ros-lab-home-u42`), copie `ws/<id>-exercice` (sans `build/`, `install/`, `log/` : tout est recompilé) et les fichiers **publiés** de l'exercice (sans `solution/`, `indices.md`, `explication.md`), puis lance `check.sh` (5 min au plus). Réponse : `{ok, code, journal}`.
- Au plus `VERIFICATIONS_MAX` (4) vérifications en même temps ; au-delà, attente jusqu'à 60 s puis « serveur de vérification occupé ».
- **Comptes** : `POST /api/comptes/exercices/<id>/verification` (session, `Origin`) appelle Contenus pour le compte connecté (une vérification à la fois par étudiant) et n'enregistre la réussite que si `ok`. La route `…/reussite` (réussite déclarée par le navigateur) **disparaît**.
- **Lab UI** : « Vérifier » enregistre les fichiers modifiés de l'éditeur, puis demande la vérification au serveur et affiche son résultat. Sans compte (lab ouvert pour un diagnostic), `check.sh` tourne dans le terminal comme avant, sans rien enregistrer.

## Global Constraints

- Le nom du volume est construit par Contenus à partir d'un nom `u<chiffres>` validé : jamais un nom arbitraire venu du réseau. Un volume absent n'est pas créé (Docker en créerait un vide) : réponse « commencez d'abord l'exercice ».
- Le workspace copié est limité à 200 Mo.
- Le `check.sh` exécuté est celui de la version **publiée** du module, jamais celui du volume de l'étudiant.

### Task 1 : Contenus

- [x] `verification.py` : script, archive des fichiers publiés, conteneur ; tests unitaires (nom refusé, volume absent, montage en lecture seule, fichiers cachés absents de l'archive, limite de concurrence) et test réel (conteneur ROS) : workspace avec le bug → échec, workspace corrigé → réussite, `check.sh` modifié par l'étudiant ignoré.
- [x] Route interne + test (secret exigé).

### Task 2 : Comptes

- [x] `POST …/verification` ; suppression de `…/reussite` ; tests (réussite seulement si Contenus dit `ok`, une vérification à la fois, erreurs).

### Task 3 : Lab UI et e2e

- [x] « Vérifier » par le serveur (fichiers enregistrés avant) ; repli local sans compte ; tests unitaires du client Comptes.
- [x] e2e : l'exercice du module Nœud réussi par la vérification serveur ; une réussite déclarée (`POST …/reussite`) ou un `check.sh` remplacé par `exit 0` ne donnent rien.

## Résultats

- Test réel (conteneur ROS, module Nœud) : workspace avec le bug → échec ; `check.sh` du volume remplacé par `exit 0` → toujours un échec ; correction (avec un faux `build/` laissé dans le volume) → réussite ; le volume n'est pas modifié. Environ 15 s par vérification.
- E2E : l'exercice du module Nœud passe par la vérification du serveur, la triche sur `check.sh` dans le lab échoue, `POST …/reussite` n'existe plus.
- Le test unitaire de ModulePanel n'existe pas (composant DOM + Monaco) : le comportement est couvert par l'e2e.

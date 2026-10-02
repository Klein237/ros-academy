# Déploiement du moteur de sessions

## Prérequis
- Un serveur Linux avec Docker et le plugin Compose (≈16 vCPU / 64 Go pour 30 à 40 sessions).
- Un nom de domaine pointant vers le serveur (ports 80 et 443 ouverts).

## Installation
1. `docker build -t ros-lab:0.1.0 images/ros-lab`
2. `cp deploy/.env.example deploy/.env` puis remplacer chaque secret par `openssl rand -hex 32`, `DOMAIN` par le domaine, et renseigner `ADMIN_EMAILS`, le SMTP et, si souhaité, GitHub / Google (voir « Comptes » ci-dessous).
3. `cd deploy && docker compose up -d --build` (construit aussi le Lab UI dans l'image Caddy : Node n'est pas nécessaire sur le serveur), puis, toujours depuis `deploy/` : `set -a; . ./.env; set +a; BASE_URL=https://$DOMAIN ../scripts/wait_for_hub.sh`

## Comptes des étudiants (service Comptes)
- **Connexion** sur `/connexion` : lien magique par e-mail (toujours disponible), GitHub et Google (affichés quand `GITHUB_CLIENT_*` / `GOOGLE_CLIENT_*` sont renseignés ; URL de retour `https://<domaine>/connexion/github/retour` et `…/google/retour`). Un compte = une adresse e-mail vérifiée : GitHub puis Google sous la même adresse ouvrent le même compte.
- **Sans SMTP** (`SMTP_HOST` vide), le lien de connexion est écrit dans `docker compose logs comptes` : pratique en développement, à ne pas laisser en production.
- **Lab** : les boutons « Ouvrir le lab » du site passent par `/compte/lab`, qui vérifie le quota du mois (formule `free` : 600 min ; `pro` : sans limite) puis émet le jeton court du Hub. Le Lab UI prévient 5 min avant la fin du quota ; à zéro, Comptes arrête le serveur et le Hub refuse tout nouveau démarrage (`COMPTES_URL`, vérifié avant chaque démarrage).
- **Progression** : QCM (2 tentatives, la meilleure est gardée), indices (−15 % chacun) et réussite des exercices sont enregistrés dans Postgres (volume `postgres-data`) ; notes sur `/compte/resultats`. Les corrections, indices et explications ne sortent de Contenus que par Comptes : Caddy bloque ces routes internes et Contenus exige un secret dérivé de `JWT_SECRET`.
- **Serveur plein** : le Lab UI prend un ticket dans la file de Comptes et affiche la position ; le démarrage est retenté quand le tour arrive.
- **Administration** : une adresse de `ADMIN_EMAILS` connectée ouvre l'éditeur depuis « Mon compte » (`/compte/admin`).
- Changer la formule d'un étudiant : `docker compose exec postgres psql -U comptes -d comptes -c "UPDATE users SET formule='pro' WHERE email='…'"`.
- Sauvegarde : `docker compose exec postgres pg_dump -U comptes comptes > comptes.sql`.

## Tester un accès étudiant sans compte (diagnostic)
Le parcours normal passe par `/connexion`. Pour tester le Hub seul, un jeton peut être émis à la main :
```bash
set -a; . deploy/.env; set +a
pip install PyJWT==2.9.0
TOKEN=$(python scripts/mint_token.py --sub essai --plan free)
echo "https://$DOMAIN/hub/jwt_login?token=$TOKEN"
```
Ouvrir le lien : connexion, redirection vers le Lab UI (`/lab/`), écran d'attente pendant le démarrage du conteneur, puis terminal, éditeur et vue 2D. Pour ouvrir directement un fichier ou un dossier (bouton « Ouvrir dans le lab » du site), ajouter `&next=` avec l'URL encodée de `/lab/?open=ws/module-02/talker.py&dossier=ws/module-02`.

Vérifier aussi la session par l'API :
```bash
# démarrer le serveur de l'étudiant
curl -sk -X POST -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/hub/api/users/essai/server
# vérifier qu'il est prêt (servers."".ready == true)
curl -sk -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/hub/api/users/essai
# créer un terminal dans le conteneur
curl -sk -X POST -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/user/essai/api/terminals
```

## Formations (service Contenus)
- Le site des formations est servi à la racine (`/`, `/parcours/…`, `/modules/…`). Son contenu vit dans un dépôt Git, dans le volume `contenus-data`, initialisé au premier démarrage avec le parcours « ROS 2 Fondamentaux » du dossier `content/`.
- **Éditer** : connectez-vous avec une adresse de `ADMIN_EMAILS`, puis « Mon compte » → « Éditer les formations » (la session de l'éditeur dure 12 h). En secours, un lien administrateur valable 5 minutes peut être émis à la main :
  ```bash
  set -a; . deploy/.env; set +a
  echo "https://$DOMAIN/admin/login?token=$(python scripts/mint_token.py --sub moi --role admin)"
  ```
  L'éditeur permet de modifier chaque fichier d'un module (aperçu en direct), le QCM en formulaire, l'ordre et les coefficients des parcours, de créer un module à partir d'un modèle, et de restaurer une version antérieure. Le **guide de rédaction** est dans l'éditeur (`/admin/guide/`).
- **Publier** : les étudiants ne voient une modification qu'après « Publier le brouillon », qui teste chaque module modifié dans un conteneur `ros-lab` sans réseau. Une publication refusée affiche le journal des tests et laisse la version en ligne intacte.
- **Sauvegarde** : `CONTENT_GIT_REMOTE` (facultatif) pousse les branches `brouillon` et `publie` vers un dépôt distant à chaque publication ; l'URL doit être accessible en écriture depuis le conteneur. Sinon, sauvegardez le volume `contenus-data`.
- Tester les modules hors de la plateforme : `ROS_LAB_IMAGE=ros-lab:0.1.0 python scripts/test_modules.py [module…]` (dépendances : `pip install -r contenus/requirements.txt`).

## Lab UI
- Servi par Caddy sous `/lab/`, sur la même origine que le Hub. Après `/hub/jwt_login`, la page demande à `/hub/lab_token` un jeton d'une heure limité au serveur de l'étudiant.
- Le Lab UI arrête lui-même le conteneur après 20 min sans interaction dans la page (avertissement 5 min avant) ; le culler du Hub reste le filet de sécurité quand l'onglet est fermé.
- Développement : `cd lab-ui && npm ci && npm test` (tests unitaires), `npm run dev` (serveur Vite), `npm run build`.
- Tests de bout en bout, contre un déploiement lancé : `set -a; . deploy/.env; set +a; cd lab-ui && npx playwright test --grep-invert @limit`.
- Robot simulé pour la vue 2D : `academy-diffbot` dans un terminal (`/cmd_vel` → `/odom`).

## Mettre à jour l'image étudiant
Construire `ros-lab:<nouvelle version>`, changer `ROS_LAB_IMAGE` dans `.env`, `docker compose up -d`. Les conteneurs déjà lancés gardent l'ancienne image jusqu'à leur arrêt ; les volumes ne sont pas touchés.

## Diagnostic
- `docker logs hub` : connexions refusées (`Connexion par jeton refusée`), démarrages, arrêts pour inactivité, démarrages refusés pour quota.
- `docker compose logs comptes` : liens de connexion (sans SMTP), arrêts pour quota (`Quota épuisé : serveur de u… arrêté`), erreurs d'envoi d'e-mail. Pas de journal d'accès : il contiendrait les liens de connexion.
- `docker ps --filter name=jupyter-` : sessions actives.

## Limites connues
- Le service Contenus monte la socket Docker pour tester les modules à la publication : comme le Hub, sa compromission équivaut à un accès root à l'hôte. Seul l'administrateur y a accès (jeton `role: admin`).
- `check.sh` et `explication.md` sont lisibles depuis le conteneur de l'étudiant (`~/.academy/<module>`) : la triche est possible en V1, comme prévu par la spec.
- Les serveurs étudiants (`/user/<nom>/`) partagent l'origine du Lab UI et un étudiant peut y servir n'importe quel fichier. Caddy leur impose `Content-Security-Policy: sandbox` : ces pages ont une origine opaque et ne peuvent lire ni les cookies du Hub, ni `/hub/lab_token`, ni les autres serveurs. Ne pas retirer cet en-tête ; à terme, des sous-domaines par étudiant (`subdomain_host`) supprimeraient le partage d'origine.
- Le jeton du Lab UI passe dans l'URL des WebSockets (`JUPYTERHUB_ALLOW_TOKEN_IN_URL=1`) : un navigateur ne peut pas y mettre d'en-tête. Il est limité au serveur de l'étudiant et expire en 1 h ; ne pas activer de journal d'accès Caddy qui enregistrerait les URL complètes.
- La réussite d'un exercice est déclarée par le Lab UI après `check.sh`, qui tourne dans le conteneur de l'étudiant : un étudiant peut la simuler (triche possible en V1, comme prévu par la spec). Les QCM, eux, sont corrigés côté serveur.
- Les minutes de lab sont relevées chaque minute auprès du Hub : un serveur prêt compte une minute entière, et un étudiant hors quota peut garder son lab jusqu'au relevé suivant (une minute au plus).
- Tous les conteneurs étudiants partagent le réseau `ros-lab-net` : ils peuvent atteindre les ports des autres, protégés par l'authentification par jeton Jupyter mais non isolés au niveau réseau.
- La limite de 1 Go par volume n'est pas encore appliquée (nécessite des quotas de projet XFS sur l'hôte).
- Sur certaines versions de Docker, un réseau `internal` laisse quand même les conteneurs joindre l'hôte via l'adresse de la passerelle du bridge : les services de l'hôte écoutant sur 0.0.0.0 (sshd, bases de données, supervision) peuvent alors être atteints depuis le code des étudiants. L'opérateur doit lier ces services à des interfaces précises, ou ajouter une règle de pare-feu rejetant le trafic venant du sous-réseau `ros-lab-net` vers l'hôte. Exemple : trouver le bridge avec `docker network inspect ros-lab-net -f '{{.Id}}'` (le bridge s'appelle `br-` suivi des 12 premiers caractères de l'identifiant), puis `iptables -I INPUT -i <bridge> -j DROP`.
- Le Hub s'exécute en root avec accès à la socket Docker (inhérent à DockerSpawner) : sa compromission équivaut à un accès root à l'hôte.
- La couche inscriptible du conteneur et le swap ne sont pas limités en taille : un étudiant peut remplir le disque de l'hôte.

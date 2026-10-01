# Déploiement du moteur de sessions

## Prérequis
- Un serveur Linux avec Docker et le plugin Compose (≈16 vCPU / 64 Go pour 30 à 40 sessions).
- Un nom de domaine pointant vers le serveur (ports 80 et 443 ouverts).

## Installation
1. `docker build -t ros-lab:0.1.0 images/ros-lab`
2. `cp deploy/.env.example deploy/.env` puis remplacer chaque secret par `openssl rand -hex 32` et `DOMAIN` par le domaine.
3. `cd deploy && docker compose up -d --build` (construit aussi le Lab UI dans l'image Caddy : Node n'est pas nécessaire sur le serveur), puis, toujours depuis `deploy/` : `set -a; . ./.env; set +a; BASE_URL=https://$DOMAIN ../scripts/wait_for_hub.sh`

## Tester un accès étudiant
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

## Lab UI
- Servi par Caddy sous `/lab/`, sur la même origine que le Hub. Après `/hub/jwt_login`, la page demande à `/hub/lab_token` un jeton d'une heure limité au serveur de l'étudiant.
- Le Lab UI arrête lui-même le conteneur après 20 min sans interaction dans la page (avertissement 5 min avant) ; le culler du Hub reste le filet de sécurité quand l'onglet est fermé.
- Développement : `cd lab-ui && npm ci && npm test` (tests unitaires), `npm run dev` (serveur Vite), `npm run build`.
- Tests de bout en bout, contre un déploiement lancé : `set -a; . deploy/.env; set +a; cd lab-ui && npx playwright test --grep-invert @limit`.
- Robot simulé pour la vue 2D : `academy-diffbot` dans un terminal (`/cmd_vel` → `/odom`).

## Mettre à jour l'image étudiant
Construire `ros-lab:<nouvelle version>`, changer `ROS_LAB_IMAGE` dans `.env`, `docker compose up -d`. Les conteneurs déjà lancés gardent l'ancienne image jusqu'à leur arrêt ; les volumes ne sont pas touchés.

## Diagnostic
- `docker logs hub` : connexions refusées (`Connexion par jeton refusée`), démarrages, arrêts pour inactivité.
- `docker ps --filter name=jupyter-` : sessions actives.

## Limites connues
- Les serveurs étudiants (`/user/<nom>/`) partagent l'origine du Lab UI et un étudiant peut y servir n'importe quel fichier. Caddy leur impose `Content-Security-Policy: sandbox` : ces pages ont une origine opaque et ne peuvent lire ni les cookies du Hub, ni `/hub/lab_token`, ni les autres serveurs. Ne pas retirer cet en-tête ; à terme, des sous-domaines par étudiant (`subdomain_host`) supprimeraient le partage d'origine.
- Le jeton du Lab UI passe dans l'URL des WebSockets (`JUPYTERHUB_ALLOW_TOKEN_IN_URL=1`) : un navigateur ne peut pas y mettre d'en-tête. Il est limité au serveur de l'étudiant et expire en 1 h ; ne pas activer de journal d'accès Caddy qui enregistrerait les URL complètes.
- Serveur plein : le Lab UI réessaie toutes les 15 s mais n'affiche pas de position dans la file (il faudra une file partagée, côté service Comptes).
- Tous les conteneurs étudiants partagent le réseau `ros-lab-net` : ils peuvent atteindre les ports des autres, protégés par l'authentification par jeton Jupyter mais non isolés au niveau réseau.
- La limite de 1 Go par volume n'est pas encore appliquée (nécessite des quotas de projet XFS sur l'hôte).
- Sur certaines versions de Docker, un réseau `internal` laisse quand même les conteneurs joindre l'hôte via l'adresse de la passerelle du bridge : les services de l'hôte écoutant sur 0.0.0.0 (sshd, bases de données, supervision) peuvent alors être atteints depuis le code des étudiants. L'opérateur doit lier ces services à des interfaces précises, ou ajouter une règle de pare-feu rejetant le trafic venant du sous-réseau `ros-lab-net` vers l'hôte. Exemple : trouver le bridge avec `docker network inspect ros-lab-net -f '{{.Id}}'` (le bridge s'appelle `br-` suivi des 12 premiers caractères de l'identifiant), puis `iptables -I INPUT -i <bridge> -j DROP`.
- Le Hub s'exécute en root avec accès à la socket Docker (inhérent à DockerSpawner) : sa compromission équivaut à un accès root à l'hôte.
- La couche inscriptible du conteneur et le swap ne sont pas limités en taille : un étudiant peut remplir le disque de l'hôte.

# Déploiement du moteur de sessions

## Prérequis
- Un serveur Linux avec Docker et le plugin Compose (≈16 vCPU / 64 Go pour 30 à 40 sessions).
- Un nom de domaine pointant vers le serveur (ports 80 et 443 ouverts).

## Installation
1. `docker build -t ros-lab:0.1.0 images/ros-lab`
2. `cp deploy/.env.example deploy/.env` puis remplacer chaque secret par `openssl rand -hex 32` et `DOMAIN` par le domaine.
3. `cd deploy && docker compose up -d --build`, puis, toujours depuis `deploy/` : `set -a; . ./.env; set +a; BASE_URL=https://$DOMAIN ../scripts/wait_for_hub.sh`

## Tester un accès étudiant
```bash
set -a; . deploy/.env; set +a
pip install PyJWT==2.9.0
TOKEN=$(python scripts/mint_token.py --sub essai --plan free)
echo "https://$DOMAIN/hub/jwt_login?token=$TOKEN"
```
Ouvrir le lien (connexion puis redirection), puis vérifier la session par l'API :
```bash
# démarrer le serveur de l'étudiant
curl -sk -X POST -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/hub/api/users/essai/server
# vérifier qu'il est prêt (servers."".ready == true)
curl -sk -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/hub/api/users/essai
# créer un terminal dans le conteneur
curl -sk -X POST -H "Authorization: token $HUB_ADMIN_TOKEN" https://$DOMAIN/user/essai/api/terminals
```
L'interface complète du terminal arrivera avec l'interface Lab (sous-projet 2).

## Mettre à jour l'image étudiant
Construire `ros-lab:<nouvelle version>`, changer `ROS_LAB_IMAGE` dans `.env`, `docker compose up -d`. Les conteneurs déjà lancés gardent l'ancienne image jusqu'à leur arrêt ; les volumes ne sont pas touchés.

## Diagnostic
- `docker logs hub` : connexions refusées (`Connexion par jeton refusée`), démarrages, arrêts pour inactivité.
- `docker ps --filter name=jupyter-` : sessions actives.

## Limites connues
- Tous les conteneurs étudiants partagent le réseau `ros-lab-net` : ils peuvent atteindre les ports des autres, protégés par l'authentification par jeton Jupyter mais non isolés au niveau réseau.
- La limite de 1 Go par volume n'est pas encore appliquée (nécessite des quotas de projet XFS sur l'hôte).
- Sur certaines versions de Docker, un réseau `internal` laisse quand même les conteneurs joindre l'hôte via l'adresse de la passerelle du bridge : les services de l'hôte écoutant sur 0.0.0.0 (sshd, bases de données, supervision) peuvent alors être atteints depuis le code des étudiants. L'opérateur doit lier ces services à des interfaces précises, ou ajouter une règle de pare-feu rejetant le trafic venant du sous-réseau `ros-lab-net` vers l'hôte. Exemple : trouver le bridge avec `docker network inspect ros-lab-net -f '{{.Id}}'` (le bridge s'appelle `br-` suivi des 12 premiers caractères de l'identifiant), puis `iptables -I INPUT -i <bridge> -j DROP`.
- Le Hub s'exécute en root avec accès à la socket Docker (inhérent à DockerSpawner) : sa compromission équivaut à un accès root à l'hôte.
- La couche inscriptible du conteneur et le swap ne sont pas limités en taille : un étudiant peut remplir le disque de l'hôte.

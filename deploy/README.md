# Déploiement du moteur de sessions

## Prérequis
- Un serveur Linux avec Docker et le plugin Compose (≈16 vCPU / 64 Go pour 30 à 40 sessions).
- Un nom de domaine pointant vers le serveur (ports 80 et 443 ouverts).

## Installation
1. `docker build -t ros-lab:0.1.0 images/ros-lab`
2. `cp deploy/.env.example deploy/.env` puis remplacer chaque secret par `openssl rand -hex 32` et `DOMAIN` par le domaine.
3. `cd deploy && docker compose up -d --build`

## Tester un accès étudiant
```bash
set -a; . deploy/.env; set +a
TOKEN=$(python scripts/mint_token.py --sub essai --plan free)
echo "https://$DOMAIN/hub/jwt_login?token=$TOKEN"
```
Ouvrir le lien, puis `https://$DOMAIN/user/essai/terminals/1`.

## Mettre à jour l'image étudiant
Construire `ros-lab:<nouvelle version>`, changer `ROS_LAB_IMAGE` dans `.env`, `docker compose up -d`. Les conteneurs déjà lancés gardent l'ancienne image jusqu'à leur arrêt ; les volumes ne sont pas touchés.

## Diagnostic
- `docker logs hub` : connexions refusées (`Connexion par jeton refusée`), démarrages, arrêts pour inactivité.
- `docker ps --filter name=jupyter-` : sessions actives.

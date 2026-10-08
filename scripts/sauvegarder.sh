#!/usr/bin/env bash
# Sauvegarde de RoboForge : base des comptes, contenu des formations, dossiers des étudiants
# et configuration (deploy/.env), dans un dossier daté. Les sauvegardes plus anciennes que
# SAUVEGARDE_JOURS (deploy/.env, 14 par défaut) sont effacées.
#
#   sudo scripts/sauvegarder.sh [--destination DOSSIER] [--jours N] [--sans-etudiants] [--copier-vers CIBLE]
#
# --destination   dossier des sauvegardes (défaut : /var/backups/ros-academy)
# --sans-etudiants  sans les dossiers des étudiants (les plus volumineux)
# --copier-vers   copie ensuite les sauvegardes hors du serveur avec rsync, ex.
#                 u123456@u123456.your-storagebox.de:ros-academy (clé SSH à installer avant)
#
# scripts/installer-serveur.sh l'installe en tâche quotidienne (timer systemd
# ros-academy-sauvegarde, à 3 h 17). Restauration : deploy/README.md, « Sauvegardes ».
set -euo pipefail

RACINE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEPLOY="$RACINE/deploy"
ENV_FILE="$DEPLOY/.env"
DEST=/var/backups/ros-academy JOURS="" ETUDIANTS=1 COPIE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --destination) DEST=$2; shift 2 ;;
    --jours) JOURS=$2; shift 2 ;;
    --sans-etudiants) ETUDIANTS=0; shift ;;
    --copier-vers) COPIE=$2; shift 2 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
  esac
done

fail() { echo "Erreur : $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail "à lancer en root (sudo)"
[ -f "$ENV_FILE" ] || fail "$ENV_FILE introuvable"
valeur_env() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -1; }
JOURS=${JOURS:-$(valeur_env SAUVEGARDE_JOURS)}
JOURS=${JOURS:-14}
[[ $JOURS =~ ^[0-9]+$ ]] && [ "$JOURS" -ge 1 ] || fail "--jours : nombre de jours attendu"
HOMES=$(valeur_env LAB_HOMES_DIR)

compose() { (cd "$DEPLOY" && docker compose "$@"); }
# Image déjà présente sur le serveur, avec tar : pas de téléchargement pendant la sauvegarde
OUTIL=postgres:16-alpine

volume_compose() {  # volume d'un service compose du projet (nom préfixé par le projet)
  local projet
  projet=$(compose config --format json 2>/dev/null | sed -n 's/^ *"name": *"\([^"]*\)".*/\1/p' | head -1)
  docker volume ls -q --filter "label=com.docker.compose.volume=$1" \
    ${projet:+--filter "label=com.docker.compose.project=$projet"} | head -1
}

umask 077
mkdir -p "$DEST"
DOSSIER="$DEST/$(date +%Y-%m-%d_%H%M%S)"
mkdir "$DOSSIER"
echo "Sauvegarde dans $DOSSIER"

# 1. Base des comptes (format personnalisé de pg_dump : restauration sélective possible)
compose exec -T postgres pg_dump -U comptes -Fc comptes > "$DOSSIER/comptes.dump"
compose exec -T postgres pg_restore --list < "$DOSSIER/comptes.dump" > /dev/null \
  || fail "la sauvegarde de la base est illisible"
echo "  base des comptes : $(du -h "$DOSSIER/comptes.dump" | cut -f1)"

# 2. Contenu des formations (dépôt Git du volume contenus-data : brouillon, publié, historique)
VOL=$(volume_compose contenus-data)
[ -n "$VOL" ] || fail "volume contenus-data introuvable"
docker run --rm -v "$VOL":/data:ro -v "$DOSSIER":/out "$OUTIL" tar -C /data -czf /out/contenus.tar.gz .
echo "  contenu des formations : $(du -h "$DOSSIER/contenus.tar.gz" | cut -f1)"

# 3. Dossiers des étudiants
if [ "$ETUDIANTS" = 1 ]; then
  if [ -n "$HOMES" ]; then
    # code 1 : un fichier a changé pendant la lecture (lab en cours) ; la sauvegarde reste valable
    tar -C "$HOMES" --numeric-owner -czf "$DOSSIER/etudiants.tar.gz" . || [ $? -eq 1 ]
  else  # volumes Docker ros-lab-home-<nom>
    mkdir "$DOSSIER/etudiants"
    for v in $(docker volume ls -q --filter name=ros-lab-home-); do
      docker run --rm -v "$v":/data:ro -v "$DOSSIER/etudiants":/out "$OUTIL" \
        tar -C /data -czf "/out/$v.tar.gz" .
    done
  fi
  echo "  dossiers des étudiants : $(du -sh "$DOSSIER"/etudiants* | cut -f1 | head -1)"
fi

# 4. Configuration (contient les secrets : le dossier n'est lisible que par root)
cp "$ENV_FILE" "$DOSSIER/env"
(cd "$DOSSIER" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "  total : $(du -sh "$DOSSIER" | cut -f1)"

# 5. Rotation
find "$DEST" -mindepth 1 -maxdepth 1 -type d -name '20??-??-??_*' -mtime "+$((JOURS - 1))" -print0 \
  | xargs -0 -r rm -rf
echo "  sauvegardes gardées : $(find "$DEST" -mindepth 1 -maxdepth 1 -type d -name '20??-??-??_*' | wc -l) ($JOURS jours)"

# 6. Copie hors du serveur
if [ -n "$COPIE" ]; then
  command -v rsync >/dev/null || fail "rsync introuvable (apt install rsync)"
  rsync -a --delete "$DEST/" "$COPIE/"
  echo "  copié vers $COPIE"
fi

#!/usr/bin/env bash
# Copie les volumes Docker des étudiants (ros-lab-home-u<id>) vers LAB_HOMES_DIR, rattachés à
# leur projet XFS (même numéro que le Hub : 10000 + id). À lancer une fois, labs arrêtés,
# après scripts/preparer-hote.sh et avant de démarrer avec docker-compose.quotas.yml :
#
#   sudo scripts/migrer-volumes.sh /srv/ros-academy/homes
#
# Les volumes ne sont pas supprimés (à faire à la main une fois la migration vérifiée :
# docker volume rm ros-lab-home-u…). Un dossier déjà présent n'est pas écrasé.
set -euo pipefail
DOSSIER=${1:?usage : migrer-volumes.sh LAB_HOMES_DIR}
[ "$(id -u)" = 0 ] || { echo "à lancer en root (sudo)" >&2; exit 1; }
if docker ps --format '{{.Names}}' | grep -q '^jupyter-'; then
  echo "Des labs sont en cours : arrêtez-les d'abord (docker compose stop hub)." >&2; exit 1
fi
for volume in $(docker volume ls -q --filter name=ros-lab-home-u); do
  [[ $volume =~ ^ros-lab-home-u[0-9]+$ ]] || continue
  nom=${volume#ros-lab-home-}
  id=${nom#u}
  cible="$DOSSIER/$nom"
  if [ -e "$cible" ]; then echo "$nom : $cible existe déjà, ignoré"; continue; fi
  mkdir "$cible"
  docker run --rm -v "$volume":/src:ro -v "$cible":/dst alpine:3.20 cp -a /src/. /dst/
  chown 1000:1000 "$cible"
  xfs_quota -x -c "project -s -p $cible $((10000 + id))" "$DOSSIER" >/dev/null
  echo "$nom : $(du -sh "$cible" | cut -f1) copiés (projet $((10000 + id)))"
done
echo "Occupation : xfs_quota -x -c 'report -p -h' $DOSSIER"

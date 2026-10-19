#!/usr/bin/env bash
# Copie les volumes Docker des étudiants (ros-lab-home-u<id>, et ros-lab-home-u<id>--<parcours> pour
# le dossier d'un parcours) vers LAB_HOMES_DIR (u<id>, et u<id>/.parcours/<parcours>), rattachés à
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
# triés : le dossier commun (u<id>) avant ceux de ses parcours (u<id>--<parcours>)
for volume in $(docker volume ls -q --filter name=ros-lab-home-u | sort); do
  if [[ $volume =~ ^ros-lab-home-(u([0-9]+))$ ]]; then
    nom=${BASH_REMATCH[1]}; id=${BASH_REMATCH[2]}; cible="$DOSSIER/$nom"
  elif [[ $volume =~ ^ros-lab-home-(u([0-9]+))--([a-z0-9][a-z0-9-]{0,63})$ ]]; then
    nom="${BASH_REMATCH[1]} (${BASH_REMATCH[3]})"; id=${BASH_REMATCH[2]}
    cible="$DOSSIER/${BASH_REMATCH[1]}/.parcours/${BASH_REMATCH[3]}"
    for d in "$DOSSIER/${BASH_REMATCH[1]}" "$DOSSIER/${BASH_REMATCH[1]}/.parcours"; do
      [ -d "$d" ] || { mkdir "$d"; chown 1000:1000 "$d"; }
    done
  else
    continue
  fi
  if [ -e "$cible" ]; then echo "$nom : $cible existe déjà, ignoré"; continue; fi
  mkdir "$cible"
  docker run --rm -v "$volume":/src:ro -v "$cible":/dst alpine:3.20 cp -a /src/. /dst/
  chown 1000:1000 "$cible"
  xfs_quota -x -c "project -s -p $cible $((10000 + id))" "$DOSSIER" >/dev/null
  echo "$nom : $(du -sh "$cible" | cut -f1) copiés (projet $((10000 + id)))"
done
echo "Occupation : xfs_quota -x -c 'report -p -h' $DOSSIER"

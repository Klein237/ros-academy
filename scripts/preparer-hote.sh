#!/usr/bin/env bash
# Prépare l'hôte pour les dossiers des étudiants limités à 1 Go (quotas de projet XFS).
#
#   sudo scripts/preparer-hote.sh --image /var/lib/ros-academy/homes.img --taille 200G
#   sudo scripts/preparer-hote.sh --partition /dev/sdb1
#
# --image      fichier image formaté en XFS, monté au démarrage (aucune partition à créer)
# --partition  partition dédiée, formatée en XFS si elle est vide (refus si elle contient
#              déjà un autre système de fichiers)
# --dossier    point de montage (défaut /srv/ros-academy/homes) → LAB_HOMES_DIR dans deploy/.env
# --quota      limite par étudiant (défaut 1g) ; --inodes : nombre de fichiers (défaut 200000)
#
# Le script est rejouable : il ne reformate jamais un XFS existant et ne fait que réappliquer
# le montage et la limite par défaut. Prévoir pour l'image ou la partition environ
# 1 Go × nombre d'étudiants actifs (l'image est creuse : seul l'espace écrit est consommé).
set -euo pipefail

IMAGE="" PARTITION="" TAILLE="" DOSSIER=/srv/ros-academy/homes QUOTA=1g INODES=200000
while [ $# -gt 0 ]; do
  case "$1" in
    --image) IMAGE=$2; shift 2 ;;
    --partition) PARTITION=$2; shift 2 ;;
    --taille) TAILLE=$2; shift 2 ;;
    --dossier) DOSSIER=$2; shift 2 ;;
    --quota) QUOTA=$2; shift 2 ;;
    --inodes) INODES=$2; shift 2 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
  esac
done

fail() { echo "Erreur : $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail "à lancer en root (sudo)"
if [ -n "$IMAGE" ] && [ -n "$PARTITION" ] || [ -z "$IMAGE$PARTITION" ]; then
  fail "indiquer --image FICHIER --taille N ou --partition PÉRIPHÉRIQUE"
fi
for cmd in mkfs.xfs xfs_quota blkid mount; do
  command -v "$cmd" >/dev/null || fail "$cmd introuvable (apt install xfsprogs)"
done
grep -qw xfs /proc/filesystems || modprobe xfs 2>/dev/null || fail "le noyau ne gère pas XFS"

if [ -n "$IMAGE" ]; then
  SOURCE=$IMAGE
  OPTIONS=loop,prjquota,nofail
  if [ ! -e "$IMAGE" ]; then
    [ -n "$TAILLE" ] || fail "--taille est obligatoire pour créer l'image (ex. 200G)"
    mkdir -p "$(dirname "$IMAGE")"
    truncate -s "$TAILLE" "$IMAGE"
    chmod 600 "$IMAGE"
  fi
  FSTAB_SOURCE=$IMAGE
else
  SOURCE=$PARTITION
  OPTIONS=prjquota,nofail
  [ -b "$PARTITION" ] || fail "$PARTITION n'est pas un périphérique bloc"
fi

TYPE=$(blkid -o value -s TYPE "$SOURCE" 2>/dev/null || true)
case "$TYPE" in
  xfs) echo "XFS déjà présent sur $SOURCE : pas de formatage." ;;
  "") echo "Formatage de $SOURCE en XFS…"; mkfs.xfs -q "$SOURCE" ;;
  *) fail "$SOURCE contient déjà un système $TYPE : refus de le formater" ;;
esac
if [ -n "$PARTITION" ]; then
  FSTAB_SOURCE="UUID=$(blkid -o value -s UUID "$PARTITION")"
fi

mkdir -p "$DOSSIER"
LIGNE="$FSTAB_SOURCE $DOSSIER xfs $OPTIONS 0 0"
if ! awk -v d="$DOSSIER" '$2 == d {found=1} END {exit !found}' /etc/fstab; then
  echo "$LIGNE" >> /etc/fstab
  echo "Ajouté à /etc/fstab : $LIGNE"
fi
if ! mountpoint -q "$DOSSIER"; then
  mount "$DOSSIER"
fi
findmnt -n -o FSTYPE,OPTIONS "$DOSSIER" | grep -q '^xfs .*prjquota' \
  || fail "$DOSSIER n'est pas monté en XFS avec prjquota (vérifier /etc/fstab)"

# Limite par défaut de tous les projets : chaque dossier d'étudiant (un projet) la reçoit
xfs_quota -x -c "limit -p -d bhard=$QUOTA ihard=$INODES" "$DOSSIER"
chown root:root "$DOSSIER"
chmod 711 "$DOSSIER"   # un étudiant ne peut pas lister les dossiers des autres

echo
echo "Prêt. Dans deploy/.env :"
echo "  LAB_HOMES_DIR=$DOSSIER"
echo "  COMPOSE_FILE=docker-compose.yml:docker-compose.quotas.yml"
echo "puis : cd deploy && docker compose up -d"
echo "Occupation par étudiant : xfs_quota -x -c 'report -p -h' $DOSSIER"

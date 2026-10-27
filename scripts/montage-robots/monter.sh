#!/usr/bin/env bash
# Montage court de vidéos de robots réels pour le site : un extrait par vidéo, enchaînés en fondu,
# même cadrage (1280×720, 24 images/s), étalonnage sombre et chaud (palette noir et or), sans son.
#
#   scripts/montage-robots/monter.sh DOSSIER_DES_VIDEOS SORTIE [SECONDES_PAR_EXTRAIT]
#
# DOSSIER_DES_VIDEOS : les vidéos sources, dans l'ordre alphabétique (01-drone.mp4, 02-marin.mp4…).
#   Un fichier « nom.debut » à côté d'une vidéo (ex. 02-marin.debut contenant 4.5) choisit le début
#   de l'extrait, en secondes ; sinon il commence à 1 s. Un fichier « nom.cadrage » (0 à 1) place la
#   fenêtre 16:9 dans une vidéo plus haute (verticale) : 0 en haut, 0.5 au centre (par défaut), 1 en bas.
# SORTIE : préfixe des fichiers produits (SORTIE.webm, SORTIE.mp4, SORTIE.webp, et pour les téléphones
#   SORTIE-mobile.webm et SORTIE-mobile.mp4 : cadrage vertical 360×640, environ 3 fois plus légers).
# Seules des vidéos dont la licence permet l'usage commercial (Pexels, Pixabay, Coverr, vos tournages)
# doivent entrer ici : notez leur source et leur licence dans SOURCES.md, à côté des vidéos.
set -euo pipefail
DOSSIER=${1:?usage : monter.sh DOSSIER_DES_VIDEOS SORTIE [SECONDES_PAR_EXTRAIT]}
SORTIE=${2:?usage : monter.sh DOSSIER_DES_VIDEOS SORTIE [SECONDES_PAR_EXTRAIT]}
DUREE=${3:-2.5}
FONDU=0.5
command -v ffmpeg >/dev/null || { echo "ffmpeg est nécessaire" >&2; exit 1; }

mapfile -t VIDEOS < <(find "$DOSSIER" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.webm' -o -iname '*.mkv' \) | LC_ALL=C sort)
[ "${#VIDEOS[@]}" -ge 2 ] || { echo "au moins deux vidéos dans $DOSSIER" >&2; exit 1; }

entrees=() filtres="" n=0
for v in "${VIDEOS[@]}"; do
  debut=1
  [ -f "${v%.*}.debut" ] && debut=$(tr -dc '0-9.' < "${v%.*}.debut")
  cadrage=0.5
  [ -f "${v%.*}.cadrage" ] && cadrage=$(tr -dc '0-9.' < "${v%.*}.cadrage")
  entrees+=(-ss "$debut" -t "$DUREE" -i "$v")
  # cadrage commun, étalonnage : un peu moins de saturation, ombres plus denses, tons chauds
  filtres+="[$n:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720:(iw-1280)/2:(ih-720)*$cadrage,fps=24,setsar=1,"
  filtres+="eq=saturation=0.85:contrast=1.08:brightness=-0.04,colorbalance=rs=0.04:bs=-0.05:rh=0.03:bh=-0.04,format=yuv420p[v$n];"
  n=$((n + 1))
done
# fondus enchaînés : chaque extrait commence FONDU secondes avant la fin du précédent
precedent="[v0]" decalage=0
for ((i = 1; i < n; i++)); do
  decalage=$(awk -v d="$decalage" -v t="$DUREE" -v f="$FONDU" 'BEGIN { printf "%.3f", d + t - f }')
  filtres+="${precedent}[v${i}]xfade=transition=fade:duration=$FONDU:offset=${decalage}[x${i}];"
  precedent="[x${i}]"
done
filtres=${filtres%;}

mkdir -p "$(dirname "$SORTIE")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
ffmpeg -loglevel error -y "${entrees[@]}" -filter_complex "$filtres" -map "$precedent" -an \
  -c:v libx264 -crf 16 -preset medium "$tmp/montage.mp4"
# fichiers du site : WebM (VP9) d'abord, MP4 (H.264) en repli, image d'attente WebP
ffmpeg -loglevel error -y -i "$tmp/montage.mp4" -c:v libvpx-vp9 -b:v 0 -crf 42 -row-mt 1 -deadline good -cpu-used 2 -an "$SORTIE.webm"
ffmpeg -loglevel error -y -i "$tmp/montage.mp4" -c:v libx264 -crf 29 -preset slow -pix_fmt yuv420p -movflags +faststart -an "$SORTIE.mp4"
ffmpeg -loglevel error -y -ss 0.5 -i "$tmp/montage.mp4" -frames:v 1 -c:v libwebp -quality 70 "$SORTIE.webp"
# téléphones : le centre de l'image, en vertical (ce que object-fit: cover y montre de toute façon)
vertical="crop=406:720:(iw-406)/2:0,scale=360:640"
ffmpeg -loglevel error -y -i "$tmp/montage.mp4" -vf "$vertical" -c:v libvpx-vp9 -b:v 0 -crf 42 -row-mt 1 -deadline good -cpu-used 2 -an "$SORTIE-mobile.webm"
ffmpeg -loglevel error -y -i "$tmp/montage.mp4" -vf "$vertical" -c:v libx264 -crf 30 -preset slow -pix_fmt yuv420p -movflags +faststart -an "$SORTIE-mobile.mp4"
total=$(awk -v n="$n" -v t="$DUREE" -v f="$FONDU" 'BEGIN { printf "%.1f", n * t - (n - 1) * f }')
echo "$n extraits, $total s : $(du -h "$SORTIE.webm" | cut -f1) (WebM), $(du -h "$SORTIE.mp4" | cut -f1) (MP4)"

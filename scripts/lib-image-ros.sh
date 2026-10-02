# shellcheck shell=bash
# Image ROS des labs à jour : son empreinte (contenu de images/ros-lab) est gardée en étiquette.
# Une image construite avant une mise à jour du dépôt (nouveaux paquets : RViz, Gazebo…) est
# reconstruite, même si son nom (ros-lab:0.1.0) n'a pas changé. Sourcé par demarrer-local.sh
# et installer-serveur.sh.

empreinte_image_ros() {  # empreinte_image_ros DOSSIER
  (cd "$1" && find . -type f ! -path '*/__pycache__/*' ! -name '*.pyc' -print | LC_ALL=C sort \
    | while IFS= read -r f; do printf '%s\n' "$f"; cat "$f"; done) \
    | { if command -v sha256sum >/dev/null; then sha256sum; else shasum -a 256; fi; } | cut -c1-16
}

image_ros_a_jour() {  # image_ros_a_jour IMAGE DOSSIER [options de docker build…]
  local image=$1 dossier=$2 attendue actuelle
  shift 2
  attendue=$(empreinte_image_ros "$dossier")
  actuelle=$(docker image inspect -f '{{index .Config.Labels "ros-academy.empreinte"}}' "$image" 2>/dev/null || true)
  if [ "$actuelle" = "$attendue" ]; then
    echo "   $image à jour"
    return
  fi
  if [ -n "$actuelle" ] || docker image inspect "$image" >/dev/null 2>&1; then
    echo "   $image construite depuis une version plus ancienne du dépôt : reconstruction…"
  else
    echo "   construction de $image : 15 à 40 minutes la première fois (ROS 2, RViz, Gazebo)…"
  fi
  docker build "$@" --label "ros-academy.empreinte=$attendue" -t "$image" "$dossier"
}

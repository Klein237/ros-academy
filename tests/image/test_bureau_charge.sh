#!/usr/bin/env bash
# Le bureau du lab sous charge, aux limites de l'offre gratuite (1 processeur, 2 Go, 256 processus,
# comme le Hub les applique) : Gazebo seul, puis avec RViz2, puis avec la fenêtre de Gazebo.
# Pour chaque étape : facteur temps réel de la simulation, processeur et mémoire du conteneur,
# temps d'ouverture de la fenêtre et capture du bureau (rapport.md et *.png dans le dossier donné).
# C'est une mesure : le script n'échoue que si la simulation ne démarre pas.
set -euo pipefail
IMG="${IMG:-ros-lab:0.1.0}"
CPUS="${CPUS:-1}"
MEM="${MEM:-2g}"
ICI=$(cd "$(dirname "$0")" && pwd)
RACINE=$(cd "$ICI/../.." && pwd)
OUT="${1:-bureau-charge}"
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

# workspace du module Gazebo : départ de l'exercice + solution = le robot complet, et la configuration RViz
WS=$(mktemp -d)
EX="$RACINE/content/modules/11-gazebo/exercice"
cp -r "$EX/depart/." "$WS/"
cp -r "$EX/solution/." "$WS/"
cp "$ICI/bureau/robot.rviz" "$WS/robot.rviz"
chmod -R a+rwX "$WS"

C=bureau-charge
docker rm -f "$C" >/dev/null 2>&1 || true
docker run -d --name "$C" --cpus="$CPUS" --memory="$MEM" --memory-swap="$MEM" --pids-limit=256 \
  -p 127.0.0.1:5901:5901 -v "$WS:/home/etudiant/ws" "$IMG" sleep infinity >/dev/null
fin() {
  for f in xvnc gazebo rviz gzgui build; do docker exec "$C" cat "/tmp/$f.log" > "$OUT/$f.log" 2>/dev/null || true; done
  docker rm -f "$C" >/dev/null 2>&1 || true
}
trap fin EXIT
dx() { docker exec "$C" bash -lc "$1"; }
fond() { docker exec -d "$C" bash -lc "$1"; }
attendre() {  # $1 : commande de test, $2 : délai maximal (s) ; affiche le temps écoulé
  local t0=$SECONDS
  until dx "$1" >/dev/null 2>&1; do
    if (( SECONDS - t0 > $2 )); then echo "—"; return 1; fi
    sleep 1
  done
  echo "$(( SECONDS - t0 )) s"
}

# l'écran du lab, comme academy-bureau (mais joignable depuis l'hôte pour les captures)
fond 'Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost=0 -rfbport 5901 -AlwaysShared=1 -nolisten tcp > /tmp/xvnc.log 2>&1'
attendre 'xdpyinfo' 30 >/dev/null
fond 'xsetroot -solid "#1b1f24"; openbox > /tmp/openbox.log 2>&1'
dx 'cd ~/ws && colcon build > /tmp/build.log 2>&1'

LIGNES=()
mesure() {  # $1 : étape, $2 : capture, $3 : temps d'ouverture de la fenêtre
  sleep 20  # le temps de se stabiliser
  local rtf cpu mem vivants
  rtf=$(dx 't=$(gz topic -l | grep -m1 -E "^/world/[^/]+/stats$"); timeout 40 gz topic -e -t "$t" -n 20 2>/dev/null | awk "/real_time_factor/ {s += \$2; n++} END {if (n) printf \"%.2f\", s / n}"' || true)
  : > "$OUT/.stats"
  for _ in $(seq 1 8); do docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' "$C" >> "$OUT/.stats"; done
  cpu=$(awk '{gsub("%", "", $1); s += $1} END {printf "%.0f %%", s / NR}' "$OUT/.stats")
  mem=$(awk '{print $2}' "$OUT/.stats" | tail -1)
  vivants=$(dx 'for p in "[g]z sim -r" "[r]viz2" "[g]z sim -g" "[r]obot_state_publisher" "[p]arameter_bridge"; do pgrep -f -- "$p" >/dev/null && printf "%s, " "${p//[\[\]]/}"; done' || true)
  vncdo -s 127.0.0.1::5901 capture "$OUT/$2.png" 2>/dev/null || echo "capture impossible : $2"
  LIGNES+=("| $1 | ${rtf:-?} | $cpu | $mem | $3 | ${vivants%, } |")
  echo "$1 : temps réel ×${rtf:-?}, processeur $cpu, mémoire $mem, fenêtre $3"
}

# 1. la simulation du module Gazebo, sans fenêtre ; le robot tourne sur place pendant les mesures
fond 'cd ~/ws && source install/setup.bash && ros2 launch my_robot_description gazebo.launch.py > /tmp/gazebo.log 2>&1'
if ! demarrage=$(attendre 'gz topic -l | grep -qE "^/world/[^/]+/stats$" && ros2 topic list | grep -qx /scan' 180); then
  echo "La simulation n'a pas démarré"; tail -30 "$OUT/gazebo.log" 2>/dev/null || dx 'tail -30 /tmp/gazebo.log'; exit 1
fi
fond 'ros2 topic pub -r 2 /cmd_vel geometry_msgs/msg/Twist "{angular: {z: 0.3}}" > /dev/null 2>&1'
mesure "Gazebo seul (sans fenêtre)" 1-gazebo "démarrage : $demarrage"

# 2. + RViz2, avec sa configuration (modèle, laser, repères) et l'heure de la simulation
fond 'rviz2 -d ~/ws/robot.rviz --ros-args -p use_sim_time:=true > /tmp/rviz.log 2>&1'
fenetre=$(attendre 'xwininfo -root -tree | grep -q "RViz"' 180 || true)
mesure "+ RViz2" 2-rviz "$fenetre"

# 3. + la fenêtre de Gazebo
fond 'gz sim -g -v 2 > /tmp/gzgui.log 2>&1'
fenetre=$(attendre 'xwininfo -root -tree | grep -q "Gazebo"' 240 || true)
mesure "+ fenêtre de Gazebo" 3-gazebo-fenetre "$fenetre"

oom=$(docker inspect -f '{{.State.OOMKilled}}' "$C")
{
  echo "## Bureau du lab sous charge (${CPUS} processeur, ${MEM})"
  echo
  echo "| Étape | Temps réel (×) | Processeur | Mémoire | Fenêtre | Programmes en vie |"
  echo "|---|---|---|---|---|---|"
  printf '%s\n' "${LIGNES[@]}"
  echo
  echo "Temps réel : vitesse de la simulation par rapport à l'horloge (1,00 = temps réel). Processeur : 100 % = le processeur entier du lab."
  echo "Conteneur arrêté par manque de mémoire : $oom. Captures du bureau : artefact bureau-charge."
} > "$OUT/rapport.md"
cat "$OUT/rapport.md"
[ -n "${GITHUB_STEP_SUMMARY:-}" ] && cat "$OUT/rapport.md" >> "$GITHUB_STEP_SUMMARY"
exit 0

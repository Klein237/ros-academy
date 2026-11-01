#!/usr/bin/env bash
# Vérifie la correction : historique conservé, branche correction fusionnée dans main, dossier propre,
# et le nœud talker de nouveau sur /bavardage, messages numérotés.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
git rev-parse --git-dir > /dev/null 2>&1 || { echo "Ce dossier n'est plus un dépôt Git."; exit 1; }
for message in "Ajoute le package demo_pkg et le nœud talker" "Publie à 2 Hz" "Harmonise le nom des topics" \
               "Numérote les messages"; do
  if ! git log main --format=%s | grep -qxF "$message"; then
    echo "Le commit « $message » a disparu de main : corrigez par un nouveau commit, sans réécrire l'historique."
    exit 1
  fi
done
if ! git rev-parse --verify -q correction > /dev/null; then
  echo "Pas de branche correction : créez-la pour y faire la correction (git switch -c correction)."
  exit 1
fi
if [ "$(git rev-list --count main..correction)" != 0 ] || [ "$(git rev-list --count correction)" -le 4 ]; then
  echo "La branche correction n'a pas de nouveau commit fusionné dans main (git merge correction depuis main)."
  exit 1
fi
if [ "$(git symbolic-ref -q --short HEAD)" != main ]; then
  echo "Revenez sur la branche main (git switch main)."
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Des modifications ne sont pas commitées :"
  git status --short
  exit 1
fi
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 run demo_pkg talker > "$EXERCICE/check-node.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT
if ! out=$(timeout 20 ros2 topic echo --once /bavardage std_msgs/msg/String 2>&1); then
  echo "talker ne publie toujours pas sur /bavardage."
  exit 1
fi
if ! grep -q "Bonjour ROS 2 ! ([0-9]*)" <<<"$out"; then
  echo "talker publie sur /bavardage, mais les messages ne sont plus numérotés : le commit « Numérote les messages » a été défait."
  exit 1
fi
echo "Historique conservé, correction fusionnée, talker publie sur /bavardage : $(grep -o 'Bonjour ROS 2 ! ([0-9]*)' <<<"$out" | head -1)"

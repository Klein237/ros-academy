#!/usr/bin/env bash
# Crée le dépôt Git de l'équipe : quatre commits, dont le troisième casse le topic du robot.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
cd "$WS"
# les produits de compilation ne se versionnent pas
printf 'build/\ninstall/\nlog/\n' > .gitignore
T=src/demo_pkg/demo_pkg/talker.py
git init -q -b main
# identité de l'étudiant dans ce dépôt (le cours montre comment la régler pour tous ses dépôts)
git config user.name "Étudiant RoboForge"
git config user.email "etudiant@roboforge.local"
# commits de l'équipe, datés : le même historique pour tous
commit() {
  GIT_AUTHOR_NAME="$2" GIT_AUTHOR_EMAIL="$3" GIT_AUTHOR_DATE="$4" \
  GIT_COMMITTER_NAME="$2" GIT_COMMITTER_EMAIL="$3" GIT_COMMITTER_DATE="$4" \
    git commit -q -m "$1"
}
git add -A
commit "Ajoute le package demo_pkg et le nœud talker" "Awa Diallo" "awa@livraison.local" "2026-09-01T09:00:00+02:00"
sed -i "s/create_timer(1.0, self.parler)/create_timer(0.5, self.parler)/" "$T"
git add "$T"
commit "Publie à 2 Hz" "Karim Benali" "karim@livraison.local" "2026-09-03T14:20:00+02:00"
sed -i "s/^TOPIC = 'bavardage'$/TOPIC = 'bavardages'/" "$T"
git add "$T"
commit "Harmonise le nom des topics" "Karim Benali" "karim@livraison.local" "2026-09-08T11:05:00+02:00"
python3 - "$T" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s = s.replace("        self.create_timer(", "        self.count = 0\n        self.create_timer(", 1)
s = s.replace("        msg = String(data='Bonjour ROS 2 !')",
              "        self.count += 1\n        msg = String(data=f'Bonjour ROS 2 ! ({self.count})')", 1)
open(p, "w", encoding="utf-8").write(s)
PY
git add "$T"
commit "Numérote les messages" "Awa Diallo" "awa@livraison.local" "2026-09-10T16:40:00+02:00"
colcon build --symlink-install > "$EXERCICE/setup.log" 2>&1
echo "Dépôt prêt : $WS ($(git rev-list --count HEAD) commits sur main)"

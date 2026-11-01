#!/usr/bin/env bash
# Rejoue les commandes du cours : dépôt, commit, historique, branche, fusion.
set -e
git config --global user.name "Test RoboForge"
git config --global user.email "test@roboforge.local"
git init -q -b main
printf 'build/\ninstall/\nlog/\n' > .gitignore
mkdir -p src build && echo "print('bonjour')" > src/noeud.py && touch build/produit
git add -A                                     # build/ est ignoré
git commit -q -m "Ajoute le package demo_pkg"
[ -z "$(git status --porcelain)" ]                        # build/ est ignoré
git switch -q -c correction
echo "print('bonjour ROS 2')" > src/noeud.py
git commit -qam "Rétablit le message"
git switch -q main
git merge -q correction
[ "$(git log --oneline | wc -l)" = 2 ] && git log --format=%s | grep -qx "Rétablit le message"
git revert --no-edit HEAD > /dev/null && grep -qx "print('bonjour')" src/noeud.py
echo "dépôt, commits, branche, fusion et revert : ok"

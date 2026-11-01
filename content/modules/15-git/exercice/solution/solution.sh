#!/usr/bin/env bash
# Solution, rejouée par la CI dans le workspace : une branche, l'annulation du commit fautif, la fusion.
set -euo pipefail
fautif=$(git log --format='%h %s' | awk '/Harmonise le nom des topics/ {print $1}')
git switch -q -c correction
git revert --no-edit "$fautif" > /dev/null
git switch -q main
git merge -q --no-edit correction

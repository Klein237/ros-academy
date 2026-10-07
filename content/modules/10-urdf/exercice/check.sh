#!/usr/bin/env bash
# Vérifie que la description Xacro produit un URDF valide, avec tous les links du robot.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
X=src/my_robot_description/urdf/my_robot.urdf.xacro
if ! xacro "$X" > "$EXERCICE/robot.urdf" 2> "$EXERCICE/xacro.log"; then
  echo "xacro échoue : $(head -3 "$EXERCICE/xacro.log")"
  exit 1
fi
if ! check_urdf "$EXERCICE/robot.urdf" > "$EXERCICE/check_urdf.log" 2>&1; then
  echo "check_urdf refuse la description :"
  grep -i "error" "$EXERCICE/check_urdf.log" | head -3
  exit 1
fi
for link in base_link chassis left_wheel right_wheel caster_wheel; do
  if ! grep -q "$link" "$EXERCICE/check_urdf.log"; then
    echo "Le link $link manque dans l'arbre du robot."
    exit 1
  fi
done
echo "Description valide : $(grep 'root Link' "$EXERCICE/check_urdf.log")"

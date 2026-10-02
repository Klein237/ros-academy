# Environnement ROS 2 de l'étudiant (sourcé par tous les shells)
source /opt/ros/jazzy/setup.bash
# Découverte DDS limitée au conteneur (remplace ROS_LOCALHOST_ONLY depuis Jazzy)
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_DOMAIN_ID=0
# Bureau graphique du lab (Lab UI → « Bureau ») : écran virtuel, rendu OpenGL logiciel
export DISPLAY=:1
export LIBGL_ALWAYS_SOFTWARE=1
export QT_X11_NO_MITSHM=1
# Gazebo (gz sim) : ses messages restent dans le conteneur, comme ceux de ROS
export GZ_IP=127.0.0.1

# Programmes graphiques : l'écran du lab n'existe qu'une fois le Bureau ouvert dans le Lab UI
_academy_bureau() {
  if ! xdpyinfo >/dev/null 2>&1; then
    echo "L'écran du lab n'est pas démarré : cliquez sur « Bureau (RViz, Gazebo) » en haut du lab, puis relancez la commande." >&2
    return 1
  fi
}
for _prog in rviz2 rqt; do
  eval "$_prog() { _academy_bureau && command $_prog \"\$@\"; }"
done
unset _prog

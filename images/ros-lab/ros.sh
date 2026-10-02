# Environnement ROS 2 de l'étudiant (sourcé par tous les shells)
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=0
# Bureau graphique du lab (Lab UI → « Bureau ») : écran virtuel, rendu OpenGL logiciel
export DISPLAY=:1
export LIBGL_ALWAYS_SOFTWARE=1
export QT_X11_NO_MITSHM=1

#!/usr/bin/env bash
# Bureau graphique du lab : écran X virtuel :1 (Xvnc, sans GPU) avec le gestionnaire de fenêtres
# openbox, servi en WebSocket par websockify sur le port donné par jupyter-server-proxy
# (/user/<nom>/bureau/, accès authentifié). Les applications lancées dans les terminaux
# (DISPLAY=:1, voir /etc/profile.d/ros.sh) s'y affichent : rviz2, gazebo…
set -euo pipefail
PORT=${1:?usage : academy-bureau PORT}
export DISPLAY=:1

# écran laissé par un bureau précédent dont le serveur X ne tourne plus
if [ -e /tmp/.X1-lock ] && ! kill -0 "$(tr -dc '0-9' </tmp/.X1-lock)" 2>/dev/null; then
  rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
fi
if ! xdpyinfo >/dev/null 2>&1; then
  # VNC sans mot de passe mais seulement en local : seul websockify (derrière le proxy) s'y connecte
  Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost=1 -rfbport 5901 \
    -AlwaysShared=1 -AcceptSetDesktopSize=1 -nolisten tcp -desktop "Lab ROS 2" \
    >/tmp/bureau-xvnc.log 2>&1 &
  for _ in $(seq 1 100); do
    xdpyinfo >/dev/null 2>&1 && break
    sleep 0.1
  done
  xdpyinfo >/dev/null 2>&1 || { cat /tmp/bureau-xvnc.log >&2; exit 1; }
  xsetroot -solid '#1b1f24' || true
  openbox >/tmp/bureau-openbox.log 2>&1 &
fi
exec websockify 127.0.0.1:"$PORT" 127.0.0.1:5901

FROM ros:jazzy-ros-base-noble

ARG JUPYTERHUB_VERSION=5.2.1
ENV DEBIAN_FRONTEND=noninteractive \
    ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    ROS_DOMAIN_ID=0

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3-pip python3-venv python3-colcon-common-extensions build-essential \
      ros-jazzy-rosbridge-suite ros-jazzy-demo-nodes-py ros-jazzy-demo-nodes-cpp \
      ros-jazzy-action-tutorials-py ros-jazzy-xacro ros-jazzy-joint-state-publisher \
      ros-jazzy-joint-state-publisher-gui ros-jazzy-rviz2 ros-jazzy-ros-gz liburdfdom-tools \
      tigervnc-standalone-server python3-websockify openbox x11-utils x11-xserver-utils \
      libgl1-mesa-dri libegl-mesa0 fonts-dejavu-core \
      nano vim-tiny less \
 && SUDO_FORCE_REMOVE=yes apt-get purge -y --auto-remove sudo \
 && rm -rf /var/lib/apt/lists/*

# Serveur Jupyter dans son propre environnement Python (Ubuntu 24.04 refuse pip dans le système) :
# le python3 des étudiants reste celui de ROS. Seul jupyterhub-singleuser est mis dans le PATH.
RUN python3 -m venv /opt/jupyter \
 && /opt/jupyter/bin/pip install --no-cache-dir \
      "jupyterhub==${JUPYTERHUB_VERSION}" \
      "jupyter-server==2.14.2" \
      "jupyter-server-proxy==4.4.0" \
      "terminado==0.18.1" \
 && ln -s /opt/jupyter/bin/jupyterhub-singleuser /usr/local/bin/jupyterhub-singleuser

COPY ros.sh /etc/profile.d/ros.sh
COPY academy_diffbot.py /usr/local/bin/academy-diffbot
COPY academy_bureau.sh /usr/local/bin/academy-bureau
COPY jupyter_server_config.py /etc/jupyter/jupyter_server_config.py
# L'image Ubuntu 24.04 a déjà un utilisateur « ubuntu » en uid 1000 : il laisse la place à « etudiant »
RUN echo 'source /etc/profile.d/ros.sh' >> /etc/bash.bashrc \
 && (userdel -r ubuntu 2>/dev/null || true) \
 && useradd --create-home --uid 1000 --shell /bin/bash etudiant

USER etudiant
WORKDIR /home/etudiant
CMD ["jupyterhub-singleuser"]

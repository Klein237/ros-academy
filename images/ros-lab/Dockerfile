FROM ros:humble-ros-base-jammy

ARG JUPYTERHUB_VERSION=5.2.1
ENV DEBIAN_FRONTEND=noninteractive \
    ROS_LOCALHOST_ONLY=1 \
    ROS_DOMAIN_ID=0

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3-pip python3-colcon-common-extensions build-essential \
      ros-humble-rosbridge-suite ros-humble-demo-nodes-py ros-humble-demo-nodes-cpp \
      nano vim-tiny less \
 && SUDO_FORCE_REMOVE=yes apt-get purge -y --auto-remove sudo \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
      "jupyterhub==${JUPYTERHUB_VERSION}" \
      "jupyter-server==2.14.2" \
      "jupyter-server-proxy==4.4.0" \
      "terminado==0.18.1"

COPY ros.sh /etc/profile.d/ros.sh
COPY jupyter_server_config.py /etc/jupyter/jupyter_server_config.py
RUN echo 'source /etc/profile.d/ros.sh' >> /etc/bash.bashrc \
 && useradd --create-home --uid 1000 --shell /bin/bash etudiant

USER etudiant
WORKDIR /home/etudiant
CMD ["jupyterhub-singleuser"]

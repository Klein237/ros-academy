FROM quay.io/jupyterhub/jupyterhub:5.2.1
COPY requirements.txt /srv/hub/requirements.txt
RUN pip install --no-cache-dir -r /srv/hub/requirements.txt
COPY rosacademy_hub /srv/hub/rosacademy_hub
COPY jupyterhub_config.py /srv/hub/jupyterhub_config.py
ENV PYTHONPATH=/srv/hub
RUN mkdir -p /srv/hub/data
WORKDIR /srv/hub
CMD ["jupyterhub", "-f", "/srv/hub/jupyterhub_config.py"]

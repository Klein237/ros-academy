# Service Contenus : site, API publique et éditeur. Contexte de construction : racine du dépôt.
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
COPY contenus/requirements.txt /srv/app/requirements.txt
RUN pip install --no-cache-dir -r /srv/app/requirements.txt
COPY contenus/academy_content /srv/app/academy_content
# Contenu initial, copié dans le dépôt de contenu au premier démarrage
COPY content /srv/seed
WORKDIR /srv/app
ENV CONTENT_ROOT=/srv/contenus CONTENT_SEED=/srv/seed PYTHONUNBUFFERED=1
EXPOSE 8200
# Pas de journal d'accès : il contiendrait le jeton de /admin/login?token=…
CMD ["uvicorn", "academy_content.app:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8200", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]

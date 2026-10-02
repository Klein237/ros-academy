# Service Comptes : connexion, quotas de lab, progression et notes.
FROM python:3.12-slim
COPY requirements.txt /srv/app/requirements.txt
RUN pip install --no-cache-dir -r /srv/app/requirements.txt
COPY alembic.ini /srv/app/alembic.ini
COPY migrations /srv/app/migrations
COPY academy_comptes /srv/app/academy_comptes
WORKDIR /srv/app
ENV PYTHONUNBUFFERED=1
RUN useradd --system --uid 10001 comptes
USER comptes
EXPOSE 8300
# Migrations, puis le service. Pas de journal d'accès : il contiendrait les liens
# de connexion (/connexion/email/<jeton>) et les codes OAuth.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn academy_comptes.app:app_from_env --factory --host 0.0.0.0 --port 8300 --proxy-headers --forwarded-allow-ips '*' --no-access-log"]

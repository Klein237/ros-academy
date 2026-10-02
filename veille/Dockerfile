# Veille du serveur : CPU, mémoire, disque et services ; alertes par e-mail.
FROM python:3.12-slim
COPY veille.py /srv/veille/veille.py
RUN useradd --system --uid 10002 veille
USER veille
ENV PYTHONUNBUFFERED=1
CMD ["python", "/srv/veille/veille.py"]

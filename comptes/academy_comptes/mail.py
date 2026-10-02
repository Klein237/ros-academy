"""Envoi du lien de connexion. Sans SMTP configuré, le lien est écrit dans les journaux."""

import logging
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("comptes.mail")


def send_login_link(settings, email, link):
    msg = EmailMessage()
    msg["Subject"] = "Votre lien de connexion à ROS Academy"
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.set_content(
        "Bonjour,\n\n"
        "Pour vous connecter à ROS Academy, ouvrez ce lien (valable 15 minutes, une seule fois) :\n\n"
        f"{link}\n\n"
        "Si vous n'avez rien demandé, ignorez ce message.\n"
    )
    if not settings.smtp_host:
        # Développement : pas de serveur d'envoi, le lien est lisible dans les journaux.
        log.warning("SMTP non configuré — lien de connexion pour %s : %s", email, link)
        return
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, 465, context=context, timeout=20) as smtp:
            _send(smtp, settings, msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls(context=context)
            _send(smtp, settings, msg)


def _send(smtp, settings, msg):
    if settings.smtp_user:
        smtp.login(settings.smtp_user, settings.smtp_password)
    smtp.send_message(msg)

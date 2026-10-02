"""Envoi du lien de connexion. Sans SMTP configuré, le lien est écrit dans les journaux.

Tester la configuration SMTP : docker compose exec comptes python -m academy_comptes.mail vous@exemple.fr
"""

import logging
import smtplib
import ssl
import sys
from email.message import EmailMessage

log = logging.getLogger("comptes.mail")


def _message(settings, email, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.set_content(body)
    return msg


def send_login_link(settings, email, link):
    msg = _message(
        settings, email, "Votre lien de connexion à ROS Academy",
        "Bonjour,\n\n"
        "Pour vous connecter à ROS Academy, ouvrez ce lien (valable 15 minutes, une seule fois) :\n\n"
        f"{link}\n\n"
        "Si vous n'avez rien demandé, ignorez ce message.\n",
    )
    if not settings.smtp_host:
        # Développement : pas de serveur d'envoi, le lien est lisible dans les journaux.
        log.warning("SMTP non configuré — lien de connexion pour %s : %s", email, link)
        return
    deliver(settings, msg)


def deliver(settings, msg):
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


def main(argv=None, settings=None):
    """Envoie un e-mail de test avec la configuration SMTP de l'environnement."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or "@" not in argv[0]:
        print("usage : python -m academy_comptes.mail adresse@exemple.fr")
        return 2
    if settings is None:
        from .settings import Settings

        settings = Settings.from_env()
    if not settings.smtp_host:
        print("SMTP_HOST est vide : aucun e-mail n'est envoyé (les liens de connexion sont dans les journaux).")
        return 1
    print(f"Envoi par {settings.smtp_host}:{settings.smtp_port} (utilisateur : {settings.smtp_user or 'aucun'}, "
          f"expéditeur : {settings.smtp_from})…")
    msg = _message(settings, argv[0], "ROS Academy : test d'envoi",
                   "Ce message confirme que ROS Academy peut envoyer des e-mails (liens de connexion, alertes).\n")
    try:
        deliver(settings, msg)
    except (OSError, smtplib.SMTPException) as exc:
        print(f"Échec : {exc.__class__.__name__} : {exc}")
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            print("Identifiants refusés. Avec Gmail, utilisez un « mot de passe d'application », pas votre mot de passe.")
        return 1
    print(f"E-mail de test envoyé à {argv[0]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

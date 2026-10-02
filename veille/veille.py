"""Veille du serveur : CPU, mémoire, disque et santé des services ; alertes par e-mail.

Bibliothèque standard seulement. Configuration par l'environnement :

- VEILLE_PROC (/host/proc), VEILLE_DISQUES (/host/root ; plusieurs chemins séparés par des virgules) ;
- VEILLE_SEUIL_CPU, VEILLE_SEUIL_MEMOIRE, VEILLE_SEUIL_DISQUE (80) ; retour à la normale 5 points en dessous ;
- VEILLE_SERVICES : « nom=url,nom=url » vérifiés en HTTP (200-399 attendu) ;
- VEILLE_INTERVALLE (15 s), VEILLE_FENETRE_CPU (300 s), VEILLE_RAPPEL (21600 s) ;
- ADMIN_EMAILS, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, DOMAIN.
"""

import logging
import os
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from email.message import EmailMessage

log = logging.getLogger("veille")
HYSTERESIS = 5.0  # points de pourcentage sous le seuil pour revenir à la normale
SERVICE_FAILURES = 3  # échecs consécutifs avant l'alerte


# --- Mesures

def read_cpu(proc):
    """(temps actif, temps total) cumulés depuis le démarrage, d'après la ligne « cpu » de /proc/stat."""
    with open(os.path.join(proc, "stat")) as f:
        fields = [int(x) for x in f.readline().split()[1:]]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
    total = sum(fields[:8])  # sans guest (déjà compté dans user)
    return total - idle, total


def read_memory_percent(proc):
    info = {}
    with open(os.path.join(proc, "meminfo")) as f:
        for line in f:
            key, _, value = line.partition(":")
            info[key] = int(value.split()[0])
    return 100.0 * (1 - info["MemAvailable"] / info["MemTotal"])


def read_disk_percent(path):
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize  # place réellement disponible (hors réserve root)
    used = total - st.f_bfree * st.f_frsize
    return 100.0 * used / (used + free) if used + free else 0.0


def check_http(url, timeout=5):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
            return 200 <= r.status < 400, f"HTTP {r.status}"
    except urllib.error.HTTPError as exc:
        return exc.code < 400, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - refus de connexion, délai, DNS
        return False, exc.__class__.__name__


class CpuWindow:
    """Utilisation moyenne du CPU sur une fenêtre glissante."""

    def __init__(self, seconds):
        self.seconds = seconds
        self.samples = deque()  # (instant, actif, total)

    def add(self, now, active, total):
        self.samples.append((now, active, total))
        while len(self.samples) > 2 and now - self.samples[1][0] >= self.seconds:
            self.samples.popleft()

    def percent(self):
        """None tant que la fenêtre n'est pas remplie (évite une alerte au démarrage)."""
        if len(self.samples) < 2:
            return None
        (t0, a0, n0), (t1, a1, n1) = self.samples[0], self.samples[-1]
        if t1 - t0 < self.seconds * 0.9 or n1 == n0:
            return None
        return 100.0 * (a1 - a0) / (n1 - n0)


# --- Alertes

@dataclass
class Alarm:
    """Une condition surveillée : entrée, rappel, sortie."""

    name: str
    active: bool = False
    since: float = 0.0
    last_sent: float = 0.0
    failures: int = 0
    detail: str = ""


@dataclass
class Settings:
    proc: str = "/host/proc"
    disks: tuple = ("/host/root",)
    cpu: float = 80.0
    memory: float = 80.0
    disk: float = 80.0
    services: dict = field(default_factory=dict)
    interval: float = 15.0
    cpu_window: float = 300.0
    reminder: float = 6 * 3600.0
    admins: tuple = ()
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "ROS Academy <no-reply@localhost>"
    domain: str = "localhost"

    @classmethod
    def from_env(cls, env=os.environ):
        def services(value):
            out = {}
            for part in (value or "").split(","):
                name, sep, url = part.strip().partition("=")
                if sep and name and url:
                    out[name] = url
            return out

        domain = env.get("DOMAIN", "localhost")
        return cls(
            proc=env.get("VEILLE_PROC", "/host/proc"),
            disks=tuple(p for p in env.get("VEILLE_DISQUES", "/host/root").split(",") if p),
            cpu=float(env.get("VEILLE_SEUIL_CPU", "80")),
            memory=float(env.get("VEILLE_SEUIL_MEMOIRE", "80")),
            disk=float(env.get("VEILLE_SEUIL_DISQUE", "80")),
            services=services(env.get("VEILLE_SERVICES", "")),
            interval=float(env.get("VEILLE_INTERVALLE", "15")),
            cpu_window=float(env.get("VEILLE_FENETRE_CPU", "300")),
            reminder=float(env.get("VEILLE_RAPPEL", str(6 * 3600))),
            admins=tuple(e.strip() for e in env.get("ADMIN_EMAILS", "").split(",") if e.strip()),
            smtp_host=env.get("SMTP_HOST", ""),
            smtp_port=int(env.get("SMTP_PORT") or "587"),
            smtp_user=env.get("SMTP_USER", ""),
            smtp_password=env.get("SMTP_PASSWORD", ""),
            smtp_from=env.get("SMTP_FROM") or f"ROS Academy <no-reply@{domain}>",
            domain=domain,
        )


def send_mail(settings, subject, body):
    """E-mail aux administrateurs ; sans SMTP ou sans destinataire, l'alerte reste dans le journal."""
    if not settings.smtp_host or not settings.admins:
        log.warning("E-mail d'alerte non envoyé (SMTP_HOST ou ADMIN_EMAILS vide) : %s", subject)
        return
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, settings.smtp_from, ", ".join(settings.admins)
    msg.set_content(body)
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        server.starttls(context=context)
    with server:
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


class Watch:
    def __init__(self, settings, mailer=send_mail, http=check_http, clock=time.time):
        self.s = settings
        self.mailer = mailer
        self.http = http
        self.clock = clock
        self.cpu = CpuWindow(settings.cpu_window)
        self.alarms = {}

    def _notify(self, subject, body):
        try:
            self.mailer(self.s, subject, body)
        except Exception as exc:  # noqa: BLE001 - un SMTP en panne ne doit pas arrêter la veille
            log.error("Envoi de l'alerte impossible (%s) : %s", exc.__class__.__name__, subject)

    def _level(self, name, value, threshold, unit_label):
        """Mesure en pourcentage : alerte au-dessus du seuil, fin sous le seuil moins l'hystérésis."""
        alarm = self.alarms.setdefault(name, Alarm(name))
        now = self.clock()
        alarm.detail = f"{unit_label} à {value:.0f} % (seuil {threshold:.0f} %)"
        if not alarm.active and value >= threshold:
            alarm.active, alarm.since, alarm.last_sent = True, now, now
            log.warning("ALERTE %s", alarm.detail)
            self._notify(f"[ROS Academy] Alerte : {alarm.detail}", self._body(alarm.detail))
        elif alarm.active and value < threshold - HYSTERESIS:
            alarm.active = False
            log.info("RETOUR À LA NORMALE %s", alarm.detail)
            self._notify(f"[ROS Academy] Retour à la normale : {unit_label}",
                         self._body(f"{alarm.detail}, après {self._duration(now - alarm.since)}."))
        elif alarm.active and now - alarm.last_sent >= self.s.reminder:
            alarm.last_sent = now
            log.warning("ALERTE (rappel) %s", alarm.detail)
            self._notify(f"[ROS Academy] Toujours en alerte : {alarm.detail}",
                         self._body(f"{alarm.detail}, depuis {self._duration(now - alarm.since)}."))

    def _service(self, name, ok, detail):
        alarm = self.alarms.setdefault(f"service:{name}", Alarm(name))
        now = self.clock()
        if ok:
            if alarm.active:
                log.info("RETOUR À LA NORMALE service %s", name)
                self._notify(f"[ROS Academy] Service rétabli : {name}",
                             self._body(f"Le service {name} répond de nouveau, après "
                                        f"{self._duration(now - alarm.since)} d'interruption."))
            alarm.active, alarm.failures = False, 0
            return
        alarm.failures += 1
        alarm.detail = f"service {name} injoignable ({detail})"
        if not alarm.active and alarm.failures >= SERVICE_FAILURES:
            alarm.active, alarm.since, alarm.last_sent = True, now, now
            log.warning("ALERTE %s", alarm.detail)
            self._notify(f"[ROS Academy] Alerte : {alarm.detail}", self._body(alarm.detail))
        elif alarm.active and now - alarm.last_sent >= self.s.reminder:
            alarm.last_sent = now
            log.warning("ALERTE (rappel) %s", alarm.detail)
            self._notify(f"[ROS Academy] Toujours en alerte : {alarm.detail}", self._body(alarm.detail))

    def _body(self, text):
        return (f"{text}\n\nServeur : {self.s.domain}\n"
                f"Journaux : https://{self.s.domain}/admin/journaux/\n")

    @staticmethod
    def _duration(seconds):
        minutes = int(seconds // 60)
        return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"

    def tick(self):
        now = self.clock()
        try:
            self.cpu.add(now, *read_cpu(self.s.proc))
            cpu = self.cpu.percent()
            if cpu is not None:
                self._level("cpu", cpu, self.s.cpu, "CPU")
            self._level("memoire", read_memory_percent(self.s.proc), self.s.memory, "mémoire")
        except (OSError, ValueError, KeyError) as exc:
            log.error("Lecture de %s impossible : %s", self.s.proc, exc)
        for path in self.s.disks:
            try:
                label = "disque" if len(self.s.disks) == 1 else f"disque {path}"
                self._level(f"disque:{path}", read_disk_percent(path), self.s.disk, label)
            except OSError as exc:
                log.error("Lecture du disque %s impossible : %s", path, exc)
        for name, url in self.s.services.items():
            self._service(name, *self.http(url))


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    settings = Settings.from_env()
    log.info("Veille démarrée : CPU %s %%, mémoire %s %%, disque %s %% ; services : %s ; alertes à %s",
             settings.cpu, settings.memory, settings.disk, ", ".join(settings.services) or "aucun",
             ", ".join(settings.admins) or "personne (ADMIN_EMAILS vide)")
    watch = Watch(settings)
    while True:
        watch.tick()
        time.sleep(settings.interval)


if __name__ == "__main__":
    main()

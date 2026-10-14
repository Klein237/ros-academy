#!/usr/bin/env python3
"""Simule « docker compose up » du robot de livraison, sans Docker (le lab n'en a pas).

    python3 simuler_compose.py <dossier du compose.yaml>

Chaque service est lancé comme un processus, avec sa commande (command) et ses variables
(environment, env_file), dans un environnement neuf où ROS 2 et le workspace du dossier sont
chargés (le rôle du point d'entrée de l'image). Le service qui écoute /etat (ros2 topic echo)
est lancé en dernier : la simulation réussit s'il reçoit l'état publié par le robot.

Les domaines ROS sont remplacés par des domaines libres, en gardant leurs égalités et leurs
différences : la simulation ne voit pas les nœuds lancés dans le lab.
"""
import os
import random
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

ATTENDU = "en service"
ATTENTE_S = 20


def variables(service, dossier):
    """environment (liste ou dictionnaire) et env_file, comme Docker Compose."""
    env = {}
    fichiers = service.get("env_file") or []
    for nom in [fichiers] if isinstance(fichiers, str) else fichiers:
        chemin = dossier / (nom["path"] if isinstance(nom, dict) else nom)
        if not chemin.is_file():
            raise ValueError(f"env_file : {chemin.name} introuvable")
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                env[cle.strip()] = valeur.strip().strip('"').strip("'")
    brut = service.get("environment") or {}
    if isinstance(brut, list):
        brut = dict(e.split("=", 1) if "=" in e else (e, "") for e in brut)
    env.update({str(k): "" if v is None else str(v) for k, v in brut.items()})
    return env


def commande(service):
    cmd = service.get("command")
    if not cmd:
        return None
    return " ".join(shlex.quote(str(c)) for c in cmd) if isinstance(cmd, list) else str(cmd)


def lancer(nom, cmd, env, dossier, tmp):
    install = dossier / "install" / "setup.bash"
    script = f'source "/opt/ros/$ROS_DISTRO/setup.bash" && source "{install}" && exec {cmd}'
    base = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": tmp, "LANG": "C.UTF-8", "ROS_DISTRO": "jazzy", "PYTHONUNBUFFERED": "1",
        "ROS_LOG_DIR": os.path.join(tmp, "log", nom),
    }
    return subprocess.Popen(["bash", "-c", script], cwd=dossier, env={**base, **env},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)


def arreter(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGINT)
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def main():
    dossier = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    fichier = next((dossier / n for n in ("compose.yaml", "compose.yml", "docker-compose.yml")
                    if (dossier / n).is_file()), None)
    if not fichier:
        print(f"Pas de compose.yaml dans {dossier}.")
        return 1
    try:
        compose = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"{fichier.name} n'est pas un YAML valide : {exc}")
        return 1
    services = compose.get("services") or {}
    if not isinstance(services, dict) or not services:
        print(f"{fichier.name} ne déclare aucun service (clé services).")
        return 1

    try:
        envs = {nom: variables(s or {}, dossier) for nom, s in services.items()}
    except ValueError as exc:
        print(exc)
        return 1
    cmds = {nom: commande(s or {}) for nom, s in services.items()}
    observateurs = [n for n, c in cmds.items() if c and "topic echo" in c and "/etat" in c]
    if not observateurs:
        print("Aucun service n'écoute /etat (ros2 topic echo /etat) : remettez le service supervision.")
        return 1
    observateur = observateurs[0]

    # DDS : sur la même machine, tous en réseau host, ou tous sur le réseau du projet Compose
    reseaux = {n: (s or {}).get("network_mode", "réseau du projet") for n, s in services.items()}
    if len(set(reseaux.values())) > 1:
        detail = ", ".join(f"{n} : {r}" for n, r in reseaux.items())
        print(f"Les services ne sont pas sur le même réseau ({detail}) : DDS ne peut pas les faire se découvrir.")
        return 1

    originaux = {n: env.get("ROS_DOMAIN_ID", "0 (absent)") for n, env in envs.items()}
    # domaines libres, en gardant les égalités et les différences du fichier
    base = random.randint(120, 200)
    correspondance = {}
    for nom, env in envs.items():
        d = env.get("ROS_DOMAIN_ID", "0")
        correspondance.setdefault(d, str(base + len(correspondance)))
        env["ROS_DOMAIN_ID"] = correspondance[d]

    print("$ docker compose up    (simulé)")
    for nom in services:
        print(f"  {nom} : {cmds[nom] or '(commande de l’image)'}  ·  ROS_DOMAIN_ID={originaux[nom]}")
    procs = []
    with tempfile.TemporaryDirectory(prefix="compose-") as tmp:
        try:
            for nom, cmd in cmds.items():
                if nom != observateur and cmd:
                    procs.append(lancer(nom, cmd, envs[nom], dossier, tmp))
            time.sleep(2)
            obs = lancer(observateur, cmds[observateur], envs[observateur], dossier, tmp)
            procs.append(obs)
            lignes, recu = [], False
            debut = time.monotonic()
            os.set_blocking(obs.stdout.fileno(), False)
            while time.monotonic() - debut < ATTENTE_S:
                ligne = obs.stdout.readline()
                if ligne:
                    lignes.append(ligne.rstrip())
                    if ATTENDU in ligne:
                        recu = True
                        break
                elif obs.poll() is not None:
                    break
                else:
                    time.sleep(0.1)
        finally:
            for p in procs:
                arreter(p)
        for ligne in lignes[-6:]:
            print(f"  {observateur}  | {ligne}")
        if recu:
            print(f"Le service {observateur} reçoit l'état publié par le robot.")
            return 0
        print(f"Le service {observateur} n'a rien reçu sur /etat en {ATTENTE_S} s.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

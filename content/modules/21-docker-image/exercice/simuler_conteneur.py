#!/usr/bin/env python3
"""Simule « docker run » de l'image du robot, sans Docker (le lab n'en a pas).

    python3 simuler_conteneur.py <dossier du Dockerfile>

Le Dockerfile est lu comme Docker le ferait pour la dernière étape : son point d'entrée
(ENTRYPOINT), sa commande (CMD), ses variables (ENV), son dossier de travail (WORKDIR) et les
fichiers qu'elle copie. Le point d'entrée et la commande sont ensuite lancés avec l'environnement
d'un conteneur neuf (aucun « source » déjà fait). Le workspace compilé dans l'image, /ws/install,
est remplacé par celui du dossier (compilé avec colcon build) ; ROS 2 est celui du lab (/opt/ros).

Code de sortie 0 : le robot démarre (« Robot de livraison prêt » dans sa sortie).
"""
import json
import os
import random
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PRET = "Robot de livraison prêt"
ATTENTE_S = 25

# /ros_entrypoint.sh des images officielles ros:* : ROS seulement, sans aucun workspace
ENTREE_OFFICIELLE = """#!/bin/bash
set -e
source "/opt/ros/$ROS_DISTRO/setup.bash" --
exec "$@"
"""


def instructions(texte):
    """[(INSTRUCTION, arguments)] : lignes de continuation jointes, commentaires retirés."""
    out, courant = [], ""
    for ligne in texte.splitlines():
        if not courant and ligne.strip().startswith("#"):
            continue
        if ligne.rstrip().endswith("\\"):
            courant += ligne.rstrip()[:-1] + " "
            continue
        courant += ligne
        if courant.strip():
            mot, _, reste = courant.strip().partition(" ")
            out.append((mot.upper(), reste.strip()))
        courant = ""
    return out


def forme(arguments):
    """Forme exec (["a", "b"]) ou forme shell (a b → /bin/sh -c "a b")."""
    if arguments.startswith("["):
        try:
            valeur = json.loads(arguments)
            if isinstance(valeur, list) and all(isinstance(v, str) for v in valeur):
                return valeur
        except json.JSONDecodeError:
            pass
        raise ValueError(f"forme exec illisible : {arguments}")
    return ["/bin/sh", "-c", arguments]


def lire_env(arguments):
    mots = shlex.split(arguments)
    if mots and "=" not in mots[0]:
        return {mots[0]: " ".join(mots[1:])}
    return dict(m.split("=", 1) for m in mots if "=" in m)


def etapes(texte):
    """Les étapes du Dockerfile, chacune résolue : héritage d'une étape précédente ou d'une image ros:*."""
    resolues, courante = {}, None
    liste = []
    for ins, args in instructions(texte):
        if ins == "FROM":
            mots = args.split()
            base = mots[0]
            nom = mots[2] if len(mots) >= 3 and mots[1].upper() == "AS" else str(len(liste))
            parent = resolues.get(base)
            if parent:
                courante = {k: (v.copy() if isinstance(v, dict) else v) for k, v in parent.items()}
            else:
                officielle = base.startswith(("ros:", "osrf/ros:"))
                courante = {
                    "env": {"ROS_DISTRO": "jazzy"} if officielle else {},
                    "fichiers": {}, "entree": ["/ros_entrypoint.sh"] if officielle else [],
                    "cmd": ["bash"], "workdir": "/", "install": None, "compile": False,
                }
            courante["nom"], courante["base"] = nom, base
            resolues[nom] = courante
            liste.append(courante)
            continue
        if courante is None:
            continue  # ARG avant le premier FROM
        if ins == "ENV":
            courante["env"].update(lire_env(args))
        elif ins == "WORKDIR":
            courante["workdir"] = os.path.join(courante["workdir"], args)
        elif ins == "ENTRYPOINT":
            courante["entree"] = forme(args)
            courante["cmd"] = []  # un nouveau point d'entrée efface la commande héritée
        elif ins == "CMD":
            courante["cmd"] = forme(args)
        elif ins == "RUN" and "colcon build" in args:
            courante["compile"] = courante["workdir"].rstrip("/") == "/ws"
        elif ins == "COPY":
            mots = shlex.split(args)
            options = {m.split("=", 1)[0]: m.split("=", 1)[1] for m in mots if m.startswith("--") and "=" in m}
            reste = [m for m in mots if not m.startswith("--")]
            if len(reste) < 2:
                continue
            *sources, dest = reste
            if not dest.startswith("/"):
                dest = os.path.join(courante["workdir"], dest)
            depuis = options.get("--from")
            if depuis:
                etape = resolues.get(depuis)
                if etape and etape["compile"] and sources == ["/ws/install"]:
                    courante["install"] = dest.rstrip("/")
            elif len(sources) == 1:
                cible = dest + os.path.basename(sources[0]) if dest.endswith("/") else dest
                courante["fichiers"][cible] = sources[0]
    return liste


def main():
    dossier = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    dockerfile = dossier / "Dockerfile"
    if not dockerfile.is_file():
        print(f"Pas de Dockerfile dans {dossier}.")
        return 1
    try:
        liste = etapes(dockerfile.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"Dockerfile : {exc}")
        return 1
    if not liste:
        print("Le Dockerfile ne contient aucune étape FROM.")
        return 1
    if not any(e["compile"] for e in liste):
        print("Aucune étape ne compile le workspace dans /ws (WORKDIR /ws puis RUN … colcon build).")
        return 1
    image = liste[-1]
    install = dossier / "install"

    def hote(chemin):
        """Chemin dans l'image → chemin dans le lab."""
        if image["install"] and (chemin == image["install"] or chemin.startswith(image["install"] + "/")):
            return str(install) + chemin[len(image["install"]):]
        return chemin

    def remplace(texte):
        if image["install"]:
            texte = texte.replace(image["install"], str(install))
        return texte

    commande = image["entree"] + image["cmd"]
    if not commande:
        print("L'image n'a ni ENTRYPOINT ni CMD : le conteneur n'a rien à lancer.")
        return 1

    with tempfile.TemporaryDirectory(prefix="conteneur-") as tmp:
        programme = commande[0]
        if programme in image["fichiers"]:
            source = dossier / image["fichiers"][programme]
            if not source.is_file():
                print(f"COPY {image['fichiers'][programme]} : fichier introuvable dans {dossier}.")
                return 1
            contenu = remplace(source.read_text(encoding="utf-8"))
        elif programme == "/ros_entrypoint.sh" and image["base"].startswith(("ros:", "osrf/ros:")):
            contenu = ENTREE_OFFICIELLE
        else:
            contenu = None
        if contenu is not None:
            script = Path(tmp) / "entree.sh"
            script.write_text(contenu, encoding="utf-8")
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            argv = ["bash", str(script)] + [remplace(a) for a in commande[1:]]
        else:
            argv = [hote(commande[0])] + [remplace(a) for a in commande[1:]]

        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": tmp, "LANG": "C.UTF-8", "ROS_LOG_DIR": os.path.join(tmp, "log"),
            "PYTHONUNBUFFERED": "1",  # la sortie de ros2 launch arrive ligne par ligne dans le tube
            **{k: remplace(v) for k, v in image["env"].items()},
            # domaine dédié : la simulation ne voit pas les nœuds lancés dans le lab
            "ROS_DOMAIN_ID": str(random.randint(150, 200)),
        }
        workdir = hote(image["workdir"])
        cwd = workdir if os.path.isdir(workdir) else tmp

        print("$ docker run --rm livraison:dev    (simulé : " + " ".join(shlex.quote(a) for a in commande) + ")")
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, start_new_session=True)
        except OSError as exc:
            print(f"exec {commande[0]} : {exc.strerror}")
            return 1
        lignes, pret = [], False
        debut = time.monotonic()
        os.set_blocking(proc.stdout.fileno(), False)
        while time.monotonic() - debut < ATTENTE_S:
            ligne = proc.stdout.readline()
            if ligne:
                lignes.append(ligne.rstrip())
                if PRET in ligne:
                    pret = True
                    break
            elif proc.poll() is not None:
                lignes += [l.rstrip() for l in proc.stdout.read().splitlines()]
                break
            else:
                time.sleep(0.1)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGINT)
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        for ligne in lignes[-15:]:
            print("  " + ligne.replace(str(install), image["install"] or "/ws/install"))
        if pret:
            print("Le conteneur démarre le robot de livraison.")
            return 0
        if proc.returncode not in (None, 0) and not lignes:
            print(f"Le conteneur s'arrête aussitôt (code {proc.returncode}), sans rien afficher.")
        elif proc.poll() is not None:
            print(f"Le conteneur s'est arrêté (code {proc.returncode}) avant que le robot soit prêt.")
        else:
            print(f"Le robot n'a pas annoncé « {PRET} » en {ATTENTE_S} s.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

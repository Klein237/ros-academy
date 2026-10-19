"""DockerSpawner avec un réseau Docker par étudiant (reseau.py) et un dossier limité à 1 Go (disque.py).

Un dossier personnel par parcours : le Lab UI démarre le serveur avec {"parcours": "<id>"} ; seul le
dossier de ce parcours est monté en /home/etudiant. Sans parcours (lab ouvert seul), l'ancien dossier
commun. Un seul lab tourne à la fois : changer de parcours redémarre le lab.
"""

import asyncio

from dockerspawner import DockerSpawner
from traitlets import Unicode, default

from . import disque, reseau


class RosLabSpawner(DockerSpawner):
    hub_container = Unicode("hub", config=True, help="Nom du conteneur du Hub, connecté au réseau de chaque étudiant.")
    lab_subnets = Unicode(reseau.DEFAULT_SUBNETS, config=True, help="Plage découpée en /28, un par étudiant.")
    lab_homes_dir = Unicode(
        "", config=True,
        help="Dossier XFS avec quotas de projet pour les dossiers des étudiants ; vide : volumes Docker sans limite.")

    @default("network_name")
    def _default_network_name(self):
        # calculé aussi pour un serveur repris après un redémarrage du Hub
        return reseau.network_name(self.user.name)

    def _in_docker_thread(self, fn, *args):
        # même thread que les appels de DockerSpawner : les créations de réseaux ne se chevauchent pas
        return asyncio.wrap_future(self.executor.submit(fn, self.client, *args))

    @property
    def parcours(self):
        """Parcours demandé au démarrage (validé) ; "" pour le dossier commun."""
        p = (self.user_options or {}).get("parcours")
        return p if isinstance(p, str) and disque.PARCOURS_RE.fullmatch(p) else ""

    async def start(self):
        home = self.notebook_dir or "/home/etudiant"
        name, parcours = self.user.name, self.parcours
        if self.lab_homes_dir:
            loop = asyncio.get_running_loop()
            if parcours:
                path = await loop.run_in_executor(
                    None, disque.prepare_parcours_home, self.lab_homes_dir, name, parcours)
            else:
                path = await loop.run_in_executor(None, disque.prepare_home, self.lab_homes_dir, name)
            self.volumes = {path: home}
        elif parcours:
            await self.pull_image(self.image)
            volume = await self._in_docker_thread(prepare_parcours_volume, name, parcours, self.image, home)
            self.volumes = {volume: home}
        else:
            self.volumes = {volume_name(name): home}
        await self._in_docker_thread(reseau.ensure_network, self.user.name, self.hub_container, self.lab_subnets)
        return await super().start()

    async def stop(self, now=False):
        await super().stop(now=now)
        try:
            await self._in_docker_thread(reseau.remove_network, self.user.name, self.hub_container)
        except Exception as exc:  # noqa: BLE001 - supprimé au prochain démarrage du Hub
            self.log.warning("Réseau de %s non supprimé : %s", self.user.name, exc)

    async def delete_forever(self):
        """Utilisateur supprimé du Hub (suppression du compte) : son dossier personnel est effacé."""
        name = self.user.name
        if self.lab_homes_dir:
            removed = await asyncio.get_running_loop().run_in_executor(
                None, disque.remove_home, self.lab_homes_dir, name)
        else:
            removed = await self._in_docker_thread(remove_volumes, name)
        self.log.info("Dossier personnel de %s %s", name, "effacé" if removed else "absent")


def volume_name(username, parcours=""):
    """Volume Docker du dossier personnel (sans LAB_HOMES_DIR) : ros-lab-home-<nom>[--<parcours>]."""
    return f"ros-lab-home-{username}--{parcours}" if parcours else f"ros-lab-home-{username}"


# Lancé une fois, à la création du volume d'un parcours : déplace ~/ws/<parcours> de l'ancien
# volume commun. Le nouveau volume est monté en /home/etudiant pour que Docker y recopie d'abord
# le dossier de l'image (.bashrc…), comme pour le lab.
MIGRATION = """set -eu
if [ -d "/ancien/ws/$1" ] && [ ! -L "/ancien/ws/$1" ] && [ ! -e "ws/$1" ]; then
  mkdir -p ws && mv "/ancien/ws/$1" "ws/$1"
fi"""


def prepare_parcours_volume(client, username, parcours, image, home="/home/etudiant"):
    """Crée au besoin le volume du parcours (avec la migration) ; renvoie son nom."""
    from docker.errors import NotFound

    volume = volume_name(username, parcours)
    try:
        client.inspect_volume(volume)
        return volume
    except NotFound:
        pass
    client.create_volume(volume)
    binds = {volume: {"bind": home, "mode": "rw"}}
    try:
        client.inspect_volume(volume_name(username))
        binds[volume_name(username)] = {"bind": "/ancien", "mode": "rw"}
    except NotFound:
        pass  # pas d'ancien dossier : rien à déplacer
    container = client.create_container(
        image, command=["sh", "-c", MIGRATION, "migration", parcours], user="etudiant", working_dir=home,
        host_config=client.create_host_config(binds=binds, network_mode="none", cap_drop=["ALL"],
                                              security_opt=["no-new-privileges"]),
    )
    try:
        client.start(container)
        code = client.wait(container, timeout=300).get("StatusCode")
    finally:
        client.remove_container(container, force=True)
    if code != 0:
        # volume retiré : la migration sera retentée au prochain démarrage, rien n'est perdu
        client.remove_volume(volume, force=True)
        raise RuntimeError(f"dossier du parcours {parcours} non préparé pour {username} (code {code})")
    return volume


def remove_volumes(client, username):
    """Supprime le volume commun et ceux des parcours ; True si au moins un existait."""
    from docker.errors import NotFound

    names = {volume_name(username)}
    prefix = volume_name(username, "x")[:-1]
    for v in (client.volumes(filters={"name": prefix}) or {}).get("Volumes") or []:
        if v["Name"].startswith(prefix):
            names.add(v["Name"])
    removed = False
    for name in sorted(names):
        try:
            client.remove_volume(name, force=True)
            removed = True
        except NotFound:
            pass
    return removed

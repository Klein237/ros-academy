"""DockerSpawner avec un réseau Docker par étudiant (reseau.py) et un dossier limité à 1 Go (disque.py)."""

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

    async def start(self):
        if self.lab_homes_dir:
            path = await asyncio.get_running_loop().run_in_executor(
                None, disque.prepare_home, self.lab_homes_dir, self.user.name)
            self.volumes = {path: self.notebook_dir or "/home/etudiant"}
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
            removed = await self._in_docker_thread(remove_volume, f"ros-lab-home-{name}")
        self.log.info("Dossier personnel de %s %s", name, "effacé" if removed else "absent")


def remove_volume(client, volume):
    from docker.errors import NotFound

    try:
        client.remove_volume(volume, force=True)
    except NotFound:
        return False
    return True

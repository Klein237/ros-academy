"""DockerSpawner avec un réseau Docker par étudiant (voir reseau.py)."""

import asyncio

from dockerspawner import DockerSpawner
from traitlets import Unicode, default

from . import reseau


class RosLabSpawner(DockerSpawner):
    hub_container = Unicode("hub", config=True, help="Nom du conteneur du Hub, connecté au réseau de chaque étudiant.")
    lab_subnets = Unicode(reseau.DEFAULT_SUBNETS, config=True, help="Plage découpée en /28, un par étudiant.")

    @default("network_name")
    def _default_network_name(self):
        # calculé aussi pour un serveur repris après un redémarrage du Hub
        return reseau.network_name(self.user.name)

    def _in_docker_thread(self, fn, *args):
        # même thread que les appels de DockerSpawner : les créations de réseaux ne se chevauchent pas
        return asyncio.wrap_future(self.executor.submit(fn, self.client, *args))

    async def start(self):
        await self._in_docker_thread(reseau.ensure_network, self.user.name, self.hub_container, self.lab_subnets)
        return await super().start()

    async def stop(self, now=False):
        await super().stop(now=now)
        try:
            await self._in_docker_thread(reseau.remove_network, self.user.name, self.hub_container)
        except Exception as exc:  # noqa: BLE001 - supprimé au prochain démarrage du Hub
            self.log.warning("Réseau de %s non supprimé : %s", self.user.name, exc)

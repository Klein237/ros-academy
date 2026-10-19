"""Image des labs : est-elle sur le serveur ? Sinon, la retélécharger depuis le registre où la CI la
publie (ghcr.io), sous son nom local, sans attendre qu'un administrateur la reconstruise."""

import logging
import threading
import time

log = logging.getLogger(__name__)

NOUVEL_ESSAI = 600  # après un téléchargement raté, pas de nouvel essai avant 10 min


def split_tag(image):
    """« ros-lab:0.1.0 » → ("ros-lab", "0.1.0") ; sans étiquette : "latest"."""
    repo, sep, tag = image.rpartition(":")
    if not sep or "/" in tag:  # « hote:5000/ros-lab » : le « : » est celui du port
        return image, "latest"
    return repo, tag


class LabImage:
    """Appelée par la route de santé : (présente, nom de l'image, note sur la réparation en cours)."""

    def __init__(self, image, registry, client_factory, clock=time.monotonic):
        self.image, self.registry = image, registry
        self.client_factory, self.clock = client_factory, clock
        self.lock = threading.Lock()
        self.note = ""
        self.next_try = 0.0

    def __call__(self):
        from docker.errors import ImageNotFound

        try:
            client = self.client_factory()
            client.images.get(self.image)
            return True, self.image, ""
        except ImageNotFound:
            pass
        except Exception as exc:  # noqa: BLE001 - démon Docker injoignable : signalé aussi
            log.warning("Image %s non vérifiable : %s", self.image, exc)
            return False, self.image, ""
        note = self.note
        if self.registry and self.clock() >= self.next_try and self.lock.acquire(blocking=False):
            note = self.note = f"Téléchargement automatique depuis {self.registry}:{split_tag(self.image)[1]} en cours."
            threading.Thread(target=self._repair, args=(client,), daemon=True).start()
        return False, self.image, note

    def _repair(self, client):
        repo, tag = split_tag(self.image)
        source = f"{self.registry}:{tag}"
        try:
            log.warning("Image %s absente : téléchargement de %s", self.image, source)
            client.images.pull(self.registry, tag=tag).tag(repo, tag)
            log.info("Image %s rétablie depuis %s", self.image, source)
            self.note = ""
        except Exception as exc:  # noqa: BLE001 - registre injoignable, image privée…
            log.warning("Téléchargement de %s impossible : %s", source, exc)
            self.note = f"Le téléchargement automatique depuis {source} a échoué ({exc}) ; nouvel essai dans 10 min."
            self.next_try = self.clock() + NOUVEL_ESSAI
        finally:
            self.lock.release()

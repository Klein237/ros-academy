"""Appels au Hub (serveurs des étudiants) et aux routes internes du service Contenus."""

import hashlib
import hmac

import httpx

INTERNAL_HEADER = "X-Academy-Interne"


def internal_token(secret):
    """Secret partagé avec Contenus pour ses routes internes (dérivé, jamais le secret lui-même)."""
    return hmac.new(secret.encode(), b"contenus-interne", hashlib.sha256).hexdigest()


def comptes_token(secret):
    """Secret dérivé que le Hub présente à la route interne de Comptes (quota avant démarrage)."""
    return hmac.new(secret.encode(), b"comptes-interne", hashlib.sha256).hexdigest()


class UpstreamError(Exception):
    def __init__(self, status, message=""):
        self.status = status
        super().__init__(message or f"erreur {status}")


class HubClient:
    def __init__(self, base, token, http=None):
        self.base = base.rstrip("/")
        self.http = http or httpx.Client(timeout=10)
        self.headers = {"Authorization": f"token {token}"}

    def running_servers(self):
        """{nom: prêt} des serveurs démarrés ou en démarrage."""
        r = self.http.get(f"{self.base}/hub/api/users", headers=self.headers)
        r.raise_for_status()
        out = {}
        for u in r.json():
            server = (u.get("servers") or {}).get("")
            if server:
                out[u["name"]] = bool(server.get("ready"))
        return out

    def stop(self, name):
        self.http.delete(f"{self.base}/hub/api/users/{name}/server", headers=self.headers)

    def delete_user(self, name, timeout=90):
        """Arrête le serveur puis supprime l'utilisateur du Hub, qui efface son dossier personnel
        (RosLabSpawner.delete_forever). Sans utilisateur au Hub (lab jamais ouvert) : rien à faire."""
        from .rgpd import wait_until

        url = f"{self.base}/hub/api/users/{name}"
        self.http.delete(f"{url}/server", headers=self.headers)

        def stopped():
            r = self.http.get(url, headers=self.headers)
            return r.status_code == 404 or (r.status_code == 200 and not (r.json().get("servers") or {}))

        if not wait_until(stopped, timeout):
            raise UpstreamError(409)
        r = self.http.delete(url, headers=self.headers)
        if r.status_code not in (204, 404):
            raise UpstreamError(r.status_code)


class ContenusClient:
    def __init__(self, base, secret, http=None):
        self.base = base.rstrip("/")
        self.http = http or httpx.Client(timeout=15)
        self.headers = {INTERNAL_HEADER: internal_token(secret)}

    def _json(self, r):
        if r.status_code >= 400:
            raise UpstreamError(r.status_code)
        return r.json()

    def correct_qcm(self, module, reponses):
        return self._json(self.http.post(f"{self.base}/api/contenus/modules/{module}/qcm",
                                         json={"reponses": reponses}, headers=self.headers))

    def hint(self, module, n):
        return self._json(self.http.get(f"{self.base}/api/contenus/modules/{module}/indices/{n}", headers=self.headers))

    def explanation(self, module):
        return self._json(self.http.get(f"{self.base}/api/contenus/modules/{module}/explication", headers=self.headers))

    def verify(self, module, student):
        """check.sh officiel sur le workspace de l'étudiant (compilation comprise : jusqu'à quelques minutes)."""
        return self._json(self.http.post(f"{self.base}/api/contenus/modules/{module}/verifier",
                                         json={"etudiant": student}, headers=self.headers, timeout=600))

    def exercise(self, module):
        return self._json(self.http.get(f"{self.base}/api/contenus/modules/{module}/exercice"))

    def parcours(self):
        return self._json(self.http.get(f"{self.base}/api/contenus/parcours"))["parcours"]

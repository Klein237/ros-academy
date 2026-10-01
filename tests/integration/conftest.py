import json
import os
import ssl
import time
import uuid

import docker
import jwt
import pytest
import requests
import urllib3
import websocket

urllib3.disable_warnings()

BASE = os.environ.get("BASE_URL", "https://localhost")
WS_BASE = BASE.replace("https://", "wss://", 1)
ADMIN_TOKEN = os.environ["HUB_ADMIN_TOKEN"]
JWT_SECRET = os.environ["JWT_SECRET"]


def mint(sub, plan="free", ttl=300):
    now = int(time.time())
    claims = {"sub": sub, "plan": plan, "aud": "ros-lab", "iat": now, "exp": now + ttl}
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


class Hub:
    def __init__(self):
        self.s = requests.Session()
        self.s.verify = False
        self.s.headers["Authorization"] = f"token {ADMIN_TOKEN}"

    def api(self, method, path, **kw):
        return self.s.request(method, f"{BASE}/hub/api{path}", **kw)

    def login(self, sub, plan="free", token=None):
        return requests.get(
            f"{BASE}/hub/jwt_login",
            params={"token": token if token is not None else mint(sub, plan)},
            verify=False,
            allow_redirects=False,
        )

    def start(self, name, timeout=180):
        r = self.api("POST", f"/users/{name}/server")
        if r.status_code not in (201, 202, 400):  # 400 = déjà démarré
            raise RuntimeError(
                f"démarrage de {name} refusé : {r.status_code} {r.text}"
            )
        deadline = time.time() + timeout
        while time.time() < deadline:
            server = self.api("GET", f"/users/{name}").json().get("servers", {}).get("")
            if server and server.get("ready"):
                return r
            time.sleep(2)
        raise TimeoutError(f"le serveur de {name} n'est pas prêt après {timeout}s")

    def stop(self, name, timeout=60):
        self.api("DELETE", f"/users/{name}/server")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.api("GET", f"/users/{name}").json().get("servers"):
                return
            time.sleep(2)
        raise TimeoutError(f"le serveur de {name} ne s'arrête pas")

    def run(self, name, command, timeout=60):
        """Exécute une commande dans un terminal du conteneur et retourne sa sortie."""
        r = self.s.post(f"{BASE}/user/{name}/api/terminals")
        r.raise_for_status()
        term = r.json()["name"]
        ws = websocket.create_connection(
            f"{WS_BASE}/user/{name}/terminals/websocket/{term}",
            header=[f"Authorization: token {ADMIN_TOKEN}"],
            sslopt={"cert_reqs": ssl.CERT_NONE},
        )
        tag = uuid.uuid4().hex
        # Les guillemets vides empêchent l'écho de la commande de contenir le marqueur.
        # Le marqueur est tapé sur une ligne séparée (et non après « ; ») pour que
        # les commandes qui se terminent par « & » restent valides en bash.
        ws.send(json.dumps(["stdin", f"{command}\recho __END_\"\"{tag}__\r"]))
        out, deadline = "", time.time() + timeout
        ws.settimeout(5)
        while f"__END_{tag}__" not in out and time.time() < deadline:
            try:
                msg = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if msg[0] == "stdout":
                out += msg[1]
        ws.close()
        self.s.delete(f"{BASE}/user/{name}/api/terminals/{term}")
        if f"__END_{tag}__" not in out:
            raise TimeoutError(f"commande sans fin : {command!r}\n{out}")
        return out


@pytest.fixture(scope="session")
def hub():
    return Hub()


@pytest.fixture(scope="session")
def docker_client():
    return docker.from_env()


@pytest.fixture
def student(hub):
    """Crée un étudiant unique, connecté et démarré ; nettoie à la fin."""
    created = []

    def _make(plan="free"):
        name = f"it{uuid.uuid4().hex[:8]}"
        created.append(name)
        assert hub.login(name, plan).status_code == 302
        hub.start(name)
        return name

    yield _make
    errors = []
    for name in created:
        try:
            hub.stop(name)
            hub.api("DELETE", f"/users/{name}")
        except Exception as e:  # noqa: BLE001 - on nettoie les autres étudiants quand même
            errors.append(f"{name}: {e!r}")
    if errors:
        raise RuntimeError("nettoyage incomplet : " + "; ".join(errors))

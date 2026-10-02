import os
import sys

from rosacademy_hub.auth import ComptesJWTAuthenticator
from rosacademy_hub.quotas import apply_limits, make_quota_hook

c = get_config()  # noqa: F821


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Variable d'environnement obligatoire manquante : {name}")
    return value


def secret_env(name):
    value = env(name, required=True)
    if len(value) < 32 or value.startswith("remplacer"):
        sys.exit(f"{name} doit faire au moins 32 caractères et ne pas être la valeur d'exemple")
    return value


jwt_secret = secret_env("JWT_SECRET")
secret_env("JUPYTERHUB_CRYPT_KEY")  # chiffre auth_state (formule)
admin_token = secret_env("HUB_ADMIN_TOKEN")

# --- Authentification : jeton émis par le service Comptes
c.JupyterHub.authenticator_class = ComptesJWTAuthenticator
c.ComptesJWTAuthenticator.secret = jwt_secret
c.Authenticator.allow_all = True
c.Authenticator.enable_auth_state = True
c.Authenticator.auto_login = True

# --- Conteneurs étudiants
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.image = env("ROS_LAB_IMAGE", "ros-lab:0.1.0")
c.DockerSpawner.cmd = ["jupyterhub-singleuser"]
c.DockerSpawner.network_name = "ros-lab-net"
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True
c.DockerSpawner.notebook_dir = "/home/etudiant"
c.DockerSpawner.volumes = {"ros-lab-home-{username}": "/home/etudiant"}
c.DockerSpawner.extra_host_config = {
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
    "init": True,  # tini en PID 1 : récolte les processus zombies
}
c.Spawner.auth_state_hook = apply_limits
comptes_url = env("COMPTES_URL", "")
if comptes_url:
    c.Spawner.pre_spawn_hook = make_quota_hook(comptes_url, jwt_secret)  # quota de minutes du mois
# Le Lab UI passe son jeton dans l'URL des WebSockets (un navigateur ne sait pas y
# mettre d'en-tête, et Chromium n'envoie pas Sec-Fetch-Mode: websocket). Les pages
# servies sous /user/ sont isolées par la CSP « sandbox » posée par Caddy.
c.Spawner.environment = {"JUPYTERHUB_ALLOW_TOKEN_IN_URL": "1"}
c.Spawner.start_timeout = 120
c.Spawner.http_timeout = 90

# --- Hub
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = "hub"
c.JupyterHub.active_server_limit = int(env("ACTIVE_SERVER_LIMIT", "35"))
c.JupyterHub.cookie_max_age_days = 1
c.JupyterHub.cookie_secret_file = "/srv/hub/data/jupyterhub_cookie_secret"
c.JupyterHub.db_url = "sqlite:////srv/hub/data/jupyterhub.sqlite"

# --- Services : arrêt des sessions inactives + accès administrateur de la plateforme
idle_timeout = int(env("IDLE_TIMEOUT_SECONDS", "1200"))
c.JupyterHub.services = [
    {
        "name": "idle-culler",
        "command": [sys.executable, "-m", "jupyterhub_idle_culler",
                    f"--timeout={idle_timeout}", "--cull-every=30"],
    },
    {"name": "platform-admin", "api_token": admin_token},
]
c.JupyterHub.load_roles = [
    {
        "name": "idle-culler",
        "scopes": ["list:users", "read:users:activity", "read:servers", "delete:servers"],
        "services": ["idle-culler"],
    },
    {
        "name": "platform-admin",
        "scopes": ["admin:users", "admin:servers", "access:servers", "read:users"],
        "services": ["platform-admin"],
    },
]

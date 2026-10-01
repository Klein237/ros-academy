import os
import sys

from rosacademy_hub.auth import ComptesJWTAuthenticator
from rosacademy_hub.quotas import apply_limits

c = get_config()  # noqa: F821


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Variable d'environnement obligatoire manquante : {name}")
    return value


jwt_secret = env("JWT_SECRET", required=True)
if len(jwt_secret) < 32:
    sys.exit("JWT_SECRET doit faire au moins 32 caractères")
env("JUPYTERHUB_CRYPT_KEY", required=True)  # chiffre auth_state (formule)
admin_token = env("HUB_ADMIN_TOKEN", required=True)

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
}
c.Spawner.auth_state_hook = apply_limits
c.Spawner.start_timeout = 120
c.Spawner.http_timeout = 90

# --- Hub
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = "hub"
c.JupyterHub.active_server_limit = int(env("ACTIVE_SERVER_LIMIT", "35"))
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

# Image `ros-lab` + moteur de sessions — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** un compte de test, muni d'un jeton signé, obtient derrière HTTPS un vrai terminal ROS 2 Humble dans un conteneur isolé, limité et sans Internet, dont les fichiers survivent à l'arrêt.

**Architecture :** JupyterHub 5 (non modifié) tourne dans un conteneur avec DockerSpawner ; il lance un conteneur `ros-lab` par étudiant sur un réseau Docker `internal` (sans sortie Internet). L'authentification est déléguée au futur service Comptes via un jeton JWT HS256 court (`/hub/jwt_login?token=…`) qui porte l'identifiant et la formule de l'étudiant ; la formule fixe les limites CPU/RAM/processus au démarrage du conteneur. Caddy termine le HTTPS devant le proxy du Hub.

**Tech Stack :** Docker + Docker Compose, ROS 2 Humble (`ros:humble-ros-base-jammy`), JupyterHub 5.2.1, DockerSpawner 13.0.0, jupyterhub-idle-culler 1.4.0, jupyter-server 2.14.2, jupyter-server-proxy 4.4.0, rosbridge_suite, PyJWT 2.9.0, Caddy 2.8, pytest 8.3.3, GitHub Actions.

**Spec :** [Plateforme de formation ROS 2 — Spec de design](https://claude.ai/code/artifact/e0a0510b-9545-459e-9c12-da51ca1898ba) — sections « Architecture d'ensemble », « Déroulé d'une session de lab », « Sécurité, quotas et erreurs », « Stratégie de tests », sous-projet 1.

## Global Constraints

- ROS 2 Humble sur Ubuntu 22.04 (`ros:humble-ros-base-jammy`).
- Un conteneur par étudiant, utilisateur non-root `etudiant` (uid 1000), sans `sudo`, sans accès au socket Docker.
- Conteneurs lancés avec `cap_drop: ["ALL"]` et `security_opt: ["no-new-privileges"]`.
- Pas d'accès Internet sortant depuis les conteneurs étudiants (réseau Docker `internal: true`).
- `ROS_LOCALHOST_ONLY=1` dans chaque conteneur (isolation DDS).
- Formule `free` : 1 vCPU, 2 Go RAM, 256 processus. Formule `pro` : 2 vCPU, 4 Go RAM, 512 processus.
- 1 session simultanée par personne ; arrêt après 20 min d'inactivité (`IDLE_TIMEOUT_SECONDS=1200`).
- Capacité cible : 30 à 40 sessions simultanées ; `ACTIVE_SERVER_LIMIT=35` par défaut, au-delà le Hub répond 429.
- Volume personnel monté sur `/home/etudiant`, conservé quand le conteneur s'arrête.
- HTTPS partout via Caddy ; jetons de connexion de durée de vie ≤ 3600 s.
- Versions JupyterHub identiques côté Hub et côté image (`5.2.1`).

**Écart assumé par rapport à la spec :** la limite de 1 Go du volume personnel n'est pas appliquée dans ce plan (Docker ne sait pas limiter un volume `local` sans quotas XFS sur l'hôte). Elle sera traitée au choix de l'hébergeur (question ouverte de la spec).

## Review Focus

1. **Formule absente, inconnue ou mal typée dans le jeton** (`null`, `"enterprise"`, `["pro"]`) → l'étudiant reçoit les limites `free`, le Hub ne plante pas. Test : Task 1 (`test_unknown_or_malformed_plan_falls_back_to_free`).
2. **Jeton forgé, expiré, de durée trop longue, `alg: none`, ou `sub` dangereux** (`../root`, `Admin`) → 403, aucun utilisateur créé. Tests : Task 2 (unitaires) et Task 5 (`test_invalid_token_is_refused`).
3. **L'étudiant revient après l'arrêt de son conteneur** → ses fichiers sont toujours là. Test : Task 5 (`test_workspace_persists_across_restart`).
4. **Deux étudiants connectés en même temps** → aucun ne voit les topics de l'autre (avec un témoin positif chez le premier). Test : Task 5 (`test_dds_is_isolated_between_students`).
5. **Serveur plein** → réponse 429 exploitable par le Lab UI (file d'attente), pas une erreur 500. Test : Task 5 (`test_server_limit_returns_429`).

---

## Structure des fichiers

```
ros-academy/
├─ images/ros-lab/
│  ├─ Dockerfile                    ← image étudiant
│  ├─ ros.sh                        ← environnement ROS (profile.d)
│  └─ jupyter_server_config.py      ← terminal en shell de login + proxy rosbridge
├─ hub/
│  ├─ Dockerfile                    ← image Hub
│  ├─ requirements.txt              ← dépendances runtime du Hub
│  ├─ requirements-dev.txt          ← dépendances de test
│  ├─ jupyterhub_config.py          ← configuration (lit les variables d'env)
│  ├─ rosacademy_hub/
│  │  ├─ __init__.py
│  │  ├─ quotas.py                  ← formule → limites, hook de spawn
│  │  └─ auth.py                    ← vérification JWT + Authenticator
│  └─ tests/
│     ├─ test_quotas.py
│     └─ test_auth.py
├─ deploy/
│  ├─ docker-compose.yml            ← hub + caddy + réseaux
│  ├─ Caddyfile
│  ├─ .env.example
│  └─ README.md                     ← runbook de déploiement
├─ scripts/
│  └─ mint_token.py                 ← fabrique un jeton de test
├─ tests/
│  ├─ image/test_image.sh           ← tests de l'image ros-lab
│  └─ integration/
│     ├─ conftest.py                ← client Hub + exécution de commandes
│     ├─ pytest.ini
│     └─ test_session.py
└─ .github/workflows/ci.yml
```

---

### Task 1 : Formules et limites (`quotas.py`)

**Files:**
- Create: `hub/rosacademy_hub/__init__.py`
- Create: `hub/rosacademy_hub/quotas.py`
- Create: `hub/requirements.txt`, `hub/requirements-dev.txt`
- Test: `hub/tests/test_quotas.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `PlanLimits(cpu: float, mem: str, pids: int)` (dataclass figée)
  - `PLANS: dict[str, PlanLimits]`, `DEFAULT_PLAN = "free"`
  - `limits_for(plan: object) -> PlanLimits`
  - `apply_limits(spawner, auth_state: dict | None) -> None` — utilisé comme `c.Spawner.auth_state_hook` en Task 4.

- [ ] **Step 1 : Créer les fichiers de dépendances**

`hub/requirements.txt` :
```
dockerspawner==13.0.0
jupyterhub-idle-culler==1.4.0
PyJWT==2.9.0
```

`hub/requirements-dev.txt` :
```
-r requirements.txt
jupyterhub==5.2.1
pytest==8.3.3
requests==2.32.3
websocket-client==1.8.0
docker==7.1.0
```

`hub/rosacademy_hub/__init__.py` : fichier vide.

Run : `cd hub && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt`
Expected : installation sans erreur.

- [ ] **Step 2 : Écrire les tests qui échouent**

`hub/tests/test_quotas.py` :
```python
from types import SimpleNamespace

import pytest

from rosacademy_hub.quotas import DEFAULT_PLAN, PLANS, PlanLimits, apply_limits, limits_for


def make_spawner():
    return SimpleNamespace(
        cpu_limit=None,
        mem_limit=None,
        extra_host_config={"cap_drop": ["ALL"], "security_opt": ["no-new-privileges"]},
    )


def test_free_and_pro_limits_match_spec():
    assert PLANS["free"] == PlanLimits(cpu=1.0, mem="2G", pids=256)
    assert PLANS["pro"] == PlanLimits(cpu=2.0, mem="4G", pids=512)
    assert DEFAULT_PLAN == "free"


def test_limits_for_known_plan():
    assert limits_for("pro") == PLANS["pro"]


@pytest.mark.parametrize("plan", [None, "", "enterprise", "PRO", ["pro"], {"plan": "pro"}, 42])
def test_unknown_or_malformed_plan_falls_back_to_free(plan):
    assert limits_for(plan) == PLANS["free"]


def test_apply_limits_sets_cpu_mem_and_pids():
    spawner = make_spawner()
    apply_limits(spawner, {"plan": "pro"})
    assert spawner.cpu_limit == 2.0
    assert spawner.mem_limit == "4G"
    assert spawner.extra_host_config["pids_limit"] == 512


def test_apply_limits_keeps_hardening_options():
    spawner = make_spawner()
    apply_limits(spawner, {"plan": "free"})
    assert spawner.extra_host_config["cap_drop"] == ["ALL"]
    assert spawner.extra_host_config["security_opt"] == ["no-new-privileges"]


def test_apply_limits_does_not_mutate_shared_config():
    shared = {"cap_drop": ["ALL"]}
    a = SimpleNamespace(cpu_limit=None, mem_limit=None, extra_host_config=shared)
    apply_limits(a, {"plan": "pro"})
    assert "pids_limit" not in shared


@pytest.mark.parametrize("auth_state", [None, {}, {"other": 1}])
def test_apply_limits_without_plan_uses_free(auth_state):
    spawner = make_spawner()
    apply_limits(spawner, auth_state)
    assert spawner.mem_limit == "2G"
    assert spawner.extra_host_config["pids_limit"] == 256
```

- [ ] **Step 3 : Vérifier qu'ils échouent**

Run : `cd hub && python -m pytest tests/test_quotas.py -v`
Expected : FAIL avec `ModuleNotFoundError: No module named 'rosacademy_hub.quotas'`.

- [ ] **Step 4 : Implémentation minimale**

`hub/rosacademy_hub/quotas.py` :
```python
"""Formules d'abonnement et limites de ressources des conteneurs ros-lab."""

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanLimits:
    cpu: float
    mem: str
    pids: int


PLANS = {
    "free": PlanLimits(cpu=1.0, mem="2G", pids=256),
    "pro": PlanLimits(cpu=2.0, mem="4G", pids=512),
}
DEFAULT_PLAN = "free"


def limits_for(plan):
    """Retourne les limites de la formule ; toute valeur inconnue donne `free`."""
    if isinstance(plan, str) and plan in PLANS:
        return PLANS[plan]
    log.warning("Formule inconnue %r, application de %s", plan, DEFAULT_PLAN)
    return PLANS[DEFAULT_PLAN]


def apply_limits(spawner, auth_state):
    """auth_state_hook de JupyterHub : fixe les limites avant le démarrage."""
    plan = (auth_state or {}).get("plan", DEFAULT_PLAN)
    limits = limits_for(plan)
    spawner.cpu_limit = limits.cpu
    spawner.mem_limit = limits.mem
    spawner.extra_host_config = {**spawner.extra_host_config, "pids_limit": limits.pids}
```

- [ ] **Step 5 : Vérifier qu'ils passent**

Run : `cd hub && python -m pytest tests/test_quotas.py -v`
Expected : 15 tests PASS.

- [ ] **Step 6 : Commit**

```bash
printf '.venv/\n__pycache__/\n.pytest_cache/\ndeploy/.env\n' > .gitignore
git add .gitignore hub/requirements.txt hub/requirements-dev.txt hub/rosacademy_hub/__init__.py hub/rosacademy_hub/quotas.py hub/tests/test_quotas.py
git commit -m "feat(hub): plan limits and spawner hook"
```

---

### Task 2 : Authentification par jeton (`auth.py`) + script `mint_token.py`

**Files:**
- Create: `hub/rosacademy_hub/auth.py`
- Create: `scripts/mint_token.py`
- Test: `hub/tests/test_auth.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `class TokenError(Exception)`
  - `verify_token(token: str, secret: str, audience: str = "ros-lab", max_lifetime: int = 3600, leeway: int = 30) -> dict` qui retourne `{"name": str, "auth_state": {"plan": object}}` ou lève `TokenError`.
  - `class ComptesJWTAuthenticator(Authenticator)` avec les traits `secret`, `audience`, `max_lifetime` ; route `/hub/jwt_login?token=…`.
  - Format du jeton (contrat avec le futur service Comptes) : HS256, claims `sub` (identifiant `^[a-z0-9][a-z0-9_-]{0,31}$`), `plan` (`"free"`|`"pro"`), `aud="ros-lab"`, `iat`, `exp` avec `exp - iat <= 3600`.
  - `scripts/mint_token.py --sub <id> [--plan free] [--ttl 300]` affiche un jeton (lit `JWT_SECRET`).

- [ ] **Step 1 : Écrire les tests qui échouent**

`hub/tests/test_auth.py` :
```python
import time

import jwt
import pytest

from rosacademy_hub.auth import TokenError, verify_token

SECRET = "s" * 40


def make(sub="u-42", plan="free", aud="ros-lab", iat=None, ttl=300, secret=SECRET, alg="HS256", **extra):
    now = int(time.time()) if iat is None else iat
    claims = {"sub": sub, "plan": plan, "aud": aud, "iat": now, "exp": now + ttl, **extra}
    return jwt.encode(claims, secret, algorithm=alg)


def test_valid_token_returns_user_and_plan():
    result = verify_token(make(plan="pro"), SECRET)
    assert result == {"name": "u-42", "auth_state": {"plan": "pro"}}


def test_missing_plan_is_passed_as_none():
    now = int(time.time())
    token = jwt.encode({"sub": "u-1", "aud": "ros-lab", "iat": now, "exp": now + 60}, SECRET, algorithm="HS256")
    assert verify_token(token, SECRET)["auth_state"] == {"plan": None}


def test_empty_token_is_refused():
    with pytest.raises(TokenError):
        verify_token("", SECRET)


def test_garbage_token_is_refused():
    with pytest.raises(TokenError):
        verify_token("not-a-jwt", SECRET)


def test_wrong_secret_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(secret="x" * 40), SECRET)


def test_expired_token_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(iat=int(time.time()) - 4000, ttl=300), SECRET)


def test_wrong_audience_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(aud="other-app"), SECRET)


def test_too_long_lifetime_is_refused():
    with pytest.raises(TokenError):
        verify_token(make(ttl=24 * 3600), SECRET)


def test_alg_none_is_refused():
    now = int(time.time())
    token = jwt.encode({"sub": "u-1", "aud": "ros-lab", "iat": now, "exp": now + 60}, None, algorithm="none")
    with pytest.raises(TokenError):
        verify_token(token, SECRET)


@pytest.mark.parametrize("sub", ["../root", "Admin", "a" * 33, "-start", "user name", "élève"])
def test_unsafe_subject_is_refused(sub):
    with pytest.raises(TokenError):
        verify_token(make(sub=sub), SECRET)


def test_missing_exp_is_refused():
    token = jwt.encode({"sub": "u-1", "aud": "ros-lab", "iat": int(time.time())}, SECRET, algorithm="HS256")
    with pytest.raises(TokenError):
        verify_token(token, SECRET)
```

- [ ] **Step 2 : Vérifier qu'ils échouent**

Run : `cd hub && python -m pytest tests/test_auth.py -v`
Expected : FAIL avec `ModuleNotFoundError: No module named 'rosacademy_hub.auth'`.

- [ ] **Step 3 : Implémentation minimale**

`hub/rosacademy_hub/auth.py` :
```python
"""Connexion au Hub par jeton JWT émis par le service Comptes."""

import re

import jwt
from jupyterhub.auth import Authenticator
from jupyterhub.handlers import BaseHandler
from jupyterhub.utils import url_path_join
from tornado import web
from traitlets import Integer, Unicode

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class TokenError(Exception):
    pass


def verify_token(token, secret, audience="ros-lab", max_lifetime=3600, leeway=30):
    if not token:
        raise TokenError("jeton manquant")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            leeway=leeway,
            options={"require": ["exp", "iat", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if claims["exp"] - claims["iat"] > max_lifetime:
        raise TokenError("durée de vie du jeton trop longue")
    sub = claims["sub"]
    if not isinstance(sub, str) or not USERNAME_RE.match(sub):
        raise TokenError("identifiant invalide")
    return {"name": sub, "auth_state": {"plan": claims.get("plan")}}


class JWTLoginHandler(BaseHandler):
    async def get(self):
        user = await self.login_user({"token": self.get_argument("token", "")})
        if user is None:
            raise web.HTTPError(403, "Lien de connexion invalide ou expiré. Rouvrez le lab depuis le site.")
        self.redirect(self.get_next_url(user))


class ComptesJWTAuthenticator(Authenticator):
    secret = Unicode(help="Secret HS256 partagé avec le service Comptes").tag(config=True)
    audience = Unicode("ros-lab").tag(config=True)
    max_lifetime = Integer(3600).tag(config=True)

    def get_handlers(self, app):
        return [(r"/jwt_login", JWTLoginHandler)]

    def login_url(self, base_url):
        return url_path_join(base_url, "jwt_login")

    async def authenticate(self, handler, data):
        try:
            return verify_token(data.get("token", ""), self.secret, self.audience, self.max_lifetime)
        except TokenError as exc:
            self.log.warning("Connexion par jeton refusée : %s", exc)
            return None
```

- [ ] **Step 4 : Vérifier qu'ils passent**

Run : `cd hub && python -m pytest tests/ -v`
Expected : tous les tests de `test_auth.py` et `test_quotas.py` PASS.

- [ ] **Step 5 : Écrire `scripts/mint_token.py`**

```python
#!/usr/bin/env python3
"""Fabrique un jeton de connexion de test (en attendant le service Comptes)."""

import argparse
import os
import sys
import time

import jwt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sub", required=True)
    parser.add_argument("--plan", default="free")
    parser.add_argument("--ttl", type=int, default=300)
    args = parser.parse_args()
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        sys.exit("JWT_SECRET manquant")
    now = int(time.time())
    claims = {"sub": args.sub, "plan": args.plan, "aud": "ros-lab", "iat": now, "exp": now + args.ttl}
    print(jwt.encode(claims, secret, algorithm="HS256"))


if __name__ == "__main__":
    main()
```

Run : `JWT_SECRET=$(printf 's%.0s' {1..40}) python scripts/mint_token.py --sub u-1 | cut -c1-10`
Expected : `eyJhbGciOi`

- [ ] **Step 6 : Commit**

```bash
git add hub/rosacademy_hub/auth.py hub/tests/test_auth.py scripts/mint_token.py
git commit -m "feat(hub): JWT login delegated to accounts service"
```

---

### Task 3 : Image étudiant `ros-lab`

**Files:**
- Create: `images/ros-lab/Dockerfile`
- Create: `images/ros-lab/ros.sh`
- Create: `images/ros-lab/jupyter_server_config.py`
- Test: `tests/image/test_image.sh`

**Interfaces:**
- Consumes: rien.
- Produces : image `ros-lab:0.1.0` ; utilisateur `etudiant` (uid 1000) ; `CMD ["jupyterhub-singleuser"]` ; rosbridge servi par jupyter-server-proxy au chemin `/user/<nom>/rosbridge/` ; terminaux en shell de login avec ROS sourcé et `ROS_LOCALHOST_ONLY=1`.

- [ ] **Step 1 : Écrire le test qui échoue**

`tests/image/test_image.sh` :
```bash
#!/usr/bin/env bash
set -euo pipefail
IMG="${IMG:-ros-lab:0.1.0}"

run() { docker run --rm "$IMG" bash -lc "$1"; }
fail() { echo "FAIL: $1"; exit 1; }

[ "$(run 'whoami')" = "etudiant" ] || fail "l'utilisateur n'est pas etudiant"
[ "$(run 'id -u')" = "1000" ] || fail "uid différent de 1000"
if run 'command -v sudo' >/dev/null; then fail "sudo est présent"; fi
[ "$(run 'echo $ROS_LOCALHOST_ONLY')" = "1" ] || fail "ROS_LOCALHOST_ONLY absent"
[ "$(run 'echo $ROS_DISTRO')" = "humble" ] || fail "ROS non sourcé"
run 'ros2 pkg list' | grep -qx rclpy || fail "rclpy manquant"
run 'ros2 pkg list' | grep -qx rclcpp || fail "rclcpp manquant"
run 'ros2 pkg list' | grep -qx rosbridge_server || fail "rosbridge_server manquant"
run 'command -v colcon' >/dev/null || fail "colcon manquant"
run 'jupyterhub-singleuser --version' | grep -q '^5\.2\.1' || fail "jupyterhub-singleuser 5.2.1 manquant"
run 'python3 -c "import jupyter_server_proxy"' || fail "jupyter-server-proxy manquant"
run 'cd /tmp && mkdir -p ws/src && cd ws/src \
     && ros2 pkg create --build-type ament_python py_pkg >/dev/null \
     && ros2 pkg create --build-type ament_cmake cpp_pkg >/dev/null \
     && cd .. && colcon build >/dev/null' || fail "colcon build Python + C++ échoue"
echo "ALL IMAGE TESTS PASSED"
```

Run : `chmod +x tests/image/test_image.sh && tests/image/test_image.sh`
Expected : FAIL — `Unable to find image 'ros-lab:0.1.0' locally` puis erreur de pull.

- [ ] **Step 2 : Écrire l'environnement ROS**

`images/ros-lab/ros.sh` :
```bash
# Environnement ROS 2 de l'étudiant (sourcé par tous les shells)
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=0
```

`images/ros-lab/jupyter_server_config.py` :
```python
c = get_config()  # noqa: F821

# Le terminal ouvre un shell de login : /etc/profile.d/ros.sh est sourcé.
c.ServerApp.terminado_settings = {"shell_command": ["/bin/bash", "-l"]}

# rosbridge écoute seulement en local ; il n'est joignable qu'à travers
# le proxy authentifié du serveur Jupyter : /user/<nom>/rosbridge/
c.ServerProxy.servers = {
    "rosbridge": {
        "command": [
            "bash", "-lc",
            "exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml "
            "port:={port} address:=127.0.0.1",
        ],
        "timeout": 60,
        "launcher_entry": {"enabled": False},
    }
}
```

- [ ] **Step 3 : Écrire le Dockerfile**

`images/ros-lab/Dockerfile` :
```dockerfile
FROM ros:humble-ros-base-jammy

ARG JUPYTERHUB_VERSION=5.2.1
ENV DEBIAN_FRONTEND=noninteractive \
    ROS_LOCALHOST_ONLY=1 \
    ROS_DOMAIN_ID=0

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3-pip python3-colcon-common-extensions build-essential \
      ros-humble-rosbridge-suite ros-humble-demo-nodes-py ros-humble-demo-nodes-cpp \
      nano vim-tiny less \
 && apt-get purge -y --auto-remove sudo \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
      "jupyterhub==${JUPYTERHUB_VERSION}" \
      "jupyter-server==2.14.2" \
      "jupyter-server-proxy==4.4.0" \
      "terminado==0.18.1"

COPY ros.sh /etc/profile.d/ros.sh
COPY jupyter_server_config.py /etc/jupyter/jupyter_server_config.py
RUN echo 'source /etc/profile.d/ros.sh' >> /etc/bash.bashrc \
 && useradd --create-home --uid 1000 --shell /bin/bash etudiant

USER etudiant
WORKDIR /home/etudiant
CMD ["jupyterhub-singleuser"]
```

- [ ] **Step 4 : Construire et vérifier que le test passe**

Run : `docker build -t ros-lab:0.1.0 images/ros-lab && tests/image/test_image.sh`
Expected : dernière ligne `ALL IMAGE TESTS PASSED`.

- [ ] **Step 5 : Commit**

```bash
git add images/ros-lab tests/image/test_image.sh
git commit -m "feat(image): ros-lab student image (ROS 2 Humble, non-root, rosbridge proxy)"
```

---

### Task 4 : Configuration du Hub, Caddy et déploiement Compose

**Files:**
- Create: `hub/Dockerfile`
- Create: `hub/jupyterhub_config.py`
- Create: `deploy/docker-compose.yml`, `deploy/Caddyfile`, `deploy/.env.example`, `deploy/README.md`
- Test: `tests/integration/pytest.ini`, `tests/integration/conftest.py`, `tests/integration/test_session.py` (premier test)

**Interfaces:**
- Consumes : `ComptesJWTAuthenticator` (Task 2), `apply_limits` (Task 1), image `ros-lab:0.1.0` (Task 3).
- Produces :
  - Hub joignable en `https://$DOMAIN` ; login `GET /hub/jwt_login?token=…` ; API `https://$DOMAIN/hub/api`.
  - Service `platform-admin` avec jeton `HUB_ADMIN_TOKEN` (scopes `admin:users`, `admin:servers`, `access:servers`, `read:users`) — utilisé par les tests et plus tard par le service Comptes.
  - Conteneurs étudiants nommés `jupyter-<nom>`, volume `ros-lab-home-<nom>`, réseau `ros-lab-net`.
  - Fixtures de test `hub` (classe `Hub` avec `login`, `start`, `stop`, `run`) et `docker_client`.
  - Variables d'environnement : `JWT_SECRET`, `JUPYTERHUB_CRYPT_KEY`, `HUB_ADMIN_TOKEN`, `DOMAIN`, `ROS_LAB_IMAGE`, `ACTIVE_SERVER_LIMIT`, `IDLE_TIMEOUT_SECONDS`.

- [ ] **Step 1 : Écrire les helpers et le premier test d'intégration**

`tests/integration/pytest.ini` :
```ini
[pytest]
markers =
    limit: nécessite ACTIVE_SERVER_LIMIT=2 sur le Hub
    cull: nécessite IDLE_TIMEOUT_SECONDS=90 sur le Hub
```

`tests/integration/conftest.py` :
```python
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
            return r
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
        ws.send(json.dumps(["stdin", f"{command}; echo __END_\"\"{tag}__\r"]))
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
        name = f"it-{uuid.uuid4().hex[:8]}"
        assert hub.login(name, plan).status_code == 302
        hub.start(name)
        created.append(name)
        return name

    yield _make
    for name in created:
        hub.stop(name)
        hub.api("DELETE", f"/users/{name}")
```

`tests/integration/test_session.py` :
```python
# Convention : le terminal renvoie aussi l'écho de la commande tapée. On coupe
# les mots attendus avec "" dans la commande (rcl""py) pour que seul le
# résultat réel contienne le mot entier (rclpy).


def test_student_gets_a_ros_terminal(student, hub):
    name = student()
    out = hub.run(name, "ros2 pkg list | grep -x rcl\"\"py")
    assert "rclpy" in out
```

- [ ] **Step 2 : Vérifier que le test échoue**

Run : `cd tests/integration && HUB_ADMIN_TOKEN=x JWT_SECRET=y python -m pytest -v`
Expected : FAIL avec `requests.exceptions.ConnectionError` (aucun Hub ne tourne).

- [ ] **Step 3 : Écrire l'image Hub et sa configuration**

`hub/Dockerfile` :
```dockerfile
FROM quay.io/jupyterhub/jupyterhub:5.2.1
COPY requirements.txt /srv/hub/requirements.txt
RUN pip install --no-cache-dir -r /srv/hub/requirements.txt
COPY rosacademy_hub /srv/hub/rosacademy_hub
COPY jupyterhub_config.py /srv/hub/jupyterhub_config.py
ENV PYTHONPATH=/srv/hub
RUN mkdir -p /srv/hub/data
WORKDIR /srv/hub
CMD ["jupyterhub", "-f", "/srv/hub/jupyterhub_config.py"]
```

`hub/jupyterhub_config.py` :
```python
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
```

- [ ] **Step 4 : Écrire Compose, Caddy et l'exemple d'environnement**

`deploy/docker-compose.yml` :
```yaml
services:
  hub:
    build: ../hub
    container_name: hub
    restart: unless-stopped
    environment:
      JWT_SECRET: ${JWT_SECRET:?}
      JUPYTERHUB_CRYPT_KEY: ${JUPYTERHUB_CRYPT_KEY:?}
      HUB_ADMIN_TOKEN: ${HUB_ADMIN_TOKEN:?}
      ROS_LAB_IMAGE: ${ROS_LAB_IMAGE:-ros-lab:0.1.0}
      ACTIVE_SERVER_LIMIT: ${ACTIVE_SERVER_LIMIT:-35}
      IDLE_TIMEOUT_SECONDS: ${IDLE_TIMEOUT_SECONDS:-1200}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - hub-data:/srv/hub/data
    networks: [public, ros-lab-net]

  caddy:
    image: caddy:2.8
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    environment:
      DOMAIN: ${DOMAIN:-localhost}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
    networks: [public]

networks:
  public: {}
  ros-lab-net:
    name: ros-lab-net
    internal: true   # pas de sortie Internet pour les conteneurs étudiants

volumes:
  hub-data: {}
  caddy-data: {}
```

`deploy/Caddyfile` :
```
{$DOMAIN} {
	reverse_proxy hub:8000
}
```

`deploy/.env.example` :
```
DOMAIN=localhost
JWT_SECRET=remplacer-par-openssl-rand-hex-32
JUPYTERHUB_CRYPT_KEY=remplacer-par-openssl-rand-hex-32
HUB_ADMIN_TOKEN=remplacer-par-openssl-rand-hex-32
ROS_LAB_IMAGE=ros-lab:0.1.0
ACTIVE_SERVER_LIMIT=35
IDLE_TIMEOUT_SECONDS=1200
```

- [ ] **Step 5 : Démarrer la pile et vérifier que le test passe**

Run :
```bash
cd deploy
cat > .env <<EOF
DOMAIN=localhost
JWT_SECRET=$(openssl rand -hex 32)
JUPYTERHUB_CRYPT_KEY=$(openssl rand -hex 32)
HUB_ADMIN_TOKEN=$(openssl rand -hex 32)
EOF
docker compose up -d --build
set -a; . ./.env; set +a
cd ../tests/integration && python -m pytest test_session.py::test_student_gets_a_ros_terminal -v
```
Expected : PASS (premier démarrage de conteneur ≤ 120 s).

Si le test échoue : `docker logs hub` et `docker logs jupyter-<nom>` avant toute modification.

- [ ] **Step 6 : Écrire le runbook `deploy/README.md`**

````markdown
# Déploiement du moteur de sessions

## Prérequis
- Un serveur Linux avec Docker et le plugin Compose (≈16 vCPU / 64 Go pour 30 à 40 sessions).
- Un nom de domaine pointant vers le serveur (ports 80 et 443 ouverts).

## Installation
1. `docker build -t ros-lab:0.1.0 images/ros-lab`
2. `cp deploy/.env.example deploy/.env` puis remplacer chaque secret par `openssl rand -hex 32` et `DOMAIN` par le domaine.
3. `cd deploy && docker compose up -d --build`

## Tester un accès étudiant
```bash
set -a; . deploy/.env; set +a
TOKEN=$(python scripts/mint_token.py --sub essai --plan free)
echo "https://$DOMAIN/hub/jwt_login?token=$TOKEN"
```
Ouvrir le lien, puis `https://$DOMAIN/user/essai/terminals/1`.

## Mettre à jour l'image étudiant
Construire `ros-lab:<nouvelle version>`, changer `ROS_LAB_IMAGE` dans `.env`, `docker compose up -d`. Les conteneurs déjà lancés gardent l'ancienne image jusqu'à leur arrêt ; les volumes ne sont pas touchés.

## Diagnostic
- `docker logs hub` : connexions refusées (`Connexion par jeton refusée`), démarrages, arrêts pour inactivité.
- `docker ps --filter name=jupyter-` : sessions actives.
````

- [ ] **Step 7 : Commit**

```bash
git add hub/Dockerfile hub/jupyterhub_config.py deploy tests/integration
git commit -m "feat(deploy): JupyterHub + DockerSpawner + Caddy, first end-to-end terminal test"
```

---

### Task 5 : Tests d'isolation, de sécurité et de robustesse

**Files:**
- Modify: `tests/integration/test_session.py`
- Modify (seulement si un test révèle un défaut) : `hub/jupyterhub_config.py`, `images/ros-lab/*`

**Interfaces:**
- Consumes : fixtures `hub`, `student`, `docker_client` et `Hub.run/start/stop/login` (Task 4) ; `mint` de `conftest.py`.
- Produces : la suite d'intégration complète utilisée par la CI (Task 6), avec les marqueurs `limit` et `cull`.

- [ ] **Step 1 : Ajouter les tests**

Ajouter à `tests/integration/test_session.py` :
```python
import json
import ssl
import time
import uuid

import pytest
import websocket

from conftest import ADMIN_TOKEN, WS_BASE, mint

GiB = 1024 ** 3


def test_invalid_token_is_refused(hub):
    name = f"it-{uuid.uuid4().hex[:8]}"
    assert hub.login(name, token="not-a-jwt").status_code == 403
    expired = mint(name, ttl=-120)
    assert hub.login(name, token=expired).status_code == 403
    assert hub.api("GET", f"/users/{name}").status_code == 404


def test_container_is_hardened_free_plan(student, hub, docker_client):
    name = student("free")
    cfg = docker_client.containers.get(f"jupyter-{name}").attrs["HostConfig"]
    assert cfg["CapDrop"] == ["ALL"]
    assert "no-new-privileges" in cfg["SecurityOpt"]
    assert cfg["PidsLimit"] == 256
    assert cfg["Memory"] == 2 * GiB
    assert cfg["NanoCpus"] == 1_000_000_000
    assert "USER=etudiant" in hub.run(name, "echo USER=$(whoami)")
    assert "command not found" in hub.run(name, "sudo -n true 2>&1")


def test_pro_plan_gets_bigger_limits(student, docker_client):
    name = student("pro")
    cfg = docker_client.containers.get(f"jupyter-{name}").attrs["HostConfig"]
    assert cfg["Memory"] == 4 * GiB
    assert cfg["NanoCpus"] == 2_000_000_000
    assert cfg["PidsLimit"] == 512


def test_no_internet_from_student_container(student, hub):
    name = student()
    out = hub.run(
        name,
        "python3 -c \"import urllib.request; urllib.request.urlopen('https://example.com', timeout=5)\" "
        "2>/dev/null && echo NET-\"\"ON || echo NET-\"\"OFF",
        timeout=30,
    )
    assert "NET-OFF" in out
    assert "NET-ON" not in out


def test_dds_is_isolated_between_students(student, hub):
    a, b = student(), student()
    hub.run(a, "nohup ros2 topic pub /secret_a std_msgs/msg/String '{data: x}' -r 2 >/dev/null 2>&1 &")
    time.sleep(5)
    assert "/secret_a" in hub.run(a, "ros2 topic list", timeout=30)  # témoin positif
    assert "/secret_a" not in hub.run(b, "ros2 topic list", timeout=30)


def test_rosbridge_is_reachable_through_proxy(student):
    name = student()
    ws = websocket.create_connection(
        f"{WS_BASE}/user/{name}/rosbridge/",
        header=[f"Authorization: token {ADMIN_TOKEN}"],
        sslopt={"cert_reqs": ssl.CERT_NONE},
        timeout=60,
    )
    ws.send(json.dumps({"op": "call_service", "service": "/rosapi/topics", "id": "t1"}))
    reply = json.loads(ws.recv())
    ws.close()
    assert reply["op"] == "service_response" and reply["result"] is True


def test_workspace_persists_across_restart(student, hub):
    name = student()
    hub.run(name, "mkdir -p ~/ws/src && echo bonjour > ~/ws/src/note.txt")
    hub.stop(name)
    hub.start(name)
    assert "bonjour" in hub.run(name, "cat ~/ws/src/note.txt")


@pytest.mark.limit
def test_server_limit_returns_429(student, hub):
    student(), student()  # ACTIVE_SERVER_LIMIT=2 : le Hub est plein
    third = f"it-{uuid.uuid4().hex[:8]}"
    assert hub.login(third).status_code == 302
    r = hub.api("POST", f"/users/{third}/server")
    assert r.status_code == 429
    hub.api("DELETE", f"/users/{third}")


@pytest.mark.cull
def test_idle_server_is_culled(student, hub):
    name = student()  # IDLE_TIMEOUT_SECONDS=90, vérification toutes les 30 s
    deadline = time.time() + 240
    while time.time() < deadline:
        if not hub.api("GET", f"/users/{name}").json().get("servers"):
            return
        time.sleep(10)
    pytest.fail("le serveur inactif n'a pas été arrêté en 240 s")
```

- [ ] **Step 2 : Lancer la suite principale**

Run : `set -a; . deploy/.env; set +a; cd tests/integration && python -m pytest -v -m "not limit and not cull"`
Expected : 8 tests PASS. Si un test échoue, appliquer superpowers:systematic-debugging : lire `docker logs hub`, `docker inspect jupyter-<nom>`, corriger la configuration (pas le test), relancer.

- [ ] **Step 3 : Lancer le test de capacité**

Run :
```bash
cd deploy && ACTIVE_SERVER_LIMIT=2 docker compose up -d hub && cd ..
cd tests/integration && python -m pytest -v -m limit
```
Expected : `test_server_limit_returns_429` PASS.

- [ ] **Step 4 : Lancer le test d'arrêt pour inactivité**

Run :
```bash
cd deploy && IDLE_TIMEOUT_SECONDS=90 docker compose up -d hub && cd ..
cd tests/integration && python -m pytest -v -m cull
cd ../../deploy && docker compose up -d hub   # retour aux valeurs de .env
```
Expected : `test_idle_server_is_culled` PASS en moins de 240 s.

- [ ] **Step 5 : Commit**

```bash
git add tests/integration hub images
git commit -m "test(integration): hardening, plan limits, DDS isolation, persistence, capacity, idle cull"
```

---

### Task 6 : Intégration continue (GitHub Actions)

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes : `hub/tests` (Tasks 1–2), `tests/image/test_image.sh` (Task 3), `deploy/` et `tests/integration` (Tasks 4–5).
- Produces : un pipeline qui bloque toute fusion si un test échoue.

- [ ] **Step 1 : Écrire le workflow**

`.github/workflows/ci.yml` :
```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:

jobs:
  unit:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r hub/requirements-dev.txt
      - run: cd hub && python -m pytest -v

  image:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t ros-lab:0.1.0 images/ros-lab
      - run: tests/image/test_image.sh

  integration:
    needs: [unit, image]
    runs-on: ubuntu-22.04
    timeout-minutes: 40
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r hub/requirements-dev.txt
      - run: docker build -t ros-lab:0.1.0 images/ros-lab
      - name: Secrets de test
        run: |
          {
            echo "DOMAIN=localhost"
            echo "JWT_SECRET=$(openssl rand -hex 32)"
            echo "JUPYTERHUB_CRYPT_KEY=$(openssl rand -hex 32)"
            echo "HUB_ADMIN_TOKEN=$(openssl rand -hex 32)"
          } > deploy/.env
      - run: cd deploy && docker compose up -d --build
      - name: Suite principale
        run: |
          set -a; . deploy/.env; set +a
          cd tests/integration && python -m pytest -v -m "not limit and not cull"
      - name: Capacité
        run: |
          set -a; . deploy/.env; set +a
          (cd deploy && ACTIVE_SERVER_LIMIT=2 docker compose up -d hub)
          cd tests/integration && python -m pytest -v -m limit
      - name: Inactivité
        run: |
          set -a; . deploy/.env; set +a
          (cd deploy && IDLE_TIMEOUT_SECONDS=90 docker compose up -d hub)
          cd tests/integration && python -m pytest -v -m cull
      - if: failure()
        run: docker logs hub; docker ps -a
```

- [ ] **Step 2 : Vérifier localement la syntaxe**

Run : `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ok')"`
Expected : `ok`

- [ ] **Step 3 : Commit et vérifier le premier passage en CI**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: unit, image and integration pipelines"
git push -u origin main
```
Expected : les trois jobs `unit`, `image`, `integration` sont verts sur GitHub.

---

## Couverture de la spec

| Exigence (spec) | Task |
|---|---|
| Vrai ROS 2 Humble par étudiant, Python et C++ compilables | 3, 4 |
| JupyterHub + DockerSpawner, auth déléguée au service Comptes | 2, 4 |
| Limites CPU/RAM/processus par formule `free` / `pro` | 1, 5 |
| Non-root, sans `sudo`, `cap_drop ALL`, `no-new-privileges` | 3, 4, 5 |
| Pas d'Internet dans les conteneurs | 4, 5 |
| Isolation DDS (`ROS_LOCALHOST_ONLY=1`) | 3, 5 |
| Volume personnel persistant | 4, 5 |
| rosbridge pour la vue 2D via le proxy du Hub | 3, 5 |
| Arrêt après 20 min d'inactivité | 4, 5 |
| Serveur plein → file d'attente (429 exploitable) | 4, 5 |
| HTTPS via Caddy, jetons ≤ 1 h | 2, 4 |
| Tests de l'image et CI | 3, 6 |

Hors de ce plan (autres sous-projets) : écran d'attente, avertissement 5 min avant l'arrêt et reconnexion du terminal (Lab UI) ; quota de minutes par mois et émission des jetons (service Comptes) ; limite de 1 Go du volume (dépend de l'hébergeur) ; journaux centralisés et alertes 80 % (à ajouter au déploiement de production).

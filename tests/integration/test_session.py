import json
import ssl
import time
import uuid

import pytest
import websocket

from conftest import ADMIN_TOKEN, WS_BASE, mint

GiB = 1024 ** 3

# Convention : le terminal renvoie aussi l'écho de la commande tapée. On coupe
# les mots attendus avec "" dans la commande (rcl""py) pour que seul le
# résultat réel contienne le mot entier (rclpy).


def test_student_gets_a_ros_terminal(student, hub):
    name = student()
    out = hub.run(name, "ros2 pkg list | grep -x rcl\"\"py")
    assert "rclpy" in out


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

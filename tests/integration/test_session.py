import json
import ssl
import time
import uuid

import pytest
import requests
import websocket

from conftest import ADMIN_TOKEN, BASE, WS_BASE, mint

GiB = 1024 ** 3

# Convention : le terminal renvoie aussi l'écho de la commande tapée. On coupe
# les mots attendus avec "" dans la commande (rcl""py) pour que seul le
# résultat réel contienne le mot entier (rclpy).


def test_student_gets_a_ros_terminal(student, hub):
    name = student()
    out = hub.run(name, "ros2 pkg list | grep -x rcl\"\"py")
    assert "rclpy" in out


def test_invalid_token_is_refused(hub):
    name = f"it{uuid.uuid4().hex[:8]}"
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
    assert cfg["CpuPeriod"] == 100_000
    assert cfg["CpuQuota"] == 100_000
    assert cfg["Init"] is True
    assert "USER=etudiant" in hub.run(name, "echo USER=$(whoami)")
    assert "command not found" in hub.run(name, "sudo -n true 2>&1")


def test_pro_plan_gets_bigger_limits(student, docker_client):
    name = student("pro")
    cfg = docker_client.containers.get(f"jupyter-{name}").attrs["HostConfig"]
    assert cfg["Memory"] == 4 * GiB
    assert cfg["CpuPeriod"] == 100_000
    assert cfg["CpuQuota"] == 200_000
    assert cfg["PidsLimit"] == 512


def test_no_internet_from_student_container(student, hub):
    name = student()
    out = hub.run(
        name,
        "python3 -c \"import socket; socket.create_connection(('hub', 8081), 5)\" "
        "&& echo LAN-\"\"OK || echo LAN-\"\"KO; "
        "python3 -c \"import urllib.request; urllib.request.urlopen('https://example.com', timeout=5)\" "
        "2>/dev/null && echo NET-\"\"ON || echo NET-\"\"OFF",
        timeout=30,
    )
    assert "LAN-OK" in out  # témoin positif : la pile réseau fonctionne
    assert "NET-OFF" in out
    assert "NET-ON" not in out


def test_dds_is_isolated_between_students(student, hub):
    a, b = student(), student()
    hub.run(
        a,
        "setsid nohup ros2 topic pub /secret_a std_msgs/msg/String '{data: x}' -r 2 "
        ">/dev/null 2>&1 < /dev/null &",
    )
    seen = False
    for _ in range(5):  # témoin positif : le sujet est visible chez a
        if "/secret_a" in hub.run(a, "ros2 topic list --spin-time 3", timeout=30):
            seen = True
            break
        time.sleep(3)
    assert seen, "/secret_a jamais visible chez l'étudiant a : test non concluant"
    out_b = hub.run(b, "ros2 topic list --spin-time 10", timeout=40)
    assert "/secret_a" not in out_b


def test_students_cannot_reach_each_other(student, hub, docker_client):
    a, b = student(), student()
    nets_a = docker_client.containers.get(f"jupyter-{a}").attrs["NetworkSettings"]["Networks"]
    nets_b = docker_client.containers.get(f"jupyter-{b}").attrs["NetworkSettings"]["Networks"]
    assert set(nets_a) == {f"ros-lab-{a}"} and set(nets_b) == {f"ros-lab-{b}"}
    ip_b = nets_b[f"ros-lab-{b}"]["IPAddress"]
    probe = "import socket,sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), 5)"
    # témoin positif : le Hub atteint le serveur Jupyter de b
    code, _ = docker_client.containers.get("hub").exec_run(["python3", "-c", probe, ip_b, "8888"])
    assert code == 0
    out = hub.run(
        a,
        f"python3 -c \"{probe}\" hub 8081 && echo HUB-\"\"OK || echo HUB-\"\"KO; "
        f"python3 -c \"{probe}\" {ip_b} 8888 2>/dev/null && echo PAIR-\"\"ON || echo PAIR-\"\"OFF; "
        f"python3 -c \"{probe}\" jupyter-{b} 8888 2>/dev/null && echo NOM-\"\"ON || echo NOM-\"\"OFF",
        timeout=40,
    )
    assert "HUB-OK" in out
    assert "PAIR-OFF" in out and "PAIR-ON" not in out
    assert "NOM-OFF" in out and "NOM-ON" not in out


def test_lab_network_is_removed_after_stop(student, hub, docker_client):
    name = student()
    net = docker_client.networks.get(f"ros-lab-{name}")
    assert net.attrs["Internal"] is True
    assert {c["Name"] for c in net.attrs["Containers"].values()} == {"hub", f"jupyter-{name}"}
    hub.stop(name)
    assert not docker_client.networks.list(names=[f"ros-lab-{name}"])


def test_rosbridge_is_reachable_through_proxy(student):
    name = student()
    ws = websocket.create_connection(
        f"{WS_BASE}/user/{name}/rosbridge/",
        header=[f"Authorization: token {ADMIN_TOKEN}"],
        sslopt={"cert_reqs": ssl.CERT_NONE},
        timeout=10,
    )
    reply = None
    try:
        # rosapi peut ne pas être encore découvert : on réessaie jusqu'à 20 s.
        deadline = time.time() + 20
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            ws.send(json.dumps(
                {"op": "call_service", "service": "/rosapi/topics", "id": f"t{attempt}"}
            ))
            try:
                reply = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if reply.get("op") == "service_response" and reply.get("result") is True:
                break
            time.sleep(2)
    finally:
        ws.close()
    assert reply is not None, "aucune réponse de rosbridge"
    assert reply["op"] == "service_response" and reply["result"] is True, reply


def test_workspace_persists_across_restart(student, hub):
    name = student()
    hub.run(name, "mkdir -p ~/ws/src && echo bonjour > ~/ws/src/note.txt")
    hub.stop(name)
    hub.start(name)
    assert "bonjour" in hub.run(name, "cat ~/ws/src/note.txt")


@pytest.mark.limit
def test_server_limit_returns_429(student, hub):
    student(), student()  # ACTIVE_SERVER_LIMIT=2 : le Hub est plein
    third = f"it{uuid.uuid4().hex[:8]}"
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


def browser_login(name, plan="free"):
    """Session navigateur : cookie du Hub obtenu par /hub/jwt_login."""
    s = requests.Session()
    s.verify = False
    r = s.get(f"{BASE}/hub/jwt_login", params={"token": mint(name, plan)}, allow_redirects=False)
    assert r.status_code == 302
    return s, r


def test_login_redirects_to_lab_without_jwt():
    name = f"it{uuid.uuid4().hex[:8]}"
    _, r = browser_login(name)
    assert r.headers["Location"] == "/lab/"
    s, _ = browser_login(name)
    r = s.get(f"{BASE}/hub/jwt_login",
              params={"token": mint(name), "next": "/lab/?open=ws/a.py"}, allow_redirects=False)
    assert r.headers["Location"] == "/lab/?open=ws/a.py"


def test_lab_token_requires_same_site_cookie(hub):
    name = f"it{uuid.uuid4().hex[:8]}"
    assert requests.get(f"{BASE}/hub/lab_token", verify=False).status_code == 403
    s, _ = browser_login(name)
    r = s.get(f"{BASE}/hub/lab_token", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403
    r = s.get(f"{BASE}/hub/lab_token", headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "no-store"
    body = r.json()
    assert body["user"] == name and body["server_url"] == f"/user/{name}/"
    # un jeton du Lab UI ne permet pas d'en fabriquer d'autres
    r = requests.get(f"{BASE}/hub/lab_token", verify=False,
                     headers={"Authorization": f"token {body['token']}"})
    assert r.status_code == 403
    hub.api("DELETE", f"/users/{name}")


def test_lab_token_is_scoped_to_its_owner(student, hub):
    alice, bob = student(), student()
    s, _ = browser_login(alice)
    token = s.get(f"{BASE}/hub/lab_token").json()["token"]
    auth = {"Authorization": f"token {token}"}

    def get(path):
        return requests.get(f"{BASE}{path}", headers=auth, verify=False, allow_redirects=False)

    assert get(f"/user/{alice}/api/contents").status_code == 200
    assert get(f"/hub/api/users/{alice}").json()["servers"][""]["ready"] is True
    assert get(f"/user/{bob}/api/contents").status_code in (302, 403)
    assert get(f"/hub/api/users/{bob}").status_code == 404
    assert get("/hub/api/users").status_code == 403
    r = requests.post(f"{BASE}/hub/api/users/{bob}/tokens", headers=auth, verify=False)
    assert r.status_code in (403, 404)
    # comme un navigateur : le jeton passe dans l'URL, accepté seulement pour un WebSocket
    ws = websocket.create_connection(
        f"{WS_BASE}/user/{alice}/rosbridge/?token={token}",
        header=["Sec-Fetch-Mode: websocket"],
        sslopt={"cert_reqs": ssl.CERT_NONE}, timeout=30,
    )
    ws.close()
    with pytest.raises(websocket.WebSocketBadStatusException):
        websocket.create_connection(
            f"{WS_BASE}/user/{bob}/rosbridge/?token={token}",
            header=["Sec-Fetch-Mode: websocket"],
            sslopt={"cert_reqs": ssl.CERT_NONE}, timeout=30,
        )


def test_student_served_pages_are_sandboxed(student, hub):
    """Une page HTML servie par un conteneur étudiant ne doit pas partager l'origine du Lab UI."""
    name = student()
    r = hub.s.put(f"{BASE}/user/{name}/api/contents/piege.html",
                  json={"type": "file", "format": "text", "content": "<script>fetch('/hub/lab_token')</script>"})
    assert r.status_code in (200, 201)
    r = hub.s.get(f"{BASE}/user/{name}/files/piege.html")
    assert r.status_code == 200
    csp = r.headers["Content-Security-Policy"]
    assert csp.startswith("sandbox") and "allow-same-origin" not in csp

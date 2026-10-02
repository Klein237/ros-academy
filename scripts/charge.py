#!/usr/bin/env python3
"""Test de charge : N sessions de lab simultanées, puis vérification de la limite du Hub.

Avant chaque ouverture de session ou d'atelier (spec : 30 à 40 sessions ; la file
d'attente se déclenche au-delà). À lancer sur le serveur, ou depuis un poste qui
l'atteint, avec les secrets du déploiement :

    set -a; . deploy/.env; set +a
    python scripts/charge.py --sessions 35 --limite 35

Pour chaque session : connexion (jeton signé comme Comptes), démarrage du conteneur,
commande ROS dans un terminal (`ros2 topic list`, qui lance le démon ROS), puis une
activité régulière pendant --duree secondes (une commande toutes les 30 s par session).
Si --limite est donnée, une session de plus doit être refusée (HTTP 429 : c'est ce qui
déclenche la file d'attente du Lab UI). Tout est nettoyé à la fin, même en cas d'échec.

Dépendances : pip install requests websocket-client PyJWT
Code de sortie : 0 si toutes les sessions ont fonctionné dans les délais, 1 sinon.
"""

import argparse
import json
import os
import ssl
import statistics
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import jwt
import requests
import urllib3
import websocket

urllib3.disable_warnings()  # certificat local auto-signé de Caddy en test ; --verifier pour un vrai domaine


class Hub:
    def __init__(self, base, admin_token, jwt_secret, verify):
        self.base = base.rstrip("/")
        self.ws_base = self.base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        self.secret = jwt_secret
        self.verify = verify
        self.admin_token = admin_token
        self.local = threading.local()

    @property
    def s(self):
        if not hasattr(self.local, "s"):
            self.local.s = requests.Session()
            self.local.s.verify = self.verify
            self.local.s.headers["Authorization"] = f"token {self.admin_token}"
        return self.local.s

    def api(self, method, path, **kw):
        return self.s.request(method, f"{self.base}/hub/api{path}", timeout=30, **kw)

    def login(self, name):
        now = int(time.time())
        token = jwt.encode({"sub": name, "plan": "free", "aud": "ros-lab", "iat": now, "exp": now + 300},
                           self.secret, algorithm="HS256")
        r = requests.get(f"{self.base}/hub/jwt_login", params={"token": token}, verify=self.verify,
                         allow_redirects=False, timeout=30)
        if r.status_code != 302:
            raise RuntimeError(f"connexion refusée ({r.status_code})")

    def start(self, name, timeout):
        r = self.api("POST", f"/users/{name}/server")
        if r.status_code == 429:
            return "plein"
        if r.status_code not in (201, 202, 400):
            raise RuntimeError(f"démarrage refusé : {r.status_code} {r.text[:200]}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            server = (self.api("GET", f"/users/{name}").json().get("servers") or {}).get("")
            if server and server.get("ready"):
                return "pret"
            time.sleep(1)
        raise TimeoutError(f"pas prêt après {timeout} s")

    def run(self, name, command, timeout=90):
        r = self.s.post(f"{self.base}/user/{name}/api/terminals", timeout=30)
        r.raise_for_status()
        term = r.json()["name"]
        ws = websocket.create_connection(
            f"{self.ws_base}/user/{name}/terminals/websocket/{term}",
            header=[f"Authorization: token {self.admin_token}"],
            sslopt={} if self.verify else {"cert_reqs": ssl.CERT_NONE}, timeout=30)
        tag = uuid.uuid4().hex
        try:
            ws.send(json.dumps(["stdin", f"{command}\recho __FIN_\"\"{tag}__\r"]))
            out, deadline = "", time.time() + timeout
            ws.settimeout(5)
            while f"__FIN_{tag}__" not in out and time.time() < deadline:
                try:
                    msg = json.loads(ws.recv())
                except websocket.WebSocketTimeoutException:
                    continue
                if msg[0] == "stdout":
                    out += msg[1]
        finally:
            ws.close()
            self.s.delete(f"{self.base}/user/{name}/api/terminals/{term}", timeout=30)
        if f"__FIN_{tag}__" not in out:
            raise TimeoutError(f"commande sans fin : {command}")
        return out

    def remove(self, name):
        self.api("DELETE", f"/users/{name}/server")
        for _ in range(60):
            r = self.api("GET", f"/users/{name}")
            if r.status_code == 404 or not r.json().get("servers"):
                break
            time.sleep(2)
        self.api("DELETE", f"/users/{name}")


def host_snapshot():
    """Charge et mémoire de la machine qui lance le script (le serveur, si lancé dessus)."""
    try:
        load = open("/proc/loadavg").read().split()[:3]
        mem = {k: int(v.split()[0]) for k, _, v in (line.partition(":") for line in open("/proc/meminfo"))}
        used = 100 * (1 - mem["MemAvailable"] / mem["MemTotal"])
        return f"charge {' / '.join(load)} ; mémoire utilisée {used:.0f} % de {mem['MemTotal'] / 1024 ** 2:.1f} Go"
    except OSError:
        return "indisponible"


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions", type=int, default=35)
    ap.add_argument("--limite", type=int, help="ACTIVE_SERVER_LIMIT du Hub : une session de plus doit être refusée")
    ap.add_argument("--duree", type=int, default=0, help="secondes d'activité simulée une fois toutes les sessions prêtes")
    ap.add_argument("--max-demarrage", type=float, default=120, help="seuil du 95e centile de démarrage (s)")
    ap.add_argument("--base", default=os.environ.get("BASE_URL") or f"https://{os.environ.get('DOMAIN', 'localhost')}")
    ap.add_argument("--verifier", action="store_true", help="vérifier le certificat TLS (vrai domaine)")
    args = ap.parse_args()

    hub = Hub(args.base, os.environ["HUB_ADMIN_TOKEN"], os.environ["JWT_SECRET"], args.verifier)
    run_id = uuid.uuid4().hex[:6]
    names = [f"charge-{run_id}-{i:02d}" for i in range(args.sessions)]
    results, errors = {}, {}
    print(f"{args.sessions} sessions sur {args.base} — machine : {host_snapshot()}", flush=True)

    def session(name):
        t0 = time.time()
        hub.login(name)
        state = hub.start(name, timeout=300)
        if state != "pret":
            raise RuntimeError("serveur plein (429) avant la limite attendue")
        ready = time.time() - t0
        t1 = time.time()
        out = hub.run(name, "ros2 topic list")
        if "/rosout" not in out and "/parameter_events" not in out:
            raise RuntimeError(f"ROS ne répond pas : {out[-200:]!r}")
        return {"demarrage": ready, "ros": time.time() - t1}

    created = list(names)
    try:
        t_all = time.time()
        with ThreadPoolExecutor(max_workers=min(args.sessions, 40)) as pool:
            futures = {pool.submit(session, n): n for n in names}
            for f in as_completed(futures):
                n = futures[f]
                try:
                    results[n] = f.result()
                    print(f"  {n} prêt en {results[n]['demarrage']:.0f} s, ROS en {results[n]['ros']:.1f} s", flush=True)
                except Exception as exc:  # noqa: BLE001
                    errors[n] = f"{exc.__class__.__name__}: {exc}"
                    print(f"  {n} ÉCHEC : {errors[n]}", flush=True)
        print(f"Toutes les sessions traitées en {time.time() - t_all:.0f} s — machine : {host_snapshot()}", flush=True)

        if args.duree and results:
            print(f"Activité simulée pendant {args.duree} s…", flush=True)
            end, latencies = time.time() + args.duree, []
            while time.time() < end:
                with ThreadPoolExecutor(max_workers=min(len(results), 40)) as pool:
                    for n, f in [(n, pool.submit(lambda n=n: (time.time(), hub.run(n, "echo actif")))) for n in results]:
                        try:
                            start, _ = f.result()
                            latencies.append(time.time() - start)
                        except Exception as exc:  # noqa: BLE001
                            errors[n] = f"activité : {exc.__class__.__name__}: {exc}"
                print(f"  commande au terminal : médiane {statistics.median(latencies):.1f} s, "
                      f"max {max(latencies):.1f} s — machine : {host_snapshot()}", flush=True)
                time.sleep(max(0, min(30, end - time.time())))

        refused_ok = None
        if args.limite is not None and args.sessions >= args.limite:
            extra = f"charge-{run_id}-plus"
            created.append(extra)
            hub.login(extra)
            refused_ok = hub.start(extra, timeout=30) == "plein"
            print(f"Session n° {args.sessions + 1} : {'refusée (429), la file d’attente prend le relais' if refused_ok else 'ACCEPTÉE alors que le Hub devrait être plein'}",
                  flush=True)
    finally:
        print("Nettoyage…", flush=True)
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(lambda n: hub.remove(n), created))

    starts = [r["demarrage"] for r in results.values()]
    ok = not errors and len(results) == args.sessions and refused_ok is not False
    if starts:
        p95 = pct(starts, 95)
        ok = ok and p95 <= args.max_demarrage
        print(f"Démarrage : médiane {statistics.median(starts):.0f} s, 95e centile {p95:.0f} s, max {max(starts):.0f} s "
              f"(seuil {args.max_demarrage:.0f} s)")
        print(f"ROS (ros2 topic list) : médiane {statistics.median(r['ros'] for r in results.values()):.1f} s")
    print(f"Résultat : {len(results)}/{args.sessions} sessions fonctionnelles, {len(errors)} échec(s) — "
          f"{'RÉUSSI' if ok else 'ÉCHEC'}")
    for n, e in errors.items():
        print(f"  {n} : {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

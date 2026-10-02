import io
import os
import tarfile
import uuid

import pytest

docker = pytest.importorskip("docker")

from academy_content.verification import (
    Busy,
    InvalidStudent,
    Resultat,
    exercise_archive,
    make_slots,
    verify_exercise,
    volume_name,
)
from conftest import REPO_CONTENT, make_module

IMAGE = os.environ.get("ROS_LAB_IMAGE")
needs_docker = pytest.mark.skipif(not IMAGE, reason="ROS_LAB_IMAGE non défini (tests Docker)")


@pytest.mark.parametrize("bad", ["", "admin", "u", "u12a", "../u1", "u1/../x", "U1", "u1 ", "ros-lab-home-u1", "u" + "1" * 13])
def test_volume_name_only_for_student_accounts(bad):
    with pytest.raises(InvalidStudent):
        volume_name(bad)
    assert volume_name("u42") == "ros-lab-home-u42"


def test_archive_hides_solution_hints_and_explanation(tmp_path):
    base = make_module(tmp_path)
    (base / "exercice" / "depart").mkdir(exist_ok=True)
    (base / "exercice" / "depart" / "a.py").write_text("x = 1\n")
    with tarfile.open(fileobj=io.BytesIO(exercise_archive(base))) as tar:
        names = set(tar.getnames())
        assert "tmp/exercice/check.sh" in names and "tmp/exercice/depart/a.py" in names
        assert not [n for n in names if "solution" in n or "indices" in n or "explication" in n]
        assert tar.getmember("tmp/exercice/check.sh").mode == 0o755
        assert {m.uid for m in tar.getmembers()} == {1000}


class FakeDocker:
    """Client Docker simulé : enregistre la création du conteneur."""

    def __init__(self, volumes=(), code=0, output=b"verifie\n::code:: 0\n"):
        self._volumes, self.code, self.output, self.created = set(volumes), code, output, []
        fake = self

        class Volumes:
            def get(self, name):
                if name not in fake._volumes:
                    raise docker.errors.NotFound(name)

        class Container:
            def put_archive(self, path, data):
                fake.archive = data

            def start(self):
                pass

            def wait(self, timeout):
                return {"StatusCode": fake.code}

            def logs(self, **kw):
                return fake.output

            def kill(self):
                pass

            def remove(self, **kw):
                fake.removed = kw

        class Containers:
            def create(self, image, **kw):
                fake.created.append((image, kw))
                return Container()

        self.volumes, self.containers = Volumes(), Containers()


def test_container_is_isolated_and_mounts_the_volume_read_only(tmp_path):
    base = make_module(tmp_path)
    fake = FakeDocker(volumes={"ros-lab-home-u7"})
    r = verify_exercise(base, "01-demo", "u7", "ros-lab:test", client=fake)
    assert r == Resultat(True, 0, "verifie")
    image, kw = fake.created[0]
    assert image == "ros-lab:test"
    assert kw["volumes"] == {"ros-lab-home-u7": {"bind": "/eleve", "mode": "ro"}}
    assert kw["network_mode"] == "none" and kw["user"] == "etudiant"
    assert kw["cap_drop"] == ["ALL"] and kw["security_opt"] == ["no-new-privileges"]
    assert kw["pids_limit"] == 256 and kw["mem_limit"] == "2g"
    assert fake.removed == {"force": True, "v": True}


def test_missing_volume_is_not_created(tmp_path):
    fake = FakeDocker()
    r = verify_exercise(make_module(tmp_path), "01-demo", "u7", "img", client=fake)
    assert not r.ok and r.code == 3 and "Commencer l'exercice" in r.journal
    assert fake.created == []


def test_failure_needs_both_exit_code_and_marker(tmp_path):
    base = make_module(tmp_path)
    assert not verify_exercise(base, "01-demo", "u7", "img", client=FakeDocker({"ros-lab-home-u7"}, code=1,
                                                                               output=b"pas encore\n::code:: 1\n")).ok
    # code 0 sans marqueur (script interrompu) : pas une réussite
    assert not verify_exercise(base, "01-demo", "u7", "img", client=FakeDocker({"ros-lab-home-u7"}, output=b"")).ok
    big = verify_exercise(base, "01-demo", "u7", "img", client=FakeDocker({"ros-lab-home-u7"}, code=4,
                                                                          output=b"::trop-gros:: 900\n"))
    assert not big.ok and "200 Mo" in big.journal


def test_concurrency_is_limited(tmp_path):
    base = make_module(tmp_path)
    slots = make_slots(1)
    slots.acquire()  # une vérification déjà en cours
    with pytest.raises(Busy):
        verify_exercise(base, "01-demo", "u7", "img", client=FakeDocker({"ros-lab-home-u7"}), slots=slots, wait=0.1)
    slots.release()
    assert verify_exercise(base, "01-demo", "u7", "img", client=FakeDocker({"ros-lab-home-u7"}), slots=slots).ok
    assert slots.acquire(blocking=False)  # la place a été rendue


# --- Conteneur ROS réel

@needs_docker
def test_official_check_on_the_student_volume():
    """Module Nœud : bug → échec ; check.sh trafiqué dans le volume → ignoré ; solution → réussite."""
    client = docker.from_env()
    student = f"u9{uuid.uuid4().int % 10**9}"
    volume = client.volumes.create(volume_name(student))
    module = REPO_CONTENT / "modules" / "02-noeud"

    def in_student_container(script):
        """Comme le lab de l'étudiant : son volume en /home/etudiant, en écriture."""
        out = client.containers.run(IMAGE, ["bash", "-lc", script], user="etudiant", network_mode="none",
                                    volumes={volume.name: {"bind": "/home/etudiant", "mode": "rw"}}, remove=True,
                                    stdout=True, stderr=True)
        return out.decode()

    try:
        # « Commencer l'exercice » : fichiers de l'exercice puis setup.sh (workspace avec le bug)
        c = client.containers.create(IMAGE, ["bash", "-lc",
                                             "mkdir -p ~/.academy/02-noeud && cp -r /tmp/exercice/. ~/.academy/02-noeud/ "
                                             "&& cd ~ && EXERCICE=~/.academy/02-noeud WS=~/ws/02-noeud-exercice "
                                             "bash ~/.academy/02-noeud/setup.sh"],
                                     user="etudiant", network_mode="none",
                                     volumes={volume.name: {"bind": "/home/etudiant", "mode": "rw"}})
        c.put_archive("/", exercise_archive(module))
        c.start()
        assert c.wait(timeout=600)["StatusCode"] == 0, c.logs().decode()
        c.remove()

        r = verify_exercise(module, "02-noeud", student, IMAGE, client=client)
        assert not r.ok and "n'avance pas" in r.journal, r.journal

        # l'étudiant remplace son check.sh et y écrit « exit 0 » : sans effet, c'est le check.sh publié qui tourne
        in_student_container("printf '#!/bin/bash\\nexit 0\\n' > ~/.academy/02-noeud/check.sh")
        assert not verify_exercise(module, "02-noeud", student, IMAGE, client=client).ok

        # correction (comme le ferait l'étudiant), avec des produits de compilation laissés dans le volume
        in_student_container("sed -i 's/cmd_vell/cmd_vel/' ~/ws/02-noeud-exercice/src/my_pkg/my_pkg/diff_drive_node.py "
                             "&& mkdir -p ~/ws/02-noeud-exercice/build/faux && echo x > ~/ws/02-noeud-exercice/build/faux/f")
        r = verify_exercise(module, "02-noeud", student, IMAGE, client=client)
        assert r.ok and r.code == 0 and "Le robot avance" in r.journal, r.journal
        # le volume de l'étudiant n'a pas été modifié par la vérification
        assert "exit 0" in in_student_container("cat ~/.academy/02-noeud/check.sh")
    finally:
        volume.remove(force=True)
    assert not [c for c in client.containers.list(all=True, filters={"label": "ros-academy.role=verification"})
                if c.labels.get("ros-academy.etudiant") == student]


def test_route_requires_secret_and_calls_the_verifier(store):
    import hashlib
    import hmac

    from fastapi.testclient import TestClient

    from academy_content.app import create_app
    from test_app import SECRET, Runner

    calls = []

    def verifier(module_dir, module_id, student):
        calls.append((module_dir.name, module_id, student))
        if student == "busy":
            raise Busy()
        volume_name(student)
        return Resultat(True, 0, "ok")

    client = TestClient(create_app(store, Runner(), SECRET, cookie_secure=False, verifier=verifier))
    url = "/api/contenus/modules/01-demo/verifier"
    secret = {"X-Academy-Interne": hmac.new(SECRET.encode(), b"contenus-interne", hashlib.sha256).hexdigest()}
    assert client.post(url, json={"etudiant": "u1"}).status_code == 403
    assert client.post(url, json={"etudiant": "u1"}, headers=secret).json() == {"ok": True, "code": 0, "journal": "ok"}
    assert calls == [("01-demo", "01-demo", "u1")]
    assert client.post(url, json={"etudiant": "../etc"}, headers=secret).status_code == 400
    assert client.post(url, json={"etudiant": "busy"}, headers=secret).status_code == 429
    assert client.post("/api/contenus/modules/99-absent/verifier", json={"etudiant": "u1"}, headers=secret).status_code == 404


from test_app import store  # noqa: E402,F401 (fixture)

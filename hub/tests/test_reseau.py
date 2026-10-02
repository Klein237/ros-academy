"""Un réseau par étudiant : création, Hub connecté, sous-réseaux libres, nettoyage."""

import ipaddress
import itertools

import pytest

from rosacademy_hub import reseau
from rosacademy_hub.reseau import LABEL, NetworkError, ensure_network, reconnect_at_startup, remove_network

HUB = "hub"


class FakeDocker:
    """API réseaux de docker.APIClient, avec le refus des sous-réseaux qui se recouvrent."""

    def __init__(self):
        self.nets = {}
        self.ids = itertools.count(1)
        self.fail_next_create = 0
        self.connect_calls = []

    def add(self, name, subnet, members=(), labels=None):
        net_id = f"id{next(self.ids)}"
        self.nets[net_id] = {"Id": net_id, "Name": name, "Labels": labels or {}, "Internal": False,
                             "Options": {}, "IPAM": {"Config": [{"Subnet": subnet}] if subnet else []},
                             "members": set(members)}
        return net_id

    def _view(self, n):
        return {k: v for k, v in n.items() if k != "members"}

    def networks(self, names=None, filters=None):
        out = list(self.nets.values())
        if names:  # comme Docker : correspondance partielle
            out = [n for n in out if any(x in n["Name"] for x in names)]
        if filters and "label" in filters:
            out = [n for n in out if filters["label"] in n["Labels"]]
        return [self._view(n) for n in out]

    def inspect_network(self, net_id):
        n = self.nets[net_id]
        return {**self._view(n), "Containers": {f"c-{m}": {"Name": m} for m in n["members"]}}

    def create_network(self, name, driver, internal, labels, options, ipam, check_duplicate):
        assert driver == "bridge" and check_duplicate
        subnet = ipaddress.ip_network(ipam["Config"][0]["Subnet"])
        if self.fail_next_create:
            self.fail_next_create -= 1
            self.add(f"autre-{name}", str(subnet))  # pris entre-temps par un autre démarrage
            raise RuntimeError("Pool overlaps with other one on this address space")
        for n in self.nets.values():
            for c in n["IPAM"]["Config"]:
                if ipaddress.ip_network(c["Subnet"]).overlaps(subnet):
                    raise RuntimeError("Pool overlaps with other one on this address space")
        net_id = self.add(name, str(subnet), labels=labels)
        self.nets[net_id].update(Internal=internal, Options=options)
        return {"Id": net_id}

    def connect_container_to_network(self, container, net_id, aliases=None):
        assert aliases == ["hub"]
        self.connect_calls.append((container, net_id))
        self.nets[net_id]["members"].add(container)

    def disconnect_container_from_network(self, container, net_id, force=False):
        self.nets[net_id]["members"].discard(container)

    def remove_network(self, net_id):
        assert not self.nets[net_id]["members"], "réseau encore utilisé"
        del self.nets[net_id]

    def by_name(self, name):
        return next(n for n in self.nets.values() if n["Name"] == name)


@pytest.fixture
def docker():
    d = FakeDocker()
    d.add("bridge", "172.17.0.0/16", members={"autre-conteneur"})
    d.add("deploy_public", "172.18.0.0/16", members={HUB})
    return d


def test_each_student_gets_an_internal_network_joined_by_the_hub(docker):
    assert ensure_network(docker, "u1", HUB) == "ros-lab-u1"
    assert ensure_network(docker, "u10", HUB) == "ros-lab-u10"
    a, b = docker.by_name("ros-lab-u1"), docker.by_name("ros-lab-u10")
    assert a["Internal"] and b["Internal"]
    assert a["Labels"] == {LABEL: "u1"}
    assert a["members"] == {HUB} and b["members"] == {HUB}
    assert a["IPAM"]["Config"] == [{"Subnet": "10.213.0.0/28"}]
    assert b["IPAM"]["Config"] == [{"Subnet": "10.213.0.16/28"}]
    assert a["Options"] == {"com.docker.network.bridge.name": "rl-0"}
    assert b["Options"] == {"com.docker.network.bridge.name": "rl-1"}


def test_existing_network_is_reused_and_hub_reconnected(docker):
    ensure_network(docker, "u1", HUB)
    calls = len(docker.connect_calls)
    ensure_network(docker, "u1", HUB)  # « u1 » ne doit pas trouver « ros-lab-u10 » ni l'inverse
    assert len(docker.connect_calls) == calls  # déjà connecté
    docker.by_name("ros-lab-u1")["members"].clear()
    ensure_network(docker, "u1", HUB)
    assert docker.by_name("ros-lab-u1")["members"] == {HUB}
    assert sum(n["Name"] == "ros-lab-u1" for n in docker.nets.values()) == 1


def test_subnets_skip_those_already_used_on_the_host(docker):
    docker.add("vpn", "10.213.0.0/27")  # recouvre les deux premiers /28
    ensure_network(docker, "u1", HUB)
    assert docker.by_name("ros-lab-u1")["IPAM"]["Config"] == [{"Subnet": "10.213.0.32/28"}]
    assert docker.by_name("ros-lab-u1")["Options"]["com.docker.network.bridge.name"] == "rl-2"


def test_subnet_taken_meanwhile_is_retried(docker):
    docker.fail_next_create = 2
    ensure_network(docker, "u1", HUB)
    assert docker.by_name("ros-lab-u1")["IPAM"]["Config"] == [{"Subnet": "10.213.0.32/28"}]


def test_pool_exhausted(docker):
    ensure_network(docker, "u1", HUB, pool="10.99.0.0/27")
    ensure_network(docker, "u2", HUB, pool="10.99.0.0/27")
    with pytest.raises(NetworkError, match="plus de sous-réseau libre"):
        ensure_network(docker, "u3", HUB, pool="10.99.0.0/27")


def test_remove_after_stop_keeps_a_network_still_in_use(docker):
    ensure_network(docker, "u1", HUB)
    docker.by_name("ros-lab-u1")["members"].add("jupyter-u1")
    assert remove_network(docker, "u1", HUB) is False
    docker.by_name("ros-lab-u1")["members"].discard("jupyter-u1")
    assert remove_network(docker, "u1", HUB) is True
    assert not any(n["Name"] == "ros-lab-u1" for n in docker.nets.values())
    assert remove_network(docker, "u1", HUB) is False  # déjà supprimé


def test_startup_rejoins_running_labs_and_removes_orphans(docker):
    ensure_network(docker, "u1", HUB)
    ensure_network(docker, "u2", HUB)
    docker.by_name("ros-lab-u1")["members"] = {"jupyter-u1"}  # Hub recréé : plus connecté
    docker.by_name("ros-lab-u2")["members"] = set()  # Hub arrêté pendant un démarrage
    docker.add("sans-label", "10.50.0.0/28")
    reconnect_at_startup(docker, HUB)
    assert docker.by_name("ros-lab-u1")["members"] == {"jupyter-u1", HUB}
    assert not any(n["Name"] == "ros-lab-u2" for n in docker.nets.values())
    assert docker.by_name("sans-label")  # réseaux qui ne sont pas des labs : intouchés


def test_spawner_network_name_is_per_student():
    from types import SimpleNamespace

    from rosacademy_hub.spawner import RosLabSpawner

    spawner = RosLabSpawner(user=SimpleNamespace(name="u7", id=7, url="/user/u7/", escaped_name="u7"))
    assert spawner.network_name == "ros-lab-u7"
    assert reseau.network_name("u7") == "ros-lab-u7"

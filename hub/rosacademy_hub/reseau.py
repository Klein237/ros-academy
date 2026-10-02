"""Un réseau Docker par étudiant : les conteneurs ros-lab ne peuvent pas se joindre entre eux.

Chaque étudiant a un réseau `internal` (pas de sortie Internet) que seul le Hub rejoint
(le proxy et l'API du Hub doivent atteindre le serveur Jupyter de l'étudiant, et celui-ci
l'API du Hub). Le réseau est créé avant le démarrage du conteneur et supprimé après son arrêt.

Les sous-réseaux sont pris dans une plage dédiée (`LAB_SUBNETS`, des /28) : les plages par
défaut de Docker ne permettent qu'une trentaine de réseaux. Les bridges s'appellent `rl-<n>`,
ce qui permet une seule règle de pare-feu pour tous (`iptables -I INPUT -i rl-+ -j DROP`).

Les fonctions prennent un `docker.APIClient` (synchrone) ; `RosLabSpawner` (spawner.py)
les exécute dans le thread Docker de DockerSpawner pour ne pas bloquer le Hub.
"""

import ipaddress
import logging

log = logging.getLogger(__name__)

LABEL = "ros-academy.reseau-etudiant"
BRIDGE_PREFIX = "rl-"
DEFAULT_SUBNETS = "10.213.0.0/16"
SUBNET_PREFIX = 28  # 14 adresses : le Hub et l'étudiant


class NetworkError(Exception):
    pass


def network_name(username):
    return f"ros-lab-{username}"


def _subnets_of(net):
    return [c["Subnet"] for c in ((net.get("IPAM") or {}).get("Config") or []) if c.get("Subnet")]


def _find(client, name):
    """Réseau portant exactement ce nom (le filtre de Docker accepte les noms partiels)."""
    return next((n for n in client.networks(names=[name]) if n["Name"] == name), None)


def _members(client, net_id):
    return {c.get("Name") for c in (client.inspect_network(net_id).get("Containers") or {}).values()}


def _free_subnet(client, pool, prefix):
    used = []
    for net in client.networks():
        for s in _subnets_of(net):
            try:
                used.append(ipaddress.ip_network(s, strict=False))
            except ValueError:
                continue
    for index, subnet in enumerate(ipaddress.ip_network(pool).subnets(new_prefix=prefix)):
        if not any(subnet.overlaps(u) for u in used if u.version == subnet.version):
            return index, subnet
    raise NetworkError(f"plus de sous-réseau libre dans {pool}")


def ensure_network(client, username, hub_container, pool=DEFAULT_SUBNETS, prefix=SUBNET_PREFIX, attempts=5):
    """Crée (si besoin) le réseau de l'étudiant et y connecte le Hub ; retourne son nom."""
    name = network_name(username)
    net = _find(client, name)
    for _ in range(attempts if net is None else 0):
        index, subnet = _free_subnet(client, pool, prefix)
        try:
            client.create_network(
                name,
                driver="bridge",
                internal=True,
                labels={LABEL: username},
                options={"com.docker.network.bridge.name": f"{BRIDGE_PREFIX}{index}"},
                ipam={"Driver": "default", "Config": [{"Subnet": str(subnet)}]},
                check_duplicate=True,
            )
        except Exception as exc:  # noqa: BLE001 - sous-réseau pris entre-temps par un autre démarrage
            log.warning("Réseau %s non créé sur %s : %s ; nouvel essai", name, subnet, exc)
        net = _find(client, name)
        if net is not None:
            break
    if net is None:
        raise NetworkError(f"réseau {name} impossible à créer")
    if hub_container not in _members(client, net["Id"]):
        client.connect_container_to_network(hub_container, net["Id"], aliases=["hub"])
    return name


def remove_network(client, username, hub_container):
    """Après l'arrêt : déconnecte le Hub et supprime le réseau s'il ne sert plus."""
    net = _find(client, network_name(username))
    if net is None:
        return False
    members = _members(client, net["Id"])
    if members - {hub_container}:
        log.warning("Réseau %s gardé : encore utilisé par %s", net["Name"], sorted(members - {hub_container}))
        return False
    if hub_container in members:
        client.disconnect_container_from_network(hub_container, net["Id"], force=True)
    client.remove_network(net["Id"])
    return True


def reconnect_at_startup(client, hub_container):
    """Au démarrage du Hub (conteneur recréé) : il rejoint les réseaux des labs encore en cours ;
    les réseaux orphelins (Hub arrêté pendant un démarrage) sont supprimés."""
    for net in client.networks(filters={"label": LABEL}):
        members = _members(client, net["Id"])
        others = members - {hub_container}
        try:
            if not others:
                if hub_container in members:
                    client.disconnect_container_from_network(hub_container, net["Id"], force=True)
                client.remove_network(net["Id"])
            elif hub_container not in members:
                client.connect_container_to_network(hub_container, net["Id"], aliases=["hub"])
        except Exception as exc:  # noqa: BLE001
            log.warning("Réseau %s non traité au démarrage : %s", net["Name"], exc)

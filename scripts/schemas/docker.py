"""Schémas du parcours Docker pour la robotique : couches, deux étapes, Compose et DDS, déploiement."""

from style import line, path, rect, svg, text

CONTENEURS = "20-docker-conteneurs"
IMAGE = "21-docker-image"
COMPOSE = "22-docker-compose"
ROBOT = "23-docker-robot"


def couche(x, y, w, nom, detail, cls="boite"):
    return [rect(x, y, w, 40, cls, 6), text(x + 14, y + 25, nom, "t-gras"), text(x + w - 14, y + 25, detail, "t-code", "end")]


def couches():
    b = [rect(20, 20, 400, 300, "fond", 12), text(38, 48, "IMAGE  livraison:1.0", "t-sur"),
         text(400, 48, "lecture seule", "t-petit", "end")]
    pile = [("workspace compilé", "/ws/install", "calcul"),
            ("dépendances", "rosdep, apt", "boite"),
            ("ROS 2 Jazzy", "ros:jazzy-ros-base", "boite"),
            ("Ubuntu 24.04", "ubuntu:noble", "boite")]
    for i, (nom, detail, cls) in enumerate(pile):
        b += couche(40, 70 + i * 52, 360, nom, detail, cls)
    b.append(text(220, 300, "chaque instruction du Dockerfile ajoute une couche", "t-petit", "middle"))
    for j, (nom, ecrit) in enumerate((("robot", "journaux, /tmp"), ("supervision", "fichiers temporaires"))):
        x = 470 + j * 205
        b += [rect(x, 20, 190, 300, "fond", 12), text(x + 95, 44, "CONTENEUR", "t-sur", "middle"),
              text(x + 95, 62, nom, "t-gras", "middle"),
              rect(x + 15, 76, 160, 64, "capteur", 6), text(x + 95, 101, "couche d'écriture", "t-gras", "middle"),
              text(x + 95, 122, ecrit, "t-petit", "middle"),
              rect(x + 15, 152, 160, 148, "boite", 6), text(x + 95, 190, "les couches", "t-petit", "middle"),
              text(x + 95, 208, "de l'image,", "t-petit", "middle"), text(x + 95, 226, "partagées", "t-petit", "middle")]
    b.append(text(665, 345, "la couche d'écriture disparaît avec le conteneur", "t-petit", "middle"))
    return svg(880, 360, "Une image en couches, deux conteneurs",
               "L'image livraison:1.0 est une pile de couches en lecture seule : Ubuntu 24.04, ROS 2 Jazzy, les dépendances "
               "installées par rosdep, puis le workspace compilé. Les conteneurs robot et supervision partagent ces couches ; "
               "chacun ajoute au-dessus sa propre couche d'écriture, supprimée avec le conteneur.", "\n".join(b))


def deux_etapes():
    b = []
    etapes = [(20, "ÉTAPE build", "FROM ros:jazzy-ros-base",
               ["COPY package.xml", "RUN rosdep install", "COPY src", "RUN colcon build"], "boite"),
              (470, "ÉTAPE robot  →  l'image", "FROM ros:jazzy-ros-core",
               ["COPY --from=build /ws/install", "COPY ros_entrypoint.sh", "USER robot", "ENTRYPOINT + CMD"], "calcul")]
    for x, titre, base, lignes, cls in etapes:
        b += [rect(x, 20, 390, 300, "fond", 12), text(x + 18, 48, titre, "t-sur"),
              rect(x + 18, 64, 354, 40, "actionneur", 6), text(x + 34, 89, base, "t-code")]
        for i, l in enumerate(lignes):
            b += [rect(x + 18, 116 + i * 46, 354, 36, cls if i == 0 and cls == "calcul" else "boite", 6),
                  text(x + 34, 139 + i * 46, l, "t-code")]
    b += [path("M392 270 C 432 270, 432 134, 486 134", "trait", fin="trait"),
          text(440, 300, "install/", "t-code", "middle"),
          text(215, 345, "compilateurs, en-têtes, colcon, rosdep : restent ici", "t-petit", "middle"),
          text(665, 345, "seulement ROS 2 et le workspace compilé", "t-petit", "middle")]
    return svg(880, 360, "Construire en deux étapes",
               "L'étape build part de ros:jazzy-ros-base : elle copie les package.xml, installe les dépendances avec rosdep, "
               "copie le code et le compile avec colcon. L'étape robot part de ros:jazzy-ros-core, ne reçoit que le dossier "
               "install copié depuis build, son point d'entrée, un utilisateur non root, ENTRYPOINT et CMD. Seule l'étape "
               "robot devient l'image : les outils de compilation restent dans build.", "\n".join(b))


def compose():
    b = [rect(20, 20, 520, 300, "fond", 12), text(38, 48, "ORDINATEUR DU ROBOT", "t-sur"),
         text(522, 48, "réseau et mémoire de l'hôte", "t-petit", "end")]
    for i, (nom, cmd) in enumerate((("robot", "ros2 launch livraison_bringup"), ("supervision", "ros2 topic echo /etat"))):
        y = 66 + i * 124
        b += [rect(40, y, 300, 90, "calcul", 10), text(56, y + 28, f"conteneur {nom}", "t-gras"),
              text(56, y + 52, cmd, "t-code"), text(56, y + 74, "ROS_DOMAIN_ID=42", "t-code")]
    b += [rect(370, 70, 150, 200, "boite", 10), text(445, 100, "network_mode:", "t-code", "middle"),
          text(445, 120, "host", "t-code", "middle"), text(445, 160, "ipc: host", "t-code", "middle"),
          text(445, 200, "mémoire", "t-petit", "middle"), text(445, 218, "partagée", "t-petit", "middle"),
          text(445, 236, "et réseau", "t-petit", "middle"), text(445, 254, "communs", "t-petit", "middle"),
          line(342, 111, 368, 111, "trait", fin="trait"), line(342, 235, 368, 235, "trait", fin="trait"),
          line(190, 160, 190, 186, "trait", fin="trait", debut="trait"),
          text(202, 178, "/etat", "t-code"),
          text(280, 300, "les deux conteneurs se découvrent : même domaine, même réseau", "t-petit", "middle")]
    b += [rect(600, 70, 260, 200, "fond", 12), text(618, 98, "PORTABLE DU DÉVELOPPEUR", "t-sur"),
          rect(618, 116, 224, 90, "boite", 10), text(634, 144, "conteneur rviz", "t-gras"),
          text(634, 168, "network_mode: host", "t-code"), text(634, 190, "ROS_DOMAIN_ID=42", "t-code"),
          text(730, 236, "même Wi-Fi, même domaine", "t-petit", "middle"),
          path("M522 170 C 560 170, 560 160, 598 160", "tirets", fin="trait"),
          text(560, 150, "DDS", "t-accent", "middle")]
    return svg(880, 330, "Compose et DDS : le robot et le poste de développement",
               "Sur l'ordinateur du robot, les conteneurs robot (ros2 launch) et supervision (ros2 topic echo /etat) sont "
               "dans le domaine 42, avec network_mode host et ipc host : ils partagent le réseau et la mémoire de l'hôte "
               "et se découvrent. Le portable du développeur, sur le même Wi-Fi et dans le même domaine, lance RViz dans "
               "un conteneur en réseau host et voit les nœuds du robot par DDS.", "\n".join(b))


def deploiement():
    b = []
    boites = [(15, "Développeur", ["git tag v1.1.0", "git push --tags"], "boite"),
              (230, "Intégration continue", ["buildx amd64 + arm64", "tests dans l'image"], "calcul"),
              (445, "Registre", ["ghcr.io/roboforge/", "livraison:1.1.0"], "capteur"),
              (660, "Robot (arm64)", ["VERSION=1.1.0", "compose pull, up -d"], "actionneur")]
    for x, titre, lignes, cls in boites:
        b += [rect(x, 40, 195, 110, cls, 12), text(x + 97, 70, titre, "t-gras", "middle")]
        for i, l in enumerate(lignes):
            b.append(text(x + 97, 98 + i * 22, l, "t-code" if i == 0 or "/" in l else "t-petit", "middle"))
    for x in (212, 427, 642):
        b.append(line(x, 95, x + 16, 95, "trait", fin="trait"))
    b += [path("M757 152 C 757 220, 690 226, 630 226 L 300 226", "tirets", fin="trait"),
          text(400, 214, "en cas de problème : VERSION=1.0.0, puis up -d (l'image est encore sur le robot)",
               "t-petit", "middle")]
    return svg(880, 250, "Du poste de développement au robot",
               "Le développeur pousse une étiquette de version v1.1.0. L'intégration continue construit l'image pour amd64 "
               "et arm64, lance les tests dans l'image et la publie dans le registre sous livraison:1.1.0. Le robot, en "
               "arm64, règle VERSION=1.1.0, puis docker compose pull et up -d. En cas de problème, il revient à "
               "VERSION=1.0.0, dont l'image est encore sur le robot.", "\n".join(b))


SCHEMAS = {
    f"{CONTENEURS}/images/couches.svg": couches,
    f"{IMAGE}/images/deux-etapes.svg": deux_etapes,
    f"{COMPOSE}/images/compose.svg": compose,
    f"{ROBOT}/images/deploiement.svg": deploiement,
}

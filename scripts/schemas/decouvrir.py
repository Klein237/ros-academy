"""Schémas du parcours gratuit (pages /decouvrir/), écrits dans static/decouvrir/ du service Contenus."""

import math

from style import arc, line, path, rect, robot, svg, text


def sans_avec():
    progs = [("lidar", 90, 90), ("caméra", 330, 90), ("localisation", 70, 230), ("planification", 350, 230),
             ("moteurs", 210, 300)]
    b = [rect(20, 20, 420, 330, "fond", 12), text(40, 48, "SANS MIDDLEWARE", "t-sur")]
    centres = [(x, y) for _, x, y in progs]
    for i, (x1, y1) in enumerate(centres):
        for x2, y2 in centres[i + 1:]:
            b.append(line(x1, y1, x2, y2, "tirets"))
    for nom, x, y in progs:
        b += [rect(x - 62, y - 18, 124, 36, "boite", 8), text(x, y + 5, nom, "t-petit", "middle")]
    b.append(text(230, 340, "chacun doit connaître tous les autres", "t-ambre", "middle"))
    b += [rect(480, 20, 420, 330, "fond", 12), text(500, 48, "AVEC UN MIDDLEWARE", "t-sur"),
          rect(500, 170, 380, 44, "calcul", 10), text(690, 197, "middleware : topics, services, découverte", "t-gras", "middle")]
    for i, nom in enumerate(["lidar", "caméra", "localisation"]):
        x = 560 + i * 130
        b += [rect(x - 56, 84, 112, 36, "boite", 8), text(x, 107, nom, "t-petit", "middle"), line(x, 122, x, 168, fin="trait")]
    for i, nom in enumerate(["planification", "moteurs"]):
        x = 620 + i * 140
        b += [rect(x - 60, 264, 120, 36, "boite", 8), text(x, 287, nom, "t-petit", "middle"), line(x, 216, x, 262, fin="trait")]
    b.append(text(690, 340, "chacun ne parle qu'au middleware", "t-accent", "middle"))
    return svg(920, 370, "Sans middleware, avec un middleware",
               "À gauche, sans middleware : cinq programmes du robot (lidar, caméra, localisation, planification, "
               "moteurs) sont reliés deux à deux, chacun doit connaître tous les autres. À droite, avec un middleware : "
               "chaque programme ne parle qu'au middleware, qui gère les topics, les services et la découverte.",
               "\n".join(b))


def communications():
    b = [rect(20, 20, 880, 420, "fond", 12)]
    # topic
    b += [text(40, 50, "TOPIC : UN FLUX CONTINU", "t-sur"),
          rect(40, 70, 150, 50, "capteur", 8), text(115, 100, "lidar", "t-gras", "middle"),
          line(192, 95, 236, 95), path("M236 95 C 280 95, 290 77, 330 77", "trait", fin="trait"),
          path("M236 95 C 280 95, 290 115, 330 115", "trait", fin="trait"),
          text(214, 86, "/scan", "t-code", "middle"), text(214, 140, "10 fois par seconde", "t-petit", "middle"),
          rect(332, 62, 170, 30, "boite", 6), text(417, 82, "arrêt d'urgence", "t-petit", "middle"),
          rect(332, 100, 170, 30, "boite", 6), text(417, 120, "cartographie", "t-petit", "middle"),
          text(530, 92, "un émetteur, autant d'abonnés que nécessaire,", "t-petit"),
          text(530, 112, "sans réponse : publier et s'abonner", "t-petit")]
    # service
    b += [line(40, 152, 880, 152, "sep"), text(40, 182, "SERVICE : UNE QUESTION, UNE RÉPONSE", "t-sur"),
          rect(40, 200, 150, 56, "boite", 8), text(115, 233, "interface", "t-gras", "middle"),
          rect(332, 200, 170, 56, "calcul", 8), text(417, 233, "batterie", "t-gras", "middle"),
          line(192, 214, 330, 214, fin="trait"), text(261, 207, "niveau ?", "t-code", "middle"),
          line(330, 244, 194, 244, fin="trait"), text(261, 266, "72 %", "t-code", "middle"),
          text(530, 224, "le client attend la réponse :", "t-petit"),
          text(530, 244, "pour une demande courte", "t-petit")]
    # action
    b += [line(40, 288, 880, 288, "sep"), text(40, 318, "ACTION : UNE TÂCHE LONGUE, SUIVIE", "t-sur"),
          rect(40, 336, 150, 80, "boite", 8), text(115, 381, "mission", "t-gras", "middle"),
          rect(332, 336, 170, 80, "calcul", 8), text(417, 381, "navigation", "t-gras", "middle"),
          line(192, 348, 330, 348, fin="trait"), text(261, 342, "va au quai 4", "t-code", "middle"),
          line(330, 376, 194, 376, "tirets", fin="trait"), text(261, 370, "encore 12 m", "t-code", "middle"),
          line(330, 404, 194, 404, fin="trait"), text(261, 398, "arrivé", "t-code", "middle"),
          text(530, 366, "un but, des nouvelles en route, un résultat ;", "t-petit"),
          text(530, 386, "on peut l'annuler en chemin", "t-petit")]
    return svg(920, 460, "Trois façons de se parler",
               "Topic : le lidar publie /scan dix fois par seconde, l'arrêt d'urgence et la cartographie s'y abonnent, "
               "sans réponse. Service : l'interface demande à la batterie son niveau et attend la réponse, 72 %. "
               "Action : la mission demande à la navigation d'aller au quai 4, reçoit des nouvelles en route (encore "
               "12 m), puis le résultat (arrivé) ; on peut l'annuler en chemin.", "\n".join(b))


def decouverte():
    b = [rect(20, 20, 420, 300, "fond", 12), text(40, 48, "ROS 1 : UN SERVEUR CENTRAL", "t-sur"),
         rect(170, 140, 120, 48, "capteur", 8), text(230, 169, "roscore", "t-code", "middle")]
    for x, y, nom in [(90, 84, "lidar"), (370, 84, "carte"), (90, 250, "moteurs"), (370, 250, "navigation")]:
        b += [rect(x - 50, y - 18, 100, 36, "boite", 8), text(x, y + 5, nom, "t-petit", "middle"),
              line(x + (40 if x < 230 else -40), y + (18 if y < 160 else -18), 230 + (-40 if x < 230 else 40),
                   164 + (-24 if y < 160 else 24), "tirets")]
    b.append(text(230, 304, "s'il s'arrête, plus personne ne se trouve", "t-ambre", "middle"))
    b += [rect(480, 20, 420, 300, "fond", 12), text(500, 48, "ROS 2 : DDS, SANS SERVEUR", "t-sur")]
    pos = [(560, 100, "lidar"), (820, 100, "carte"), (560, 240, "moteurs"), (820, 240, "navigation")]
    for i, (x1, y1, _) in enumerate(pos):
        for x2, y2, _ in pos[i + 1:]:
            b.append(line(x1, y1, x2, y2, "tirets"))
    for x, y, nom in pos:
        b += [rect(x - 54, y - 18, 108, 36, "calcul", 8), text(x, y + 5, nom, "t-petit", "middle")]
    b += [rect(600, 152, 180, 28, "boite", 6), text(690, 171, "« je publie /scan »", "t-code", "middle"),
          text(690, 304, "chacun s'annonce sur le réseau", "t-accent", "middle")]
    return svg(920, 340, "Se trouver : ROS 1 et ROS 2",
               "À gauche, ROS 1 : chaque nœud s'enregistre auprès d'un serveur central, roscore ; s'il s'arrête, plus "
               "personne ne se trouve. À droite, ROS 2 : il n'y a pas de serveur, chaque nœud s'annonce sur le réseau "
               "grâce à DDS (« je publie /scan ») et les nœuds se découvrent entre eux.", "\n".join(b))


def graphe():
    b = [rect(20, 20, 880, 360, "fond", 12), text(40, 48, "LE ROBOT DE LIVRAISON, VU PAR ROS 2", "t-sur")]
    noeuds = {"lidar": (110, 120, "capteur"), "odometrie": (110, 290, "capteur"),
              "arret_urgence": (440, 120, "calcul"), "navigation": (440, 290, "calcul"),
              "base": (780, 205, "boite")}
    for nom, (x, y, cls) in noeuds.items():
        b += [f'<ellipse class="{cls}" cx="{x}" cy="{y}" rx="82" ry="30"/>', text(x, y + 5, nom, "t-code", "middle")]
    fleches = [((192, 120), (356, 120), "/scan", (274, 110)), ((150, 146), (380, 270), "/scan", (222, 226)),
               ((192, 290), (356, 290), "/odom", (274, 282)), ((522, 120), (712, 186), "/arret", (630, 136)),
               ((522, 290), (712, 224), "/cmd_vel", (632, 282))]
    for (x1, y1), (x2, y2), nom, (tx, ty) in fleches:
        b += [line(x1, y1, x2, y2, fin="trait"), text(tx, ty, nom, "t-code", "middle")]
    b += [text(780, 256, "commande les roues", "t-petit", "middle"),
          text(110, 340, "les capteurs publient", "t-petit", "middle"),
          text(440, 340, "les décisions s'abonnent et publient", "t-petit", "middle"),
          text(780, 340, "les moteurs obéissent", "t-petit", "middle")]
    return svg(920, 400, "Le robot de livraison vu comme un graphe ROS 2",
               "Cinq nœuds reliés par des topics. Le lidar publie /scan, lu par arret_urgence et par navigation. "
               "L'odométrie publie /odom, lu par navigation. arret_urgence publie /arret et navigation publie /cmd_vel, "
               "tous deux lus par le nœud base, qui commande les roues. Les capteurs publient, les décisions "
               "s'abonnent et publient, les moteurs obéissent.", "\n".join(b))


def twist():
    b = [rect(20, 20, 880, 300, "fond", 12), text(40, 48, "UN MESSAGE : geometry_msgs/msg/Twist SUR /cmd_vel", "t-sur"),
         robot(210, 180, 0, 1.6)]
    b += [line(270, 180, 380, 180, "vitesse", fin="vitesse"), text(330, 168, "linear.x", "t-code", "middle"),
          text(330, 206, "avancer, en m/s", "t-petit", "middle"),
          arc(210, 180, 78, 15, 120, "trajet", fin="trajet"), text(300, 92, "angular.z", "t-code"),
          text(300, 110, "tourner, en rad/s (positif : à gauche)", "t-petit")]
    lignes = [("linear:", ""), ("  x: 0.3", "# avance à 0,3 m/s"), ("  y: 0.0", ""), ("  z: 0.0", ""),
              ("angular:", ""), ("  x: 0.0", ""), ("  y: 0.0", ""), ("  z: 0.5", "# tourne à gauche")]
    b.append(rect(560, 70, 320, 220, "boite", 8))
    for i, (l, commentaire) in enumerate(lignes):
        retrait = 22 if l.startswith(" ") else 0
        b.append(text(580 + retrait, 98 + i * 24, l.strip(), "t-code"))
        if commentaire:
            b.append(text(680, 98 + i * 24, commentaire, "t-petit"))
    return svg(920, 340, "Un message Twist sur /cmd_vel",
               "Le robot vu de dessus. Une flèche vers l'avant représente linear.x, la vitesse d'avance en mètres par "
               "seconde ; un arc représente angular.z, la vitesse de rotation en radians par seconde. À droite, le "
               "message : linear x 0.3 (avance à 0,3 m/s), y et z à 0 ; angular x et y à 0, z 0.5 (tourne à gauche).",
               "\n".join(b))


def du_code_au_robot():
    b = [rect(20, 20, 880, 260, "fond", 12), text(40, 48, "DU CODE AU ROBOT", "t-sur")]
    etapes = [("src/", "vos packages :", "code Python ou C++", "boite"),
              ("colcon build", "compile et", "installe", "calcul"),
              ("install/", "source", "install/setup.bash", "boite"),
              ("ros2 run", "ou ros2 launch :", "les nœuds démarrent", "calcul")]
    for i, (nom, l1, l2, cls) in enumerate(etapes):
        x = 40 + i * 172
        b += [rect(x, 80, 152, 104, cls, 8), text(x + 76, 112, nom, "t-code", "middle"),
              text(x + 76, 142, l1, "t-petit", "middle"), text(x + 76, 162, l2, "t-petit", "middle")]
        b.append(line(x + 154, 132, x + 170, 132, fin="trait"))
    b += [rect(728, 70, 152, 54, "capteur", 8), text(804, 94, "simulation", "t-gras", "middle"),
          text(804, 112, "Gazebo, RViz", "t-petit", "middle"),
          rect(728, 140, 152, 54, "capteur", 8), text(804, 164, "robot réel", "t-gras", "middle"),
          text(804, 182, "le même code", "t-petit", "middle"),
          text(460, 236, "le workspace : un dossier ws/ avec src/, build/, install/ et log/", "t-petit", "middle"),
          text(460, 258, "seul src/ s'écrit à la main ; le reste se recrée avec colcon build", "t-petit", "middle")]
    return svg(920, 300, "Du code au robot",
               "Quatre étapes : le code des packages dans src/, en Python ou en C++ ; colcon build compile et installe ; "
               "on charge install/setup.bash ; ros2 run ou ros2 launch démarre les nœuds, en simulation (Gazebo, RViz) "
               "ou sur le robot réel, avec le même code. Le workspace est un dossier ws/ avec src/, build/, install/ et "
               "log/ ; seul src/ s'écrit à la main.", "\n".join(b))


STATIQUES = {
    "decouvrir/sans-avec.svg": sans_avec,
    "decouvrir/communications.svg": communications,
    "decouvrir/decouverte.svg": decouverte,
    "decouvrir/graphe.svg": graphe,
    "decouvrir/twist.svg": twist,
    "decouvrir/du-code-au-robot.svg": du_code_au_robot,
}
SCHEMAS = {}

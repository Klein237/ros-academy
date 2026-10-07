"""Schémas des modules « Pourquoi ROS 2 » et « Organiser son code »."""

from style import line, path, rect, svg, text

ROS2 = "03-ros2"
WS = "04-workspace"


def noeud(x, y, w, nom, sous=""):
    out = [rect(x, y, w, 62, "calcul", 10), text(x + w / 2, y + 27, nom, "t-gras", "middle")]
    if sous:
        out.append(text(x + w / 2, y + 47, sous, "t-petit", "middle"))
    return out


def topic(x, y, w, nom, type_):
    return [rect(x, y, w, 54, "capteur", 27), text(x + w / 2, y + 24, nom, "t-code", "middle"),
            text(x + w / 2, y + 42, type_, "t-petit", "middle")]


def graphe():
    b = []
    b += noeud(20, 40, 200, "Vue 2D du lab", "flèches de téléopération")
    b += noeud(560, 40, 220, "/academy_diffbot", "le robot simulé")
    b += noeud(20, 210, 200, "ros2 topic echo", "votre terminal")
    b += topic(300, 44, 180, "/cmd_vel", "geometry_msgs/Twist")
    b += topic(300, 214, 180, "/odom", "nav_msgs/Odometry")
    b += [line(222, 71, 296, 71, fin="trait"), text(259, 62, "publie", "t-petit", "middle"),
          line(482, 71, 556, 71, fin="trait"), text(519, 62, "s'abonne", "t-petit", "middle"),
          path("M670 104 C 670 180, 560 241, 486 241", fin="trait"), text(640, 190, "publie", "t-petit", "middle"),
          line(298, 241, 224, 241, fin="trait"), text(261, 232, "s'abonne", "t-petit", "middle"),
          path("M330 212 C 300 160, 160 160, 130 106", fin="trait"), text(232, 150, "s'abonne", "t-petit", "middle")]
    b += [rect(20, 300, 26, 18, "calcul", 5), text(54, 314, "nœud", "t-petit"),
          rect(110, 300, 34, 18, "capteur", 9), text(152, 314, "topic et type de message", "t-petit"),
          line(330, 309, 370, 309, fin="trait"), text(380, 314, "sens des messages", "t-petit")]
    return svg(800, 330, "Le graphe ROS du robot de livraison",
               "Trois nœuds et deux topics : la vue 2D publie des ordres de vitesse sur /cmd_vel ; le nœud "
               "/academy_diffbot s'y abonne et publie sa position sur /odom, que lisent la vue 2D et ros2 topic echo.",
               "\n".join(b))


def communication():
    b = []
    panneaux = [(20, "TOPIC", "un flux, sans réponse"), (300, "SERVICE", "une question, une réponse"),
                (580, "ACTION", "une mission suivie, annulable")]
    for x, titre, sous in panneaux:
        b += [rect(x, 20, 260, 330, "fond", 12), text(x + 18, 48, titre, "t-sur"), text(x + 18, 68, sous, "t-petit")]
    # topic : un éditeur, deux abonnés, des messages en continu
    b += [rect(40, 90, 100, 36, "calcul", 8), text(90, 113, "éditeur", "t-gras", "middle"),
          rect(160, 170, 100, 36, "calcul", 8), text(210, 193, "abonné", "t-gras", "middle"),
          rect(160, 250, 100, 36, "calcul", 8), text(210, 273, "abonné", "t-gras", "middle")]
    for y in (148, 172, 196, 220):  # les messages, l'un après l'autre
        b.append(f'<circle class="cir" cx="78" cy="{y}" r="5"/>')
    b += [path("M90 128 C 90 240, 120 188, 156 188", fin="trait"), path("M90 128 C 90 300, 120 268, 156 268", fin="trait"),
          text(40, 320, "/odom, 20 messages par seconde", "t-petit")]
    # service : requête puis réponse, le client attend
    cx, sx = 350, 500
    b += [text(cx, 104, "client", "t-gras", "middle"), text(sx, 104, "serveur", "t-gras", "middle"),
          line(cx, 112, cx, 320, "tirets"), line(sx, 112, sx, 320, "tirets"),
          line(cx, 150, sx - 4, 180, fin="trait"), text(425, 150, "requête", "t-petit", "middle"),
          rect(sx - 6, 182, 12, 50, "calcul", 3),
          line(sx, 236, cx + 4, 266, fin="trait"), text(425, 270, "réponse", "t-petit", "middle"),
          text(cx + 8, 214, "attend…", "t-petit"), text(320, 340, "« où es-tu ? » → (x, y, θ)", "t-petit")]
    # action : goal, feedbacks, résultat
    cx, sx = 630, 780
    b += [text(cx, 104, "client", "t-gras", "middle"), text(sx, 104, "serveur", "t-gras", "middle"),
          line(cx, 112, cx, 320, "tirets"), line(sx, 112, sx, 320, "tirets"),
          line(cx, 135, sx - 4, 150, fin="trait"), text(705, 132, "goal", "t-petit", "middle"),
          rect(sx - 6, 152, 12, 140, "calcul", 3)]
    for y in (180, 210, 240):
        b.append(line(sx, y, cx + 4, y + 10, "tirets", fin="trait"))
    b += [text(705, 205, "feedbacks", "t-petit", "middle"),
          line(sx, 294, cx + 4, 308, fin="trait"), text(705, 296, "résultat", "t-petit", "middle"),
          text(600, 340, "« va au point (2, 1) »", "t-petit")]
    return svg(860, 360, "Topic, service, action : trois façons de communiquer",
               "Topic : un éditeur diffuse un flux de messages à des abonnés, sans réponse. Service : un client "
               "envoie une requête et attend la réponse du serveur. Action : le client envoie un goal, reçoit des "
               "feedbacks pendant l'exécution, puis un résultat ; il peut annuler en cours de route.", "\n".join(b))


def distribue():
    b = [text(20, 30, "ROS 1 : UN MAÎTRE CENTRAL", "t-sur"), text(450, 30, "ROS 2 : CHACUN SE DÉCOUVRE (DDS)", "t-sur"),
         line(425, 20, 425, 300, "sep")]
    # ROS 1 : roscore au centre, tout passe par lui pour se trouver
    b += [rect(150, 130, 120, 48, "actionneur", 10), text(210, 159, "roscore", "t-code", "middle")]
    for x, y, nom in ((30, 60, "laser"), (290, 60, "moteurs"), (30, 230, "carte"), (290, 230, "navigation")):
        b += [rect(x, y, 100, 40, "calcul", 8), text(x + 50, y + 25, nom, "t-gras", "middle"),
              line(x + 50, y + (40 if y < 130 else 0), 210, 154 + (-24 if y < 130 else 24), "tirets")]
    b.append(text(210, 296, "s'il s'arrête, plus personne ne se trouve", "t-petit", "middle"))
    # ROS 2 : deux machines, même domaine, découverte directe
    b += [rect(450, 50, 180, 210, "fond", 12), text(540, 74, "robot", "t-petit", "middle"),
          rect(660, 50, 180, 210, "fond", 12), text(750, 74, "ordinateur portable", "t-petit", "middle")]
    nodes = [(475, 95, "laser"), (475, 175, "moteurs"), (685, 95, "navigation"), (685, 175, "RViz")]
    for x, y, nom in nodes:
        b += [rect(x, y, 130, 40, "calcul", 8), text(x + 65, y + 25, nom, "t-gras", "middle")]
    for (x1, y1, _), (x2, y2, _) in ((nodes[0], nodes[2]), (nodes[1], nodes[2]), (nodes[0], nodes[3]), (nodes[1], nodes[0])):
        b.append(line(x1 + 65, y1 + 20, x2 + 65, y2 + 20, "tirets"))
    b += [text(645, 290, "même ROS_DOMAIN_ID : les nœuds se voient, sans serveur central", "t-petit", "middle")]
    return svg(860, 310, "Une architecture distribuée, sans maître central",
               "En ROS 1, les nœuds passaient par un maître central, roscore, pour se trouver. En ROS 2, grâce à DDS, "
               "les nœuds d'un même domaine se découvrent directement, y compris sur des machines différentes : le "
               "robot et un ordinateur portable.", "\n".join(b))


def arbre(x0, y0, items, note_x, pas=40):
    """items : (nom, note, niveau, dernier) ; dessine ├─ / └─ en police à chasse fixe."""
    out, ouverts = [], []
    for i, (nom, note, niveau, dernier) in enumerate(items):
        y = y0 + pas * i
        prefixe = "".join("│  " if o else "   " for o in ouverts[:max(niveau - 1, 0)])
        if niveau:
            prefixe += "└─ " if dernier else "├─ "
        if niveau:  # ce niveau reste ouvert (│) tant qu'il reste des frères après lui
            del ouverts[niveau - 1:]
            ouverts.append(not dernier)
        out.append(f'<text class="t-code" x="{x0}" y="{y}" xml:space="preserve">{prefixe}{nom}</text>')
        if note:
            out.append(text(note_x, y, note, "t-petit"))
    return out


def workspace():
    b = [rect(20, 20, 620, 330, "fond", 12)]
    b += arbre(44, 60, [("~/ws/04-workspace/", "le workspace", 0, False),
                        ("src/", "vos sources : un dossier par package", 1, False),
                        ("mon_premier_pkg/", "un package", 2, True),
                        ("build/", "fichiers intermédiaires de compilation", 1, False),
                        ("install/", "le résultat, prêt à lancer, avec setup.bash", 1, False),
                        ("log/", "les journaux de colcon", 1, True)], 290)
    b += [rect(40, 300, 580, 32, "capteur", 16),
          text(330, 321, "colcon build lit src/ et produit build/, install/ et log/", "t-petit", "middle")]
    return svg(660, 365, "La structure d'un workspace ROS 2",
               "Un workspace contient src (les sources, un dossier par package). colcon build crée build (fichiers "
               "intermédiaires), install (le résultat, avec setup.bash) et log (les journaux).", "\n".join(b))


def overlay():
    b = []
    couches = [(220, "underlay : /opt/ros/jazzy", "ROS 2 et ses packages (rclpy, geometry_msgs, nav2…)", "actionneur"),
               (140, "overlay : ~/ws/…/install", "vos packages, compilés par colcon", "calcul")]
    for y, titre, sous, cls in couches:
        b += [rect(40, y, 440, 64, cls, 10), text(60, y + 28, titre, "t-code"), text(60, y + 48, sous, "t-petit")]
    b += [rect(40, 40, 440, 64, "capteur", 10), text(60, 68, "votre terminal", "t-gras"),
          text(60, 88, "voit les deux couches, l'overlay par-dessus", "t-petit")]
    b += [text(500, 177, "← source install/setup.bash", "t-code"),
          text(500, 257, "← source /opt/ros/jazzy/setup.bash", "t-code"),
          text(522, 277, "(déjà fait par ~/.bashrc dans le lab)", "t-petit")]
    return svg(800, 310, "Underlay et overlay",
               "L'installation de ROS 2 (/opt/ros/jazzy) est l'underlay. Votre workspace compilé (install) est un "
               "overlay, superposé par source install/setup.bash. Le terminal voit les deux ; un package de "
               "l'overlay masque celui du même nom dans l'underlay.", "\n".join(b))


def package():
    b = [text(20, 30, "PACKAGE PYTHON (ament_python)", "t-sur"), text(500, 30, "PACKAGE C++ (ament_cmake)", "t-sur"),
         line(480, 20, 480, 300, "sep")]
    b += arbre(24, 64, [("mon_pkg/", "", 0, False), ("package.xml", "nom, dépendances", 1, False),
                        ("setup.py", "entry_points : les exécutables", 1, False),
                        ("setup.cfg", "où installer les scripts", 1, False),
                        ("resource/mon_pkg", "marqueur pour ROS", 1, False),
                        ("mon_pkg/", "le code Python", 1, True), ("mon_noeud.py", "un nœud", 2, True)], 240, 34)
    b += arbre(504, 64, [("mon_pkg_cpp/", "", 0, False), ("package.xml", "nom, dépendances", 1, False),
                         ("CMakeLists.txt", "compilation, installation", 1, False),
                         ("include/mon_pkg_cpp/", "les en-têtes", 1, False),
                         ("src/", "le code C++", 1, True), ("mon_noeud.cpp", "un nœud", 2, True)], 740, 34)
    b.append(text(480, 312, "package.xml dans les deux cas : c'est lui qui fait d'un dossier un package ROS",
                  "t-petit", "middle"))
    return svg(960, 325, "L'anatomie d'un package, en Python et en C++",
               "Un package Python contient package.xml, setup.py (avec les entry_points qui déclarent les "
               "exécutables), setup.cfg, resource et le code. Un package C++ contient package.xml, CMakeLists.txt, "
               "include et src.", "\n".join(b))


SCHEMAS = {
    f"{ROS2}/images/graphe.svg": graphe,
    f"{ROS2}/images/communication.svg": communication,
    f"{ROS2}/images/distribue.svg": distribue,
    f"{WS}/images/workspace.svg": workspace,
    f"{WS}/images/overlay.svg": overlay,
    f"{WS}/images/package.svg": package,
}

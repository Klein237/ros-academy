"""Schémas du parcours « Tester et fiabiliser » : tests unitaires (module 40), tests d'intégration (module 41), rejeu de données (module 42), intégration continue (module 43)."""

import math

from style import line, path, rect, robot, svg, text

UNITAIRES = "40-tests-unitaires"
INTEGRATION = "41-tests-integration"
REJEU = "42-rejeu-donnees"
CI = "43-integration-continue"


def separation():
    b = [rect(20, 20, 400, 300, "fond", 12), text(40, 48, "AVANT : TOUT DANS LE NŒUD", "t-sur"),
         rect(44, 70, 352, 200, "boite", 8), text(64, 98, "class Odometrie(Node)", "t-code"),
         text(76, 128, "abonnement /cmd_vel", "t-petit"), text(76, 150, "minuterie", "t-petit"),
         rect(68, 164, 304, 58, "capteur", 6), text(84, 188, "x += v * cos(theta) * dt …", "t-code"),
         text(84, 208, "calcul mêlé à ROS", "t-ambre"),
         text(76, 248, "publication /odom", "t-petit"),
         text(220, 300, "pour tester le calcul, il faut lancer ROS", "t-petit", "middle")]
    b += [rect(500, 20, 400, 300, "fond", 12), text(520, 48, "APRÈS : UN NŒUD FIN, UN CALCUL PUR", "t-sur"),
          rect(524, 70, 352, 92, "boite", 8), text(544, 98, "class Odometrie(Node)", "t-code"),
          text(556, 124, "reçoit, appelle integrer(),", "t-petit"), text(556, 144, "publie : rien d'autre", "t-petit"),
          rect(524, 192, 352, 70, "calcul", 8), text(544, 220, "odometrie/calcul.py", "t-code"),
          text(556, 244, "integrer, normaliser, vitesses_roues", "t-petit"),
          line(700, 164, 700, 190, fin="trait"), text(712, 182, "appelle", "t-petit"),
          rect(760, 270, 116, 34, "capteur", 6), text(818, 292, "pytest", "t-code", "middle"),
          text(640, 296, "testé seul, en millisecondes", "t-petit", "middle"),
          line(422, 170, 498, 170, fin="trait")]
    return svg(920, 340, "Séparer le calcul du nœud pour le tester",
               "Avant : le calcul de l'odométrie est écrit dans le nœud ROS, mêlé à l'abonnement, à la minuterie et à la "
               "publication ; pour le tester, il faut lancer ROS. Après : le nœud est fin, il reçoit les vitesses, appelle "
               "integrer() et publie ; le calcul vit dans odometrie/calcul.py (integrer, normaliser, vitesses_roues), "
               "sans ROS, et pytest le teste seul, en quelques millisecondes.", "\n".join(b))


def pyramide():
    b = [rect(20, 20, 880, 300, "fond", 12)]
    etages = [("système et simulation", "le robot entier, rejeu de données", "module 42", 270, "boite"),
              ("intégration", "plusieurs nœuds, launch_testing", "module 41", 370, "boite"),
              ("unitaires", "une fonction, pytest", "ce module", 470, "calcul")]
    for i, (nom, detail, ou, largeur, cls) in enumerate(etages):
        y = 48 + i * 86
        b += [rect(360 - largeur / 2, y, largeur, 72, cls, 8),
              text(360, y + 32, nom, "t-gras", "middle"), text(360, y + 54, detail, "t-petit", "middle"),
              text(640, y + 42, ou, "t-accent" if cls == "calcul" else "t-petit")]
    b += [line(780, 70, 780, 286, "trait", fin="trait", debut="trait"),
          text(796, 92, "plus lents", "t-petit"), text(796, 110, "plus réalistes", "t-petit"),
          text(796, 260, "rapides,", "t-petit"), text(796, 278, "nombreux", "t-petit")]
    return svg(920, 340, "La pyramide des tests",
               "Trois étages de tests, du bas vers le haut. En bas, les tests unitaires : une fonction testée avec pytest, "
               "rapides et nombreux (ce module). Au milieu, les tests d'intégration : plusieurs nœuds ensemble avec "
               "launch_testing (module 41). En haut, les tests du système et de simulation : le robot entier, avec des "
               "données rejouées (module 42), plus lents mais plus réalistes.", "\n".join(b))


def mutants():
    b = [rect(20, 20, 880, 320, "fond", 12), text(40, 48, "VOS TESTS FACE À DES BUGS VOLONTAIRES", "t-sur"),
         rect(40, 130, 180, 90, "capteur", 8), text(130, 166, "vos tests", "t-gras", "middle"),
         text(130, 190, "test_calcul.py", "t-code", "middle")]
    cibles = [("calcul correct", "tous les tests doivent réussir", "calcul", "tous réussis : bien", "t-accent"),
              ("mutant : cos et sin inversés", "au moins un test doit échouer", "boite", "un test échoue : attrapé", "t-accent"),
              ("mutant : dt oublié", "au moins un test doit échouer", "boite", "un test échoue : attrapé", "t-accent"),
              ("mutant : -pi au lieu de pi", "au moins un test doit échouer", "boite", "tout réussit : raté", "t-ambre")]
    for i, (nom, attendu, cls, verdict, cls_v) in enumerate(cibles):
        y = 66 + i * 66
        b += [path(f"M222 175 C 280 175, 300 {y + 25}, 358 {y + 25}", "trait", fin="trait"),
              rect(360, y, 300, 50, cls, 8), text(376, y + 22, nom, "t-gras"), text(376, y + 41, attendu, "t-petit")]
        b.append(text(684, y + 31, verdict, cls_v))
    b.append(text(460, 326, "un bug raté : il manque un test, ici celui de normaliser(pi)", "t-petit", "middle"))
    return svg(920, 350, "Mesurer ses tests avec des mutants",
               "Vos tests sont lancés sur le calcul correct, où ils doivent réussir, puis sur des versions volontairement "
               "buggées, les mutants : cos et sin inversés, dt oublié, -pi renvoyé au lieu de pi. Sur chaque mutant, au moins "
               "un test doit échouer : le bug est alors attrapé. Si un mutant passe tous les tests, comme ici celui de "
               "normaliser(pi), c'est qu'il manque un test.", "\n".join(b))


def cablage():
    b = [rect(20, 20, 420, 300, "fond", 12), text(40, 48, "TEST UNITAIRE", "t-sur"),
         rect(44, 70, 172, 50, "capteur", 8), text(130, 100, "test_borner()", "t-code", "middle"),
         line(218, 95, 262, 95, fin="trait"),
         rect(264, 70, 152, 50, "calcul", 8), text(340, 100, "borner()", "t-code", "middle"),
         text(44, 156, "voit :", "t-gras"), text(60, 180, "le calcul, ses cas limites", "t-petit"),
         text(44, 216, "ne voit pas :", "t-gras"), text(60, 240, "les noms des topics", "t-petit"),
         text(60, 260, "les paramètres de lancement", "t-petit"), text(60, 280, "le démarrage et l'arrêt du nœud", "t-petit")]
    b += [rect(480, 20, 420, 300, "fond", 12), text(500, 48, "TEST D'INTÉGRATION", "t-sur"),
          rect(504, 70, 372, 112, "boite", 8), text(520, 94, "nœud limiteur, lancé pour de vrai", "t-gras"),
          rect(516, 106, 126, 30, "capteur", 6), text(579, 126, "/cmd_vel_brut", "t-code", "middle"),
          rect(658, 106, 92, 30, "calcul", 6), text(704, 126, "borner()", "t-code", "middle"),
          rect(766, 106, 96, 30, "capteur", 6), text(814, 126, "/cmd_vel", "t-code", "middle"),
          line(643, 121, 656, 121, fin="trait"), line(751, 121, 764, 121, fin="trait"),
          text(520, 164, "paramètre vitesse_max : 0.3", "t-code"),
          text(504, 216, "voit en plus :", "t-gras"), text(520, 240, "un topic renommé, plus personne n'écoute", "t-petit"),
          text(520, 260, "un paramètre ignoré", "t-petit"), text(520, 280, "un nœud qui plante ou quitte en erreur", "t-petit"),
          text(690, 306, "plus lent : quelques secondes par fichier", "t-ambre", "middle")]
    return svg(920, 340, "Ce que voit un test unitaire, et ce que voit un test d'intégration",
               "À gauche, le test unitaire appelle directement la fonction borner() : il voit le calcul et ses cas limites, "
               "mais pas les noms des topics, les paramètres de lancement, ni le démarrage et l'arrêt du nœud. À droite, le "
               "test d'intégration lance le vrai nœud limiteur, avec le paramètre vitesse_max à 0.3 : les commandes "
               "arrivent sur /cmd_vel_brut, passent par borner() et repartent sur /cmd_vel. Il voit en plus un topic "
               "renommé, un paramètre ignoré, un nœud qui plante ou quitte en erreur. Il est plus lent : quelques "
               "secondes par fichier.", "\n".join(b))


def integration():
    b = [rect(20, 20, 880, 300, "fond", 12), text(40, 48, "UN TEST LAUNCH_TESTING", "t-sur"),
         rect(40, 70, 840, 74, "boite", 8), text(60, 96, "generate_test_description()", "t-code"),
         text(60, 120, "lance le nœud limiteur (vitesse_max : 0.3), puis ReadyToTest()", "t-petit"),
         rect(60, 180, 230, 104, "capteur", 8), text(175, 210, "nœud testeur", "t-gras", "middle"),
         text(175, 234, "créé par le test", "t-petit", "middle"), text(175, 262, "envoyer(1.0, 0.0)", "t-code", "middle"),
         rect(630, 180, 230, 104, "calcul", 8), text(745, 210, "nœud limiteur", "t-gras", "middle"),
         text(745, 234, "le vrai nœud, lancé", "t-petit", "middle"), text(745, 262, "borne à 0.3", "t-code", "middle"),
         line(292, 206, 626, 206, fin="trait"), text(460, 198, "/cmd_vel_brut : v = 1.0", "t-code", "middle"),
         line(628, 258, 294, 258, fin="trait"), text(460, 250, "/cmd_vel : v = 0.3", "t-code", "middle"),
         text(460, 280, "assertAlmostEqual(sortie.linear.x, 0.3)", "t-accent", "middle"),
         line(745, 146, 745, 178, "tirets", fin="trait")]
    return svg(920, 340, "Un test launch_testing du limiteur",
               "generate_test_description() lance le vrai nœud limiteur avec le paramètre vitesse_max à 0.3, puis "
               "ReadyToTest(). Le test crée un nœud testeur qui publie une commande v = 1.0 sur /cmd_vel_brut ; le "
               "limiteur la borne et publie v = 0.3 sur /cmd_vel ; le testeur la reçoit et vérifie "
               "assertAlmostEqual(sortie.linear.x, 0.3).", "\n".join(b))


def deroulement():
    b = [rect(20, 20, 880, 260, "fond", 12), text(40, 48, "LE DÉROULEMENT D'UN TEST", "t-sur")]
    etapes = [("lancement", "les nœuds de la", "description démarrent", "boite"),
              ("ReadyToTest", "les tests peuvent", "commencer", "boite"),
              ("tests actifs", "publier, attendre,", "vérifier", "capteur"),
              ("arrêt", "launch envoie SIGINT", "à chaque nœud", "boite"),
              ("après l'arrêt", "assertExitCodes", "(proc_info)", "calcul")]
    for i, (nom, l1, l2, cls) in enumerate(etapes):
        x = 40 + i * 172
        b += [rect(x, 80, 152, 110, cls, 8), text(x + 76, 112, nom, "t-gras", "middle"),
              text(x + 76, 142, l1, "t-petit", "middle"), text(x + 76, 162, l2, "t-petit", "middle")]
        if i < len(etapes) - 1:
            b.append(line(x + 154, 135, x + 170, 135, fin="trait"))
    b += [line(60, 214, 690, 214, "tirets", debut="trait", fin="trait"),
          text(375, 236, "le limiteur tourne", "t-petit", "middle"),
          text(728, 236, "codes de sortie", "t-ambre"), text(728, 254, "vérifiés", "t-ambre")]
    return svg(920, 300, "Le déroulement d'un test launch_testing",
               "Cinq étapes, de gauche à droite : le lancement des nœuds de la description ; ReadyToTest, les tests "
               "peuvent commencer ; les tests actifs, qui publient, attendent et vérifient pendant que le limiteur tourne ; "
               "l'arrêt, où launch envoie SIGINT à chaque nœud ; les tests après l'arrêt, où assertExitCodes(proc_info) "
               "vérifie les codes de sortie.", "\n".join(b))


def enregistrer_rejouer():
    b = [rect(20, 20, 420, 300, "fond", 12), text(40, 48, "SUR LE ROBOT, DANS L'ALLÉE 3", "t-sur"),
         robot(100, 120, 0, 1.1),
         rect(170, 98, 110, 44, "capteur", 8), text(225, 126, "/scan", "t-code", "middle"),
         line(282, 120, 316, 120, fin="trait"),
         rect(318, 92, 104, 56, "boite", 8), text(370, 116, "ros2 bag", "t-code", "middle"),
         text(370, 136, "record", "t-code", "middle"),
         line(370, 150, 370, 196, fin="trait"),
         rect(280, 198, 180, 96, "calcul", 8), text(370, 224, "allee3/", "t-gras", "middle"),
         text(370, 248, "metadata.yaml", "t-code", "middle"), text(370, 270, "allee3_0.mcap", "t-code", "middle"),
         text(60, 230, "le bug se produit ici,", "t-petit"), text(60, 250, "on enregistre ce que", "t-petit"),
         text(60, 270, "le lidar a vu", "t-petit")]
    b += [path("M462 246 C 500 246, 500 246, 520 246", "tirets", fin="trait"), text(490, 236, "copie", "t-petit", "middle")]
    b += [rect(520, 20, 380, 300, "fond", 12), text(540, 48, "SUR VOTRE POSTE", "t-sur"),
          rect(540, 198, 120, 96, "calcul", 8), text(600, 224, "allee3/", "t-gras", "middle"),
          text(600, 248, "les mêmes", "t-petit", "middle"), text(600, 268, "messages", "t-petit", "middle"),
          line(600, 196, 600, 152, fin="trait"),
          rect(540, 92, 120, 58, "boite", 8), text(600, 116, "ros2 bag", "t-code", "middle"), text(600, 136, "play", "t-code", "middle"),
          line(662, 120, 712, 120, fin="trait"), text(687, 110, "/scan", "t-code", "middle"),
          rect(714, 92, 168, 58, "capteur", 8), text(798, 116, "arret_urgence", "t-code", "middle"),
          text(798, 136, "le nœud étudié", "t-petit", "middle"),
          line(798, 152, 798, 196, fin="trait"),
          rect(714, 198, 168, 44, "boite", 8), text(798, 226, "/arret", "t-code", "middle"),
          text(798, 272, "le bug, reproduit", "t-ambre", "middle")]
    return svg(920, 340, "Enregistrer sur le robot, rejouer sur son poste",
               "À gauche, sur le robot dans l'allée 3, là où le bug se produit : ros2 bag record enregistre le topic /scan "
               "du lidar dans le dossier allee3, qui contient metadata.yaml et le fichier de données allee3_0.mcap. Le "
               "dossier est copié sur le poste du développeur. À droite, ros2 bag play republie les mêmes messages sur "
               "/scan devant le nœud arret_urgence, qui publie sa décision sur /arret : le bug est reproduit.",
               "\n".join(b))


def scan_laser():
    cx, cy = 300, 205
    b = [rect(20, 20, 880, 330, "fond", 12), text(40, 48, "UN SCAN LASER, VU DE DESSUS", "t-sur"),
         f'<circle class="tirets" cx="{cx}" cy="{cy}" r="140"/>', f'<circle class="tirets" cx="{cx}" cy="{cy}" r="34"/>']
    mesures = [(-80, 1.0), (-60, 1.0), (-40, 1.0), (-20, 1.0), (0, None), (20, 1.0), (40, 0.0), (60, 1.0), (80, 1.0),
               (100, 1.0), (120, 1.0), (140, 1.0), (160, 1.0), (180, None), (200, 1.0), (220, 1.0), (240, 0.0), (260, 1.0)]
    zeros = []
    for angle, valeur in mesures:
        a = math.radians(angle)
        if valeur is None:          # rien à portée : inf
            x, y = cx + 140 * math.cos(a), cy - 140 * math.sin(a)
            b.append(line(cx, cy, x, y, "tirets"))
            continue
        d = 0 if valeur == 0.0 else min(124, 90 / max(abs(math.sin(a)), 0.73))
        x, y = cx + d * math.cos(a), cy - d * math.sin(a)
        if valeur == 0.0:
            zeros.append(f'<circle class="cir" cx="{cx + 22 * math.cos(a):.1f}" cy="{cy - 22 * math.sin(a):.1f}" r="5"/>')
        else:
            b += [line(cx, cy, x, y, "trait"), f'<circle class="roue" cx="{x:.1f}" cy="{y:.1f}" r="4"/>']
    b += [robot(cx, cy, 90, 0.4)] + zeros + [
          text(cx + 112, cy - 112, "range_max", "t-code"), text(cx + 40, cy + 44, "range_min", "t-code")]
    b += [text(520, 92, "mesure valide", "t-gras"), text(520, 112, "entre range_min et range_max : un mur, un obstacle", "t-petit"),
          f'<circle class="roue" cx="508" cy="88" r="4"/>',
          text(520, 160, "inf", "t-gras"), text(520, 180, "rien à portée sur ce rayon", "t-petit"),
          line(496, 156, 510, 156, "tirets"),
          text(520, 228, "0.0", "t-gras"), text(520, 248, "le laser n'est pas revenu : pas une distance", "t-petit"),
          f'<circle class="cir" cx="508" cy="224" r="5"/>',
          text(520, 300, "le message dit lesquelles sont fiables :", "t-petit"),
          text(520, 320, "ros2 interface show sensor_msgs/msg/LaserScan", "t-code")]
    return svg(920, 370, "Ce que contient un scan laser",
               "Le robot vu de dessus, au centre, avec ses rayons laser tout autour. Deux cercles en tirets marquent "
               "range_min, près du robot, et range_max, la portée du capteur. Les mesures valides, entre les deux, "
               "touchent les murs. Certains rayons ne rencontrent rien à portée : leur distance vaut inf. Pour deux "
               "rayons, le laser n'est pas revenu : la distance vaut 0.0, ce qui n'est pas une vraie distance. La "
               "définition du message, ros2 interface show sensor_msgs/msg/LaserScan, dit quelles mesures sont fiables.",
               "\n".join(b))


def non_regression():
    b = [rect(20, 20, 880, 300, "fond", 12), text(40, 48, "DU BUG AU TEST DE NON-RÉGRESSION", "t-sur")]
    etapes = [("1. le bug", "le robot s'arrête", "sans raison", "boite"),
              ("2. enregistrer", "ros2 bag record", "/scan", "boite"),
              ("3. reproduire", "ros2 bag play,", "le bug revient", "boite"),
              ("4. un test", "qui rejoue le bag :", "il échoue", "capteur"),
              ("5. corriger", "le test réussit,", "il reste dans la CI", "calcul")]
    for i, (nom, l1, l2, cls) in enumerate(etapes):
        x = 40 + i * 172
        b += [rect(x, 84, 152, 110, cls, 8), text(x + 76, 116, nom, "t-gras", "middle"),
              text(x + 76, 146, l1, "t-petit", "middle"), text(x + 76, 166, l2, "t-petit", "middle")]
        if i < len(etapes) - 1:
            b.append(line(x + 154, 139, x + 170, 139, fin="trait"))
    b += [path("M764 196 C 764 262, 592 262, 592 198", "tirets", fin="trait"),
          text(678, 280, "le bug revient ? le test échoue", "t-ambre", "middle"),
          text(212, 240, "le test s'écrit AVANT la correction :", "t-petit", "middle"),
          text(212, 260, "le voir échouer prouve qu'il attrape le bug", "t-petit", "middle")]
    return svg(920, 340, "Du bug au test de non-régression",
               "Cinq étapes : 1, le robot s'arrête sans raison ; 2, on enregistre /scan avec ros2 bag record ; 3, on "
               "rejoue avec ros2 bag play et le bug revient ; 4, on écrit un test qui rejoue le bag, et il échoue ; 5, on "
               "corrige, le test réussit et reste dans l'intégration continue. Si le bug revient un jour, le test échoue. "
               "Le test s'écrit avant la correction : le voir échouer prouve qu'il attrape le bug.", "\n".join(b))


def pipeline():
    b = [rect(20, 20, 880, 300, "fond", 12), text(40, 48, "UNE PULL REQUEST ET SA CI", "t-sur")]
    etapes = [("développeur", "git push, puis", "pull request", "boite"),
              ("CI : machine neuve", "checkout, dépendances,", "compilation, tests", "calcul"),
              ("résultat", "affiché sur la", "pull request", "capteur")]
    for i, (nom, l1, l2, cls) in enumerate(etapes):
        x = 40 + i * 230
        b += [rect(x, 76, 200, 104, cls, 8), text(x + 100, 108, nom, "t-gras", "middle"),
              text(x + 100, 136, l1, "t-petit", "middle"), text(x + 100, 156, l2, "t-petit", "middle")]
        if i < 2:
            b.append(line(x + 202, 128, x + 228, 128, fin="trait"))
    b += [line(642, 104, 700, 92, fin="trait"), line(642, 152, 700, 214, fin="trait"),
          rect(702, 66, 178, 52, "calcul", 8), text(791, 90, "✔ vert", "t-accent", "middle"),
          text(791, 108, "fusion possible dans main", "t-petit", "middle"),
          rect(702, 188, 178, 52, "capteur", 8), text(791, 212, "✘ rouge", "t-ambre", "middle"),
          text(791, 230, "on corrige, on repousse", "t-petit", "middle"),
          path("M702 226 C 400 284, 160 284, 140 182", "tirets", fin="trait"),
          text(420, 300, "nouvelle tentative : la CI repart de zéro", "t-petit", "middle")]
    return svg(920, 340, "Une pull request et son intégration continue",
               "Le développeur pousse sa branche et ouvre une pull request. La CI démarre sur une machine neuve : "
               "récupération du code, dépendances, compilation, tests. Le résultat s'affiche sur la pull request : vert, "
               "la fusion dans main est possible ; rouge, on corrige et on repousse, et la CI repart de zéro.",
               "\n".join(b))


def workflow():
    b = [rect(20, 20, 880, 330, "fond", 12), text(40, 48, ".GITHUB/WORKFLOWS/CI.YML", "t-sur"),
         rect(40, 70, 260, 260, "capteur", 8), text(60, 98, "on", "t-code"), text(60, 120, "quand ?", "t-gras"),
         text(60, 154, "push sur main", "t-petit"), text(60, 176, "pull_request", "t-petit"),
         text(60, 224, "sans pull_request, l'erreur", "t-petit"), text(60, 244, "n'apparaît qu'après la fusion", "t-petit"),
         rect(320, 70, 260, 260, "boite", 8), text(340, 98, "jobs", "t-code"), text(340, 120, "sur quelle machine ?", "t-gras"),
         text(340, 154, "runs-on: ubuntu-24.04", "t-code"), text(340, 176, "container:", "t-code"),
         text(352, 196, "ros:jazzy-ros-base", "t-code"),
         text(340, 244, "une machine neuve à chaque fois", "t-petit"),
         rect(600, 70, 280, 260, "calcul", 8), text(620, 98, "steps", "t-code"), text(620, 120, "quoi, dans l'ordre ?", "t-gras")]
    pas = [("actions/checkout", "✔"), ("dépendances (rosdep)", "✔"), ("colcon build", "✔"), ("colcon test", "✔"),
           ("colcon test-result", "✘")]
    for i, (nom, res) in enumerate(pas):
        y = 140 + i * 30
        b += [rect(620, y, 200, 24, "boite", 5), text(632, y + 17, nom, "t-code"),
              text(842, y + 17, res, "t-accent" if res == "✔" else "t-ambre", "middle")]
    b.append(text(740, 318, "une étape échoue : le job s'arrête, rouge", "t-ambre", "middle"))
    return svg(920, 370, "Les trois parties d'un workflow GitHub Actions",
               "Le fichier .github/workflows/ci.yml a trois parties. on : quand il se déclenche, à chaque push sur main "
               "et à chaque pull_request ; sans pull_request, l'erreur n'apparaît qu'après la fusion. jobs : sur quelle "
               "machine, ici ubuntu-24.04 avec le conteneur ros:jazzy-ros-base, une machine neuve à chaque fois. steps : "
               "les étapes dans l'ordre, actions/checkout, dépendances avec rosdep, colcon build, colcon test, colcon "
               "test-result. Ici colcon test-result échoue : le job s'arrête et devient rouge.", "\n".join(b))


def codes_sortie():
    b = [rect(20, 20, 880, 280, "fond", 12), text(40, 48, "UN TEST ÉCHOUE : QUE RENVOIENT LES COMMANDES ?", "t-sur"),
         rect(40, 76, 200, 60, "boite", 8), text(140, 104, "1 test sur 12", "t-gras", "middle"),
         text(140, 124, "échoue", "t-petit", "middle")]
    lignes = [("colcon test", "lance les tests, enregistre les résultats", "code 0", "t-accent", "l'étape reste verte : le piège", 92),
              ("colcon test-result", "lit les résultats enregistrés", "code 1", "t-ambre", "l'étape échoue : la CI est rouge", 196)]
    for cmd, detail, code, cls, effet, y in lignes:
        b += [path(f"M242 106 C 280 106, 290 {y + 28}, 318 {y + 28}", "trait", fin="trait"),
              rect(320, y, 260, 56, "calcul", 8), text(340, y + 24, cmd, "t-code"), text(340, y + 44, detail, "t-petit"),
              line(582, y + 28, 616, y + 28, fin="trait"),
              rect(618, y, 92, 56, "capteur" if code == "code 1" else "boite", 8), text(664, y + 34, code, cls, "middle"),
              text(726, y + 24, effet.split(" : ")[0], "t-gras"), text(726, y + 44, effet.split(" : ")[1], "t-petit")]
    b.append(text(460, 284, "vérifiez votre CI : cassez un test exprès, elle doit devenir rouge", "t-petit", "middle"))
    return svg(920, 320, "colcon test et colcon test-result face à un test qui échoue",
               "Un test sur douze échoue. colcon test lance les tests et enregistre les résultats, mais renvoie le code 0 : "
               "l'étape de la CI reste verte, c'est le piège. colcon test-result lit les résultats enregistrés et renvoie "
               "le code 1 : l'étape échoue et la CI devient rouge. Pour vérifier une CI, on casse un test exprès : elle "
               "doit devenir rouge.", "\n".join(b))


SCHEMAS = {
    f"{UNITAIRES}/images/separation.svg": separation,
    f"{UNITAIRES}/images/pyramide.svg": pyramide,
    f"{UNITAIRES}/images/mutants.svg": mutants,
    f"{INTEGRATION}/images/cablage.svg": cablage,
    f"{INTEGRATION}/images/integration.svg": integration,
    f"{INTEGRATION}/images/deroulement.svg": deroulement,
    f"{REJEU}/images/enregistrer-rejouer.svg": enregistrer_rejouer,
    f"{REJEU}/images/scan.svg": scan_laser,
    f"{REJEU}/images/non-regression.svg": non_regression,
    f"{CI}/images/pipeline.svg": pipeline,
    f"{CI}/images/workflow.svg": workflow,
    f"{CI}/images/codes-sortie.svg": codes_sortie,
}

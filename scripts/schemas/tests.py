"""Schémas du parcours « Tester et fiabiliser » : tests unitaires (module 40), tests d'intégration (module 41)."""

from style import line, path, rect, svg, text

UNITAIRES = "40-tests-unitaires"
INTEGRATION = "41-tests-integration"


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


SCHEMAS = {
    f"{UNITAIRES}/images/separation.svg": separation,
    f"{UNITAIRES}/images/pyramide.svg": pyramide,
    f"{UNITAIRES}/images/mutants.svg": mutants,
    f"{INTEGRATION}/images/cablage.svg": cablage,
    f"{INTEGRATION}/images/integration.svg": integration,
    f"{INTEGRATION}/images/deroulement.svg": deroulement,
}

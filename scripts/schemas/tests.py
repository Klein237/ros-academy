"""Schémas du parcours « Tester et fiabiliser » : séparer le calcul du nœud, la pyramide des tests, les mutants."""

from style import line, path, rect, svg, text

UNITAIRES = "40-tests-unitaires"


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


SCHEMAS = {
    f"{UNITAIRES}/images/separation.svg": separation,
    f"{UNITAIRES}/images/pyramide.svg": pyramide,
    f"{UNITAIRES}/images/mutants.svg": mutants,
}

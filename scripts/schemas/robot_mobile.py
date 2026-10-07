"""Schémas du module « Le robot mobile »."""

import math

from style import arc, axes, esc, line, path, rect, robot, svg, text

MODULE = "01-robot-mobile"


def architecture():
    b = []
    cols = [(20, "PERCEVOIR · les capteurs", "capteur",
             ["Lidar : distances", "Caméra : images", "Encodeurs : roues", "Centrale inertielle"]),
            (320, "DÉCIDER · l'ordinateur", "calcul", ["Où suis-je ?", "Où aller ?", "À quelle vitesse ?"]),
            (620, "AGIR · les actionneurs", "actionneur", ["Contrôleur moteurs", "Moteurs, réducteurs", "Roues"])]
    for x, titre, cls, lignes in cols:
        b.append(text(x, 40, titre, "t-sur"))
        b.append(rect(x, 52, 220, 150, cls, 12))
        for i, l in enumerate(lignes):
            b.append(text(x + 18, 86 + 30 * i, l))
    for x, mot in ((240, "mesures"), (540, "ordres")):
        b.append(line(x + 6, 127, x + 74, 127, fin="trait"))
        b.append(text(x + 40, 117, mot, "t-petit", "middle"))
    b.append(rect(320, 214, 220, 32, "badge", 16))
    b.append(text(430, 235, "ROS 2 relie ces programmes", "t-badge", "middle"))
    # la boucle : le robot bouge, les mesures changent
    b.append(path("M730 202 C 730 290, 130 290, 130 206", "tirets", fin="trait"))
    b.append(text(430, 318, "le robot bouge, les mesures changent : la boucle recommence", "t-petit", "middle"))
    return svg(860, 330, "L'architecture d'un robot mobile",
               "Une boucle en trois temps : les capteurs perçoivent, l'ordinateur embarqué décide (où suis-je, "
               "où aller, à quelle vitesse), les actionneurs agissent. ROS 2 relie tous ces programmes.", "\n".join(b))


def locomotion():
    b = [text(30, 30, "DIFFÉRENTIEL", "t-sur"), text(440, 30, "ACKERMANN (VOITURE)", "t-sur"),
         line(410, 20, 410, 330, "sep")]
    # différentiel : deux roues motrices sur un même axe, centre de rotation sur cet axe
    cx, cy = 210, 220
    b.append(robot(cx, cy, 90, 1.6))
    b.append(line(cx - 150, cy, cx + 30, cy, "tirets"))
    icr = (cx - 130, cy)
    b.append(f'<circle class="cir" cx="{icr[0]}" cy="{icr[1]}" r="5"/>')
    b.append(text(icr[0], icr[1] + 22, "centre de rotation", "t-ambre", "middle"))
    b.append(text(icr[0], icr[1] + 38, "sur l'axe des roues", "t-petit", "middle"))
    b.append(arc(*icr, 130, 0, 45, "trajet", "trajet"))
    b.append(text(30, 300, "2 roues motrices indépendantes + une roulette.", "t-petit"))
    b.append(text(30, 318, "Tourne sur place (v = 0). Le robot du parcours.", "t-petit"))
    # Ackermann : 4 roues, les roues avant braquent ; le centre de rotation est sur l'axe arrière
    ox, oy = 640, 250  # milieu de l'essieu arrière
    lon, voie = 120, 64
    b.append(rect(ox - voie / 2 - 6, oy - lon - 24, voie + 12, lon + 48, "robot", 14))
    for dx in (-voie / 2, voie / 2):
        b.append(f'<rect class="roue" x="{ox + dx - 5:.1f}" y="{oy - 14:.1f}" width="10" height="28" rx="3"/>')
    icr = (ox - 190, oy)
    for dx in (-voie / 2, voie / 2):  # chaque roue avant est perpendiculaire à la droite qui la relie au centre
        wx, wy = ox + dx, oy - lon
        # le grand côté de la roue (sens de roulement) est perpendiculaire à la droite roue-centre
        a = math.degrees(math.atan2(wy - icr[1], wx - icr[0]))
        b.append(f'<rect class="roue" x="-5" y="-14" width="10" height="28" rx="3" '
                 f'transform="translate({wx:.1f} {wy:.1f}) rotate({a:.1f})"/>')
        b.append(line(icr[0], icr[1], wx, wy, "tirets"))
    b.append(line(icr[0], oy, ox + voie / 2 + 20, oy, "tirets"))
    b.append(f'<circle class="cir" cx="{icr[0]}" cy="{icr[1]}" r="5"/>')
    b.append(text(icr[0] + 4, icr[1] + 22, "centre de rotation", "t-ambre", "middle"))
    b.append(text(icr[0] + 4, icr[1] + 38, "sur l'axe arrière", "t-petit", "middle"))
    b.append(text(440, 300, "Les roues avant braquent, chacune d'un angle différent.", "t-petit"))
    b.append(text(440, 318, "Ne tourne pas sur place : il lui faut un rayon minimal.", "t-petit"))
    return svg(830, 335, "Deux façons de tourner : différentiel et Ackermann",
               "À gauche, un robot différentiel : deux roues motrices indépendantes sur un même axe ; son centre de "
               "rotation est sur cet axe, il peut tourner sur place. À droite, une voiture (Ackermann) : les roues "
               "avant braquent pour viser un centre de rotation situé sur l'axe arrière.", "\n".join(b))


def pose():
    b = [rect(20, 20, 480, 330, "fond", 12)]
    o = (70, 300)  # origine du repère odom, 100 px par mètre
    for i in range(5):
        b.append(line(o[0] + 100 * i, 30, o[0] + 100 * i, 340, "grille"))
    for j in range(3):
        b.append(line(30, o[1] - 100 * j, 490, o[1] - 100 * j, "grille"))
    b.append(axes(*o, 0, 60, "odom", -10, 26))
    r = (o[0] + 250, o[1] - 150)  # robot en (2,5 ; 1,5)
    th = 35
    b.append(line(r[0], o[1], r[0], r[1], "tirets"))
    b.append(line(o[0], r[1], r[0], r[1], "tirets"))
    b.append(text((o[0] + r[0]) / 2, o[1] + 22, "x = 2,5 m", "t-math", "middle"))
    b.append(text(o[0] - 8, (o[1] + r[1]) / 2 + 5, "y = 1,5 m", "t-math", "end") if False else
             text(o[0] + 8, (o[1] + r[1]) / 2 - 4, "y = 1,5 m", "t-math"))
    b.append(robot(*r, th, 1.2))
    b.append(line(r[0], r[1], r[0] + 95, r[1], "tirets"))
    b.append(arc(*r, 78, 0, th, "trajet", "trajet"))
    b.append(text(r[0] + 88, r[1] - 22, "θ = 35°", "t-math"))
    b.append(axes(*r, th, 52, "base_link", -40, 64))
    b.append(text(260, 44, "la pose (x, y, θ) : où est le robot, et vers où il regarde", "t-petit", "middle"))
    return svg(520, 370, "La pose d'un robot : position et orientation",
               "Vue de dessus avec une grille d'un mètre. Le repère odom est fixe ; le robot est en x = 2,5 m, "
               "y = 1,5 m, tourné de θ = 35° par rapport à l'axe x d'odom. Son propre repère, base_link, le suit.",
               "\n".join(b))


def vitesses():
    b = []
    c = (300, 250)  # base_link, robot tourné vers le haut (90°)
    b.append(robot(*c, 90, 2.2))
    voie = 2 * 26.5 * 2.2  # distance entre les roues, à l'échelle du dessin
    g, d = (c[0] - voie / 2, c[1]), (c[0] + voie / 2, c[1])
    # vitesses des roues : la roue extérieure (droite) va plus vite pour tourner à gauche
    b.append(line(g[0] - 40, g[1], g[0] - 40, g[1] - 60, "vitesse", "vitesse"))
    b.append(text(g[0] - 48, g[1] - 66, "v_g", "t-math", "end"))
    b.append(line(d[0] + 40, d[1], d[0] + 40, d[1] - 110, "vitesse", "vitesse"))
    b.append(text(d[0] + 48, d[1] - 114, "v_d", "t-math"))
    b.append(line(c[0], c[1] - 70, c[0], c[1] - 150, "vitesse", "vitesse"))
    b.append(text(c[0] + 10, c[1] - 140, "v (m/s)", "t-math"))
    b.append(arc(c[0], c[1], 72, 112, 158, "trajet", "trajet"))
    b.append(text(c[0] - 58, c[1] - 84, "ω (rad/s)", "t-math", "end"))
    # voie L entre les roues
    y = c[1] + 92
    b.append(line(g[0], y, d[0], y, "trait", "trait", "trait"))
    b.append(text(c[0], y + 20, "L : distance entre les roues", "t-petit", "middle"))
    # centre de rotation, à gauche sur l'axe des roues, à la distance R = v / ω
    icr = (c[0] - 205, c[1])
    b.append(line(icr[0], c[1], g[0] - 6, c[1], "tirets"))
    b.append(f'<circle class="cir" cx="{icr[0]}" cy="{icr[1]}" r="5"/>')
    b.append(text(icr[0], icr[1] + 22, "centre de rotation", "t-ambre", "middle"))
    b.append(text((icr[0] + g[0]) / 2 - 20, c[1] - 10, "R = v / ω", "t-math", "middle"))
    b.append(text(620, 70, "Tourner à gauche :", "t-gras"))
    b.append(text(620, 94, "la roue droite va plus vite", "t"))
    b.append(text(620, 118, "que la roue gauche.", "t"))
    b.append(text(620, 160, "v_g = v − ω · L / 2", "t-math"))
    b.append(text(620, 186, "v_d = v + ω · L / 2", "t-math"))
    b.append(text(620, 228, "v = (v_d + v_g) / 2", "t-math"))
    b.append(text(620, 254, "ω = (v_d − v_g) / L", "t-math"))
    return svg(860, 380, "Vitesse linéaire, vitesse angulaire et vitesses des roues",
               "Le robot avance à la vitesse v et tourne à la vitesse angulaire ω. Pour tourner à gauche, la roue "
               "droite va plus vite que la gauche. Le robot décrit alors un cercle de rayon R = v / ω autour d'un "
               "centre situé sur l'axe des roues. Formules : v_g = v − ω·L/2, v_d = v + ω·L/2.", "\n".join(b))


def trajectoires():
    b = []
    cas = [("v > 0, ω = 0", "ligne droite"), ("v = 0, ω > 0", "rotation sur place"),
           ("v > 0, ω > 0", "arc de cercle, R = v / ω")]
    for i, (titre, sous) in enumerate(cas):
        x0 = 20 + 280 * i
        b.append(rect(x0, 20, 260, 250, "fond", 12))
        b.append(text(x0 + 130, 50, titre, "t-math", "middle"))
        b.append(text(x0 + 130, 70, sous, "t-petit", "middle"))
        cx, cy = x0 + 130, 210
        if i == 0:
            b.append(line(cx, cy - 30, cx, 95, "trajet", "trajet"))
            b.append(robot(cx, cy, 90, 1.0))
        elif i == 1:
            b.append(arc(cx, cy - 10, 60, 120, 400, "trajet", "trajet"))
            b.append(robot(cx, cy - 10, 90, 1.0))
        else:
            R = 95
            ic = (cx - R + 40, cy)
            b.append(f'<circle class="cir" cx="{ic[0]:.1f}" cy="{ic[1]:.1f}" r="4"/>')
            b.append(line(ic[0], ic[1], cx + 40, cy, "tirets"))
            b.append(arc(*ic, R, 0, 80, "trajet", "trajet"))
            b.append(text((ic[0] + cx + 40) / 2, cy + 20, "R", "t-math", "middle"))
            b.append(robot(cx + 40, cy, 90, 1.0))
    return svg(860, 290, "Trois commandes, trois trajectoires",
               "Avec ω = 0, le robot va en ligne droite. Avec v = 0, il tourne sur place. Avec v et ω positifs, "
               "il décrit un arc de cercle de rayon R = v / ω, vers la gauche.", "\n".join(b))


SCHEMAS = {
    f"{MODULE}/images/architecture.svg": architecture,
    f"{MODULE}/images/locomotion.svg": locomotion,
    f"{MODULE}/images/pose.svg": pose,
    f"{MODULE}/images/vitesses.svg": vitesses,
    f"{MODULE}/images/trajectoires.svg": trajectoires,
}

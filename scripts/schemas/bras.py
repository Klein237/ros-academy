"""Schémas du parcours bras robotique : chaîne articulaire, angles cumulés, triangle de la cinématique inverse."""

import math

from style import arc, line, path, rect, svg, text

MANIPULATEUR = "30-bras-manipulateur"
DIRECTE = "32-cinematique-directe"
INVERSE = "33-cinematique-inverse"

H, L1, L2, L3 = 0.10, 0.30, 0.25, 0.10


def points(q1, q2, q3, ox, oy, echelle):
    """Épaule, coude, poignet, pince en coordonnées écran (bras vu de côté, avant vers la droite)."""
    pts = [(ox, oy)]
    phi = 0.0
    for q, longueur in ((q1, L1), (q2, L2), (q3, L3)):
        phi += q
        x, y = pts[-1]
        pts.append((x + longueur * echelle * math.sin(phi), y - longueur * echelle * math.cos(phi)))
    return pts


def segments(pts, socle_y):
    ox, oy = pts[0]
    b = [rect(ox - 48, socle_y - 22, 96, 22, "actionneur", 4), rect(ox - 26, oy, 52, socle_y - 22 - oy, "boite", 4)]
    for (x1, y1), (x2, y2), cls in zip(pts, pts[1:], ("trajet", "trajet", "vitesse")):
        b.append(line(x1, y1, x2, y2, cls))
    for x, y in pts[:3]:
        b.append(f'<circle class="boite" cx="{x:.1f}" cy="{y:.1f}" r="9"/>')
        b.append(f'<circle class="roue" cx="{x:.1f}" cy="{y:.1f}" r="3"/>')
    x, y = pts[3]
    b.append(f'<circle class="cir" cx="{x:.1f}" cy="{y:.1f}" r="6"/>')
    return b


def chaine():
    q1, q2, q3 = 0.35, 0.9, 0.9
    pts = points(q1, q2, q3, 140, 280, 360)
    b = [rect(20, 20, 400, 330, "fond", 12), text(38, 48, "LE BRAS VU DE CÔTÉ", "t-sur")]
    b += segments(pts, 330)
    (e, c, p, t) = pts
    b += [text(e[0] - 16, e[1] + 5, "épaule", "t-code", "end"), text(c[0] - 14, c[1] - 6, "coude", "t-code", "end"),
          text(p[0] + 14, p[1] - 8, "poignet", "t-code"), text(t[0] - 12, t[1] + 22, "tool0 (pince)", "t-code", "middle"),
          text(e[0] + 60, 344, "base_rotation : la tourelle pivote", "t-petit", "middle"),
          text((e[0] + c[0]) / 2 - 12, (e[1] + c[1]) / 2 + 4, "bras", "t-accent", "end"),
          text((c[0] + p[0]) / 2 - 4, (c[1] + p[1]) / 2 - 14, "avant-bras", "t-accent", "middle")]
    b += [rect(450, 20, 410, 330, "fond", 12), text(468, 48, "DEUX FAÇONS DE DÉCRIRE LA POSE", "t-sur"),
          rect(468, 66, 374, 120, "calcul", 10), text(486, 92, "Espace articulaire", "t-gras"),
          text(486, 116, "un angle par articulation", "t-petit"),
          text(486, 144, f"(q0, q1, q2, q3) = (0.0, {q1}, {q2}, {q3})", "t-code"),
          text(486, 168, "ce que les moteurs connaissent", "t-petit"),
          rect(468, 208, 374, 120, "capteur", 10), text(486, 234, "Espace cartésien", "t-gras"),
          text(486, 258, "la position de la pince dans base_link", "t-petit")]
    x, y, z = position(0.0, q1, q2, q3)
    b += [text(486, 286, f"(x, y, z) = ({x:.2f}, {y:.2f}, {z:.2f}) m", "t-code"),
          text(486, 310, "ce que la tâche demande", "t-petit"),
          line(655, 188, 655, 206, "trait", fin="trait", debut="trait")]
    return svg(880, 370, "La chaîne articulaire du bras",
               "Vu de côté, le bras part du socle : l'épaule, le bras, le coude, l'avant-bras, le poignet et la pince, "
               "dont le point de prise s'appelle tool0. La tourelle pivote autour de la verticale (base_rotation). "
               "La même pose se décrit de deux façons : dans l'espace articulaire, par un angle par articulation, "
               "ce que connaissent les moteurs ; dans l'espace cartésien, par la position de la pince dans base_link, "
               "ce que demande la tâche.", "\n".join(b))


def position(q0, q1, q2, q3):
    r = L1 * math.sin(q1) + L2 * math.sin(q1 + q2) + L3 * math.sin(q1 + q2 + q3)
    z = H + L1 * math.cos(q1) + L2 * math.cos(q1 + q2) + L3 * math.cos(q1 + q2 + q3)
    return r * math.cos(q0), r * math.sin(q0), z


def angles_cumules():
    q1, q2, q3 = 0.45, 0.85, 1.0
    pts = points(q1, q2, q3, 150, 310, 470)
    b = [rect(20, 20, 840, 370, "fond", 12), text(38, 48, "DANS LE PLAN DU BRAS", "t-sur")]
    b += segments(pts, 380)
    (e, c, p, t) = pts
    # verticales de référence et angles mesurés depuis la verticale
    phis = (q1, q1 + q2, q1 + q2 + q3)
    noms = ("q1", "q1 + q2", "q1 + q2 + q3")
    for (x, y), phi, nom in zip((e, c, p), phis, noms):
        b.append(line(x, y, x, y - 70, "tirets"))
        a0 = 90.0
        a1 = 90.0 - math.degrees(phi)
        b.append(arc(x, y, 44, a0, a1, "trait", fin="trait"))
        b.append(text(x + 6, y - 76, nom, "t-math"))
    b += [line(e[0], e[1], t[0], e[1], "tirets"), text((e[0] + t[0]) / 2, e[1] + 20, "r", "t-math", "middle"),
          line(t[0], e[1], t[0], t[1], "tirets"), text(t[0] + 10, (e[1] + t[1]) / 2 + 20, "z − H", "t-math")]
    x0 = 560
    b += [rect(x0, 70, 280, 290, "boite", 10), text(x0 + 18, 98, "Chaque segment penche de la", "t-gras"),
          text(x0 + 18, 118, "somme des angles avant lui", "t-gras"),
          text(x0 + 18, 156, "r = L1·sin(q1)", "t-code"),
          text(x0 + 30, 178, "+ L2·sin(q1 + q2)", "t-code"),
          text(x0 + 30, 200, "+ L3·sin(q1 + q2 + q3)", "t-code"),
          text(x0 + 18, 236, "z = H + L1·cos(q1)", "t-code"),
          text(x0 + 30, 258, "+ L2·cos(q1 + q2)", "t-code"),
          text(x0 + 30, 280, "+ L3·cos(q1 + q2 + q3)", "t-code"),
          text(x0 + 18, 318, "puis la tourelle tourne de q0 :", "t-petit"),
          text(x0 + 18, 340, "x = r·cos(q0) ; y = r·sin(q0)", "t-code")]
    return svg(880, 410, "Les angles se cumulent le long du bras",
               "Dans le plan vertical du bras, chaque angle se mesure depuis la verticale. Le bras penche de q1, "
               "l'avant-bras de q1 plus q2, la pince de q1 plus q2 plus q3 : chaque segment hérite de l'inclinaison "
               "de tous ceux qui le portent. La distance horizontale r et la hauteur z s'obtiennent en ajoutant les "
               "trois segments, puis la rotation de la tourelle q0 donne x égal r cosinus q0 et y égal r sinus q0.",
               "\n".join(b))


def triangle():
    # cible (0.35, 0, 0.30), pince vers le bas
    u, v = 0.35, 0.30 + L3 - H
    d = (u * u + v * v - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    q2 = math.acos(d)
    q1 = math.atan2(u, v) - math.atan2(L2 * math.sin(q2), L1 + L2 * math.cos(q2))
    q3 = math.pi - q1 - q2
    s = 520
    pts = points(q1, q2, q3, 110, 340, s)
    b = [rect(20, 20, 840, 390, "fond", 12), text(38, 48, "LA CIBLE, VUE DANS LE PLAN DU BRAS", "t-sur")]
    b += segments(pts, 400)
    (e, c, p, t) = pts
    b += [line(e[0], e[1], p[0], p[1], "tirets"),
          line(e[0], e[1], p[0], e[1], "tirets"), line(p[0], e[1], p[0], p[1], "tirets"),
          text((e[0] + p[0]) / 2, e[1] + 20, "u", "t-math", "middle"),
          text(p[0] + 12, (e[1] + p[1]) / 2 + 40, "v", "t-math"),
          text(e[0] - 14, e[1] + 5, "épaule", "t-code", "end"), text(c[0] - 12, c[1] - 10, "coude", "t-code", "end"),
          text(p[0] + 14, p[1] - 8, "poignet", "t-code"), text(t[0] + 14, t[1] + 5, "cible", "t-ambre"),
          text(t[0] - 8, (p[1] + t[1]) / 2 + 4, "L3", "t-math", "end"),
          arc(e[0], e[1], 70, 90, 90 - math.degrees(math.atan2(u, v)), "trait", fin="trait"),
          text(e[0] + 8, e[1] - 96, "atan2(u, v)", "t-code")]
    x0 = 520
    b += [rect(x0, 70, 320, 320, "boite", 10), text(x0 + 18, 98, "1. Le poignet, au-dessus de la cible", "t-gras"),
          text(x0 + 18, 122, "u = √(x² + y²) ; v = z + L3 − H", "t-code"),
          text(x0 + 18, 160, "2. Le coude : loi des cosinus", "t-gras"),
          text(x0 + 18, 184, "d = (u² + v² − L1² − L2²) / (2·L1·L2)", "t-code"),
          text(x0 + 18, 206, "q2 = acos(d) ; |d| > 1 : trop loin", "t-code"),
          text(x0 + 18, 244, "3. L'épaule", "t-gras"),
          text(x0 + 18, 268, "q1 = atan2(u, v)", "t-code"),
          text(x0 + 52, 290, "− atan2(L2·sin q2, L1 + L2·cos q2)", "t-code"),
          text(x0 + 18, 328, "4. Le poignet, pince vers le bas", "t-gras"),
          text(x0 + 18, 352, "q3 = π − q1 − q2 ; q0 = atan2(y, x)", "t-code")]
    return svg(880, 430, "Le triangle de la cinématique inverse",
               "La pince doit pointer vers le bas : le poignet se place donc à L3 au-dessus de la cible. Dans le plan "
               "du bras, il est à une distance horizontale u et une hauteur v de l'épaule. Le bras et l'avant-bras "
               "forment avec la droite épaule-poignet un triangle dont on connaît les trois côtés : la loi des "
               "cosinus donne l'angle du coude q2. L'angle de l'épaule q1 est la direction du poignet, atan2 de u "
               "et v depuis la verticale, moins l'angle que fait le bras avec cette direction. Le poignet compense "
               "pour que la somme des trois angles vaille pi, et la tourelle tourne de atan2 de y et x.",
               "\n".join(b))


SCHEMAS = {
    f"{MANIPULATEUR}/images/chaine.svg": chaine,
    f"{DIRECTE}/images/angles-cumules.svg": angles_cumules,
    f"{INVERSE}/images/triangle.svg": triangle,
}

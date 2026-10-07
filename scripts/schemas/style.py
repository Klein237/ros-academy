"""Style commun des schémas des cours : couleurs du site, thème sombre intégré au SVG.

Un SVG chargé par <img> ne voit pas la feuille de style du site : il porte sa propre palette,
et la change sous @media (prefers-color-scheme: dark), comme le site.
"""

import html
import math

CSS = """
.fond { fill: #fbfbf9; stroke: #c9cfc9; stroke-width: 1.5; }
.grille { stroke: #e7eae6; stroke-width: 1; }
.boite { fill: #ffffff; stroke: #c9cfc9; stroke-width: 1.5; }
.calcul { fill: #e3f1ee; stroke: #0b5e57; stroke-width: 2; }
.capteur { fill: #fff8e8; stroke: #d39a2c; stroke-width: 2; }
.actionneur { fill: #eef1f5; stroke: #56606a; stroke-width: 2; }
.robot { fill: #e3f1ee; stroke: #0b5e57; stroke-width: 2; }
.roue { fill: #12171c; }
.roulette { fill: #ffffff; stroke: #12171c; stroke-width: 1.5; }
.nez { fill: #0b5e57; }
.ax-x { stroke: #d64545; stroke-width: 3; fill: none; } .ax-y { stroke: #2f9e44; stroke-width: 3; fill: none; }
.px { fill: #d64545; } .py { fill: #2f9e44; }
.trait { stroke: #56606a; stroke-width: 2; fill: none; }
.tirets { stroke: #8a949c; stroke-width: 1.5; stroke-dasharray: 5 5; fill: none; }
.trajet { stroke: #d39a2c; stroke-width: 3; fill: none; stroke-linecap: round; }
.trajet-pointe { fill: #d39a2c; }
.vitesse { stroke: #0b5e57; stroke-width: 3; fill: none; }
.vitesse-pointe { fill: #0b5e57; }
.pointe { fill: #56606a; }
.cir { fill: #d39a2c; }
.t { fill: #12171c; font: 400 14px "IBM Plex Sans", system-ui, sans-serif; }
.t-gras { fill: #12171c; font: 600 14px "IBM Plex Sans", system-ui, sans-serif; }
.t-titre { fill: #12171c; font: 600 16px "IBM Plex Sans", system-ui, sans-serif; }
.t-petit { fill: #56606a; font: 400 12.5px "IBM Plex Sans", system-ui, sans-serif; }
.t-sur { fill: #56606a; font: 600 12px "IBM Plex Sans", system-ui, sans-serif; letter-spacing: 0.08em; }
.t-math { fill: #12171c; font: italic 500 15px "IBM Plex Serif", Georgia, serif; }
.t-code { fill: #12171c; font: 500 13px "JetBrains Mono", "DejaVu Sans Mono", monospace; }
.t-accent { fill: #0b5e57; font: 600 13px "IBM Plex Sans", system-ui, sans-serif; }
.t-ambre { fill: #8a5d10; font: 600 13px "IBM Plex Sans", system-ui, sans-serif; }
.t-x { fill: #d64545; font: 600 13px "JetBrains Mono", monospace; } .t-y { fill: #2f9e44; font: 600 13px "JetBrains Mono", monospace; }
.badge { fill: #0b5e57; } .t-badge { fill: #ffffff; font: 600 12px "IBM Plex Sans", system-ui, sans-serif; }
.sep { stroke: #e2e5e1; stroke-width: 1.5; }
@media (prefers-color-scheme: dark) {
  .fond { fill: #0f161d; stroke: #34424f; } .grille { stroke: #1b2630; }
  .boite { fill: #121a22; stroke: #34424f; }
  .calcul, .robot { fill: #12302d; stroke: #4fb3a7; }
  .capteur { fill: #2a2212; stroke: #f2b544; }
  .actionneur { fill: #1a222b; stroke: #8a99a8; }
  .roue { fill: #c9d3dc; } .roulette { fill: #121a22; stroke: #c9d3dc; } .nez { fill: #4fb3a7; }
  .ax-x { stroke: #ff6b6b; } .ax-y { stroke: #51cf66; } .px, .t-x { fill: #ff6b6b; } .py, .t-y { fill: #51cf66; }
  .trait { stroke: #8a99a8; } .tirets { stroke: #5d6b78; } .pointe { fill: #8a99a8; }
  .trajet { stroke: #f2b544; } .trajet-pointe, .cir { fill: #f2b544; }
  .vitesse { stroke: #4fb3a7; } .vitesse-pointe { fill: #4fb3a7; }
  .t, .t-gras, .t-titre, .t-math, .t-code { fill: #e3e8ee; }
  .t-petit, .t-sur { fill: #8a99a8; } .t-accent { fill: #4fb3a7; } .t-ambre { fill: #f2b544; }
  .badge { fill: #4fb3a7; } .t-badge { fill: #0b1015; } .sep { stroke: #22303c; }
}
"""

MARKERS = """
<marker id="m-trait" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="pointe" d="M0 0 L10 5 L0 10 z"/></marker>
<marker id="m-trajet" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="trajet-pointe" d="M0 0 L10 5 L0 10 z"/></marker>
<marker id="m-vitesse" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="vitesse-pointe" d="M0 0 L10 5 L0 10 z"/></marker>
<marker id="m-x" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path class="px" d="M0 0 L10 5 L0 10 z"/></marker>
<marker id="m-y" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path class="py" d="M0 0 L10 5 L0 10 z"/></marker>
"""


def esc(s):
    return html.escape(str(s), quote=True)


def svg(width, height, titre, description, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
            f'aria-labelledby="t d">\n<title id="t">{esc(titre)}</title>\n<desc id="d">{esc(description)}</desc>\n'
            f"<style>{CSS}</style>\n<defs>{MARKERS}</defs>\n{body}\n</svg>\n")


def text(x, y, s, cls="t", anchor="start"):
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{esc(s)}</text>'


def line(x1, y1, x2, y2, cls="trait", fin=None, debut=None):
    m = (f' marker-end="url(#m-{fin})"' if fin else "") + (f' marker-start="url(#m-{debut})"' if debut else "")
    return f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"{m}/>'


def path(d, cls="trait", fin=None):
    m = f' marker-end="url(#m-{fin})"' if fin else ""
    return f'<path class="{cls}" d="{d}"{m}/>'


def rect(x, y, w, h, cls="boite", rx=10):
    return f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"/>'


def arc(cx, cy, r, a0, a1, cls="trait", fin=None):
    """Arc de cercle en coordonnées écran, angles en degrés dans le sens trigonométrique (y vers le haut)."""
    p0 = (cx + r * math.cos(math.radians(a0)), cy - r * math.sin(math.radians(a0)))
    p1 = (cx + r * math.cos(math.radians(a1)), cy - r * math.sin(math.radians(a1)))
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 0 if a1 > a0 else 1
    return path(f"M{p0[0]:.1f} {p0[1]:.1f} A{r:.1f} {r:.1f} 0 {large} {sweep} {p1[0]:.1f} {p1[1]:.1f}", cls, fin)


def axes(x, y, theta_deg=0.0, longueur=40, nom="", nom_dx=8, nom_dy=18):
    """Repère 2D vu de dessus : x en rouge, y en vert (sens trigonométrique, y écran vers le bas)."""
    t = math.radians(theta_deg)
    xe = (x + longueur * math.cos(t), y - longueur * math.sin(t))
    ye = (x - longueur * math.sin(t), y - longueur * math.cos(t))
    out = [line(x, y, *xe, cls="ax-x", fin="x"), line(x, y, *ye, cls="ax-y", fin="y"),
           text(xe[0] + 6 * math.cos(t), xe[1] - 6 * math.sin(t) + 4, "x", "t-x", "middle"),
           text(ye[0] - 8 * math.sin(t), ye[1] - 8 * math.cos(t) + 4, "y", "t-y", "middle"),
           f'<circle class="roue" cx="{x:.1f}" cy="{y:.1f}" r="3.5"/>']
    if nom:
        out.append(text(x + nom_dx, y + nom_dy, nom, "t-code"))
    return "\n".join(out)


def robot(x, y, theta_deg=0.0, echelle=1.0, repere=False):
    """Robot différentiel vu de dessus, centré sur base_link (milieu de l'essieu), tourné de theta."""
    s = echelle
    parts = [
        f'<rect class="roue" x="{-16 * s:.1f}" y="{-31 * s:.1f}" width="{32 * s:.1f}" height="{9 * s:.1f}" rx="{3 * s:.1f}"/>',
        f'<rect class="roue" x="{-16 * s:.1f}" y="{22 * s:.1f}" width="{32 * s:.1f}" height="{9 * s:.1f}" rx="{3 * s:.1f}"/>',
        f'<rect class="robot" x="{-26 * s:.1f}" y="{-22 * s:.1f}" width="{66 * s:.1f}" height="{44 * s:.1f}" rx="{10 * s:.1f}"/>',
        f'<circle class="roulette" cx="{-17 * s:.1f}" cy="0" r="{4.5 * s:.1f}"/>',
        f'<path class="nez" d="M{30 * s:.1f} 0 l{-9 * s:.1f} {-6 * s:.1f} v{12 * s:.1f} z"/>',
    ]
    g = f'<g transform="translate({x:.1f} {y:.1f}) rotate({-theta_deg:.1f})">' + "".join(parts) + "</g>"
    return g + ("\n" + axes(x, y, theta_deg, 34 * s) if repere else "")

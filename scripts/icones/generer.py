#!/usr/bin/env python3
"""Icônes du site (favicon, écran d'accueil du téléphone) depuis le symbole Umoja Roboti.

    python3 scripts/icones/generer.py && node scripts/icones/rendre.cjs

Écrit, dans contenus/academy_content/static/icones/ :
- favicon.svg : version simplifiée pour l'onglet (16-32 px) : les trois arcs plus épais, sans les petits
  anneaux ni les points, qui disparaissent à cette taille ; sur une tuile crème, lisible sur un onglet
  clair comme sombre ;
- icone-complete.svg et icone-carree.svg (intermédiaires, non servis) : le symbole complet sur la tuile,
  à bords arrondis (Android) ou carrée (iOS arrondit lui-même) ;
rendre.cjs en tire les PNG et favicon.ico.
"""
import re
from pathlib import Path

ICI = Path(__file__).parent
SORTIE = ICI.parent.parent / "contenus" / "academy_content" / "static" / "icones"
CREME = "#F6F1E7"
TUILE = '<rect x="-6" y="-6" width="412" height="412"{rx} fill="' + CREME + '"/>'
# le symbole d'origine (400×400) a des marges : recentré et agrandi dans la tuile
CADRE = "translate(200 200) scale({s}) translate(-184 -190)"

svg = (ICI / "umoja-roboti.svg").read_text()
corps = svg.split("<g>", 1)[1].rsplit("</g>", 1)[0]
arcs = re.findall(r'<path d="([^"]+)"[^>]*stroke="(#[0-9A-F]+)"', svg)


def simplifie(d, pas=6):
    pts = re.findall(r"([\d.]+),([\d.]+)", d)
    pts = pts[::pas] + ([pts[-1]] if (len(pts) - 1) % pas else [])
    return "M" + " L".join(f"{float(x):.1f},{float(y):.1f}" for x, y in pts)


def icone(contenu, s, rx=' rx="92"'):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-6 -6 412 412">{TUILE.format(rx=rx)}'
            f'<g transform="{CADRE.format(s=s)}">{contenu}</g></svg>')


simple = "".join(f'<path d="{simplifie(d)}" fill="none" stroke="{c}" stroke-width="44" stroke-linecap="round" '
                 'stroke-linejoin="round"/>' for d, c in arcs)
simple += '<circle cx="200" cy="200" r="30" fill="none" stroke="#1B1F3B" stroke-width="34"/>'
SORTIE.mkdir(parents=True, exist_ok=True)
(SORTIE / "favicon.svg").write_text(icone(simple, 0.88))
(ICI / "icone-complete.svg").write_text(icone(corps, 0.86))
(ICI / "icone-carree.svg").write_text(icone(corps, 0.86, rx=""))
print("favicon.svg, icone-complete.svg, icone-carree.svg")

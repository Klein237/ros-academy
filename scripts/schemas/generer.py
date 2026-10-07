#!/usr/bin/env python3
"""Génère les schémas des cours dans content/modules/<id>/images/.

    python3 scripts/schemas/generer.py              # écrit les SVG
    python3 scripts/schemas/generer.py --verifier   # échoue si un SVG n'est pas à jour (CI)

Chaque fichier de ce dossier décrit les schémas d'un module, avec le style commun (style.py).
"""

import sys
from pathlib import Path

import bonus
import robot_mobile
import ros2

CONTENT = Path(__file__).resolve().parents[2] / "content" / "modules"
SOURCES = [robot_mobile, ros2, bonus]


def main():
    verifier = "--verifier" in sys.argv
    perimes = []
    for source in SOURCES:
        for rel, fn in source.SCHEMAS.items():
            target = CONTENT / rel
            contenu = fn()
            if target.is_file() and target.read_text(encoding="utf-8") == contenu:
                continue
            if verifier:
                perimes.append(rel)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contenu, encoding="utf-8")
                print(f"écrit : {rel}")
    if perimes:
        print("Schémas à regénérer (python3 scripts/schemas/generer.py) :\n  " + "\n  ".join(perimes))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

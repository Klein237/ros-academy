"""PNG rendus par rendre.mjs → WebP 400×400 recadrés, prêts pour le site (Pillow requis).

    python3 scripts/icones-3d/webp.py <dossier des PNG> contenus/academy_content/static/icones
"""

import sys
from pathlib import Path

from PIL import Image


def main(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for png in sorted(source.glob("*.png")):
        image = Image.open(png).convert("RGBA")
        image = image.crop(image.getbbox())
        cote = max(image.size) + 40  # une petite marge autour de l'objet
        carre = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
        carre.paste(image, ((cote - image.width) // 2, (cote - image.height) // 2))
        sortie = destination / f"{png.stem}.webp"
        carre.resize((400, 400), Image.LANCZOS).save(sortie, "WEBP", quality=86, method=6)
        print(sortie, sortie.stat().st_size, "octets")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))

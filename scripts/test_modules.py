#!/usr/bin/env python3
"""Valide le dépôt de contenu et teste les modules dans l'image ros-lab.

    python scripts/test_modules.py                 # tous les modules de content/
    python scripts/test_modules.py 05-noeud        # un module
    ROS_LAB_IMAGE=ros-lab:0.1.0 CONTENT_DIR=content python scripts/test_modules.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "contenus"))

from academy_content.model import list_module_ids, validate_tree  # noqa: E402
from academy_content.testing import run_module_tests  # noqa: E402


def main(argv):
    root = Path(os.environ.get("CONTENT_DIR", Path(__file__).resolve().parents[1] / "content"))
    image = os.environ.get("ROS_LAB_IMAGE", "ros-lab:0.1.0")
    erreurs = validate_tree(root)
    if erreurs:
        print("Format invalide :")
        for e in erreurs:
            print(f"  ✘ {e}")
        return 1
    print("✔ format du contenu valide")
    modules = argv or list_module_ids(root)
    failed = []
    for module_id in modules:
        print(f"\n=== {module_id}", flush=True)
        rapport = run_module_tests(root / "modules" / module_id, image=image)
        print(rapport.resume(), flush=True)
        if not rapport.ok:
            failed.append(module_id)
            print("--- journal ---")
            print(rapport.journal[-6000:])
    if failed:
        print(f"\n✘ modules en échec : {', '.join(failed)}")
        return 1
    print(f"\n✔ {len(modules)} module(s) testé(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

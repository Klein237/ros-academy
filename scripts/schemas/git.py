"""Schémas du module Git : les trois zones, l'historique, une branche de correction, le travail en équipe."""

from style import line, path, rect, svg, text

GIT = "15-git"


def zones():
    b = []
    w = 230
    colonnes = [(20, "DOSSIER DE TRAVAIL", "vos fichiers, tels quels", "boite",
                 ["talker.py  modifié", "setup.py", "README.md"]),
                (350, "INDEX", "le prochain commit", "capteur", ["talker.py"]),
                (680, "DÉPÔT", "l'historique (.git)", "calcul", ["a1f3  Ajoute talker", "7c2e  Publie à 2 Hz",
                                                                   "e90b  Corrige le topic"])]
    for x, titre, sous, cls, lignes in colonnes:
        b += [rect(x, 20, w, 240, "fond", 12), text(x + w / 2, 48, titre, "t-sur", "middle"),
              text(x + w / 2, 68, sous, "t-petit", "middle")]
        for i, l in enumerate(lignes):
            b += [rect(x + 16, 86 + i * 46, w - 32, 36, cls, 6), text(x + 30, 109 + i * 46, l, "t-code")]
    for x0, nom in ((20 + w, "git add"), (350 + w, "git commit")):
        b += [line(x0 + 8, 150, x0 + 92, 150, fin="trait"), text(x0 + 50, 136, nom, "t-code", "middle")]
    b += [path("M795 262 C 795 318, 135 318, 135 264", "tirets", fin="trait"),
          text(465, 338, "git restore, git switch : revenir à une version enregistrée", "t-petit", "middle")]
    return svg(930, 352, "Les trois zones de Git",
               "Le dossier de travail contient vos fichiers tels quels, dont talker.py modifié. git add place talker.py dans "
               "l'index, qui prépare le prochain commit. git commit enregistre l'index dans le dépôt, l'historique rangé dans "
               "le dossier .git : chaque commit a un identifiant court et un message. git restore et git switch font revenir "
               "le dossier de travail à une version enregistrée.", "\n".join(b))


def commit(x, y, ident, cls="calcul"):
    return [f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="16"/>', text(x, y + 4, ident, "t-commit", "middle")]


def etiquette(x, y, nom, cls="t-accent"):
    w = 10 + 8 * len(nom)
    return [rect(x - w / 2, y - 14, w, 22, "boite", 11), text(x, y + 2, nom, cls, "middle")]


def historique():
    b = [rect(20, 20, 880, 300, "fond", 12), text(40, 48, "HISTORIQUE DE main", "t-sur")]
    commits = [("a1f3", "Ajoute le nœud talker"), ("7c2e", "Publie toutes les 0,5 s"),
               ("b4d9", "Renomme le topic"), ("e90b", "Ajoute un compteur")]
    xs = [120 + i * 210 for i in range(len(commits))]
    for i, (ident, msg) in enumerate(commits):
        if i:
            b.append(line(xs[i - 1] + 16, 150, xs[i] - 16, 150, "trait"))
        cls = "capteur" if ident == "b4d9" else "calcul"
        b += commit(xs[i], 150, ident, cls)
        b += [text(xs[i], 196, msg, "t-petit", "middle")]
    b += etiquette(xs[-1], 104, "main") + etiquette(xs[-1], 76, "HEAD", "t-ambre")
    b += [line(xs[-1], 88, xs[-1], 92, "trait"), line(xs[-1], 116, xs[-1], 132, "trait", fin="trait"),
          text(xs[2], 230, "le commit qui a cassé le robot", "t-ambre", "middle"),
          text(xs[2], 250, "git log, git show b4d9", "t-code", "middle"),
          text(460, 296, "chaque commit pointe vers le précédent : l'historique ne se perd pas", "t-petit", "middle")]
    return svg(920, 340, "L'historique : une chaîne de commits",
               "L'historique de la branche main est une chaîne de quatre commits, du plus ancien au plus récent : a1f3 "
               "Ajoute le nœud talker, 7c2e Publie toutes les 0,5 s, b4d9 Renomme le topic, e90b Ajoute un compteur. "
               "Les étiquettes main et HEAD désignent le dernier commit. Le commit b4d9, mis en évidence, est celui qui a "
               "cassé le robot : git log et git show b4d9 permettent de le retrouver et de le lire.", "\n".join(b))


def branches():
    b = [rect(20, 20, 880, 300, "fond", 12), text(40, 48, "UNE BRANCHE POUR LA CORRECTION", "t-sur")]
    y_main, y_br = 120, 230
    xs = [100, 260, 420]
    for i, x in enumerate(xs):
        if i:
            b.append(line(xs[i - 1] + 16, y_main, x - 16, y_main))
        b += commit(x, y_main, ["a1f3", "b4d9", "e90b"][i], "capteur" if i == 1 else "calcul")
    # branche correction
    b += [path(f"M{xs[-1] + 12} {y_main + 12} C {xs[-1] + 60} {y_br}, {xs[-1] + 90} {y_br}, 574 {y_br}", "trait")]
    b += commit(590, y_br, "c5a0", "calcul")
    b += [text(590, y_br + 40, "Rétablit le topic /bavardage", "t-petit", "middle")]
    b += etiquette(590, y_br - 34, "correction")
    # fusion
    b += [line(xs[-1] + 16, y_main, 734, y_main, "tirets"),
          path(f"M606 {y_br - 6} C 680 {y_br - 20}, 700 {y_main + 30}, 736 {y_main + 12}", "trait")]
    b += commit(750, y_main, "f81e", "calcul")
    b += etiquette(750, y_main - 36, "main") + [text(776, y_main + 5, "fusion (merge)", "t-petit")]
    b += [text(260, y_main - 30, "main reste utilisable pendant la correction", "t-petit", "middle"),
          text(460, 296, "git switch -c correction  →  git commit  →  git switch main  →  git merge correction",
               "t-code", "middle")]
    return svg(920, 340, "Corriger sur une branche, puis fusionner",
               "Depuis le dernier commit de main, on crée la branche correction. Le commit c5a0, Rétablit le topic /bavardage, "
               "y est enregistré sans toucher main, qui reste utilisable. Une fois la correction vérifiée, on revient sur main "
               "et on fusionne la branche correction : le commit de fusion f81e réunit les deux lignes. Commandes : "
               "git switch -c correction, git commit, git switch main, git merge correction.", "\n".join(b))


def equipe():
    b = []
    postes = [(20, "VOTRE POSTE", "dépôt local"), (640, "COLLÈGUE", "dépôt local")]
    for x, titre, sous in postes:
        b += [rect(x, 150, 260, 150, "fond", 12), text(x + 130, 178, titre, "t-sur", "middle"),
              text(x + 130, 198, sous, "t-petit", "middle"),
              rect(x + 30, 216, 200, 60, "calcul", 8), text(x + 130, 244, "branche", "t-gras", "middle"),
              text(x + 130, 264, "nouveau-capteur" if x == 20 else "main", "t-code", "middle")]
    b += [rect(300, 20, 320, 170, "fond", 12), text(460, 48, "DÉPÔT DISTANT", "t-sur", "middle"),
          text(460, 68, "GitHub, GitLab…", "t-petit", "middle"),
          rect(330, 86, 260, 84, "capteur", 8), text(460, 112, "pull request", "t-gras", "middle"),
          text(460, 134, "relecture du code", "t-petit", "middle"), text(460, 154, "tests automatiques (CI)", "t-petit", "middle"),
          path("M282 214 C 300 190, 300 160, 328 140", "trait", fin="trait"), text(250, 132, "git push", "t-code", "middle"),
          path("M592 140 C 620 160, 620 190, 638 214", "trait", fin="trait"), text(672, 132, "git pull", "t-code", "middle"),
          text(460, 236, "la branche n'entre dans main", "t-petit", "middle"),
          text(460, 256, "qu'après relecture et tests", "t-petit", "middle")]
    return svg(920, 320, "Travailler à plusieurs : push, pull request, pull",
               "Votre poste et celui d'une collègue ont chacun leur dépôt local. Vous envoyez votre branche nouveau-capteur "
               "sur le dépôt distant (GitHub, GitLab) avec git push et ouvrez une pull request : le code est relu et les tests "
               "automatiques tournent. La branche n'entre dans main qu'après relecture et tests ; la collègue récupère main "
               "avec git pull.", "\n".join(b))


SCHEMAS = {
    f"{GIT}/images/zones.svg": zones,
    f"{GIT}/images/historique.svg": historique,
    f"{GIT}/images/branches.svg": branches,
    f"{GIT}/images/equipe.svg": equipe,
}

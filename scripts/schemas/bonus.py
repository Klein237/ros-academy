"""Schémas des modules bonus « La qualité de service » et « Les outils de débogage »."""

from style import line, rect, svg, text

QOS = "12-qos"
DEBUG = "13-debogage"


def boite(x, y, w, nom, qos, cls="calcul"):
    return [rect(x, y, w, 56, cls, 10), text(x + w / 2, y + 24, nom, "t-gras", "middle"),
            text(x + w / 2, y + 44, qos, "t-code", "middle")]


def croix(x, y):
    return [line(x - 9, y - 9, x + 9, y + 9, "ax-x"), line(x - 9, y + 9, x + 9, y - 9, "ax-x")]


def coche(x, y):
    return [f'<path class="ax-y" d="M{x - 10} {y} L{x - 3} {y + 8} L{x + 11} {y - 9}"/>']


def compatibilite():
    b = []
    panneaux = [(20, "FIABILITÉ", ("RELIABLE", "BEST_EFFORT")),
                (450, "DURABILITÉ", ("TRANSIENT_LOCAL", "VOLATILE"))]
    for x0, titre, (fort, faible) in panneaux:
        b += [rect(x0, 20, 410, 330, "fond", 12), text(x0 + 18, 48, titre, "t-sur"),
              text(x0 + 70, 76, "éditeur : offre", "t-petit", "middle"),
              text(x0 + 330, 76, "abonné : demande", "t-petit", "middle")]
        # ligne du haut : l'éditeur offre le plus, il convient aux deux abonnés
        b += boite(x0 + 10, 100, 130, "éditeur", fort)
        b += boite(x0 + 260, 90, 140, "abonné", fort)
        b += boite(x0 + 260, 160, 140, "abonné", faible)
        b += [line(x0 + 142, 128, x0 + 256, 118, fin="trait"), line(x0 + 142, 128, x0 + 256, 188, fin="trait")]
        b += coche(x0 + 205, 108) + coche(x0 + 205, 172)
        # ligne du bas : l'éditeur offre le moins, l'abonné exigeant ne reçoit rien
        b += [line(x0 + 18, 236, x0 + 392, 236, "sep")]
        b += boite(x0 + 10, 256, 130, "éditeur", faible)
        b += boite(x0 + 260, 256, 140, "abonné", fort)
        b += [line(x0 + 142, 284, x0 + 256, 284, "tirets")] + croix(x0 + 199, 284)
        b.append(text(x0 + 205, 336, "la demande dépasse l'offre : aucun message", "t-petit", "middle"))
    return svg(880, 370, "Offre et demande : la compatibilité des QoS",
               "Un éditeur RELIABLE convient à un abonné RELIABLE comme BEST_EFFORT ; un éditeur BEST_EFFORT ne "
               "convient pas à un abonné RELIABLE. De même, un éditeur TRANSIENT_LOCAL convient aux deux abonnés, "
               "un éditeur VOLATILE ne convient pas à un abonné TRANSIENT_LOCAL : aucun message ne passe.",
               "\n".join(b))


def durabilite():
    b = []
    lignes = [(70, "VOLATILE", "l'abonné ne reçoit que les messages suivants : ici, rien"),
              (220, "TRANSIENT_LOCAL", "l'éditeur garde la mission et la lui envoie à son arrivée")]
    for y, titre, note in lignes:
        b += [rect(20, y - 50, 820, 140, "fond", 12), text(38, y - 24, titre, "t-sur"),
              text(140, y + 12, "éditeur", "t-gras", "end"), text(140, y + 62, "abonné", "t-gras", "end"),
              line(160, y + 7, 800, y + 7, "trait", fin="trait"), line(160, y + 57, 800, y + 57, "tirets"),
              text(820, y + 12, "t", "t-math", "end")]
        # 9 h 00 : la mission est publiée une fois
        b += [f'<circle class="cir" cx="240" cy="{y + 7}" r="7"/>', text(240, y - 8, "mission publiée", "t-petit", "middle"),
              text(240, y + 30, "9 h 00", "t-petit", "middle")]
        # 9 h 05 : l'abonné démarre
        b += [rect(468, y + 45, 24, 24, "calcul", 5), text(480, y + 88, "9 h 05 : l'abonné démarre", "t-petit", "middle")]
        b.append(text(822, y - 24, note, "t-petit", "end"))
    b += [line(248, 233, 470, 271, "trait", fin="trait"), f'<circle class="cir" cx="512" cy="277" r="7"/>']
    b += croix(530, 127)
    return svg(860, 330, "La durabilité : recevoir un message publié avant son arrivée",
               "La mission est publiée une seule fois à 9 h 00 ; un abonné démarre à 9 h 05. En VOLATILE, il ne la "
               "reçoit jamais. En TRANSIENT_LOCAL, l'éditeur l'a gardée et la lui envoie dès son arrivée.",
               "\n".join(b))


def methode():
    etapes = [("1", "Le nœud tourne-t-il ?", "ros2 node list", "sinon : lancement, exécutable, plantage"),
              ("2", "Est-il relié aux autres ?", "ros2 node info · ros2 topic info -v", "noms, types et QoS des deux côtés"),
              ("3", "Les données circulent-elles ?", "ros2 topic echo · hz · ros2 param get", "valeurs plausibles, bonne fréquence"),
              ("4", "Que dit le nœud ?", "--ros-args --log-level nœud:=debug", "journaux, /rosout, ros2 bag pour rejouer")]
    b = []
    for i, (num, question, cmd, note) in enumerate(etapes):
        y = 20 + i * 86
        b += [rect(20, y, 820, 70, "boite", 12),
              f'<circle class="badge" cx="56" cy="{y + 35}" r="17"/>', text(56, y + 40, num, "t-badge", "middle"),
              text(90, y + 30, question, "t-gras"), text(90, y + 52, note, "t-petit"),
              text(820, y + 41, cmd, "t-code", "end")]
        if i < len(etapes) - 1:
            b.append(line(56, y + 54, 56, y + 100, "trait", fin="trait"))
    return svg(860, 370, "Diagnostiquer un robot : quatre questions dans l'ordre",
               "1. Le nœud tourne-t-il ? (ros2 node list) 2. Est-il relié aux autres ? (ros2 node info, ros2 topic "
               "info -v : noms, types, QoS) 3. Les données circulent-elles ? (ros2 topic echo, hz, ros2 param get) "
               "4. Que dit le nœud ? (journaux en niveau debug, /rosout, ros2 bag pour rejouer).", "\n".join(b))


SCHEMAS = {
    f"{QOS}/images/compatibilite.svg": compatibilite,
    f"{QOS}/images/durabilite.svg": durabilite,
    f"{DEBUG}/images/methode.svg": methode,
}

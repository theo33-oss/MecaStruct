"""Valeurs clés d'une ligne d'état, affichées en cartes sous le bouton « Calculer » (bureau et site).

« A = 1 u, B = 2 u (vérifié) — C = 3 u » donne trois cartes : A, B (avec le verdict) et C.
"""

import re

_MORCEAU = re.compile(r"^(?P<label>[^=:]{1,25}?) = (?P<value>[^()]+?)(?: \((?P<note>[^()]+)\))?$")
_COULEURS = {"vérifié": "green", "NON vérifié": "red"}


def valeurs(status: str) -> list[dict]:
    """Cartes {label, value, delta, delta_color} tirées d'une ligne d'état ; rien sans « x = y »."""
    cartes = []
    for morceau in re.split(r",\s|\s—\s|\s;\s", str(status)):
        m = _MORCEAU.match(morceau.strip())
        if m is None:
            continue
        valeur, _, verdict = m["value"].partition(" : ")
        note = (m["note"] or verdict).strip()
        carte = {"label": m["label"].strip(), "value": valeur.strip()}
        if note:
            carte["delta"] = note
            carte["delta_color"] = _COULEURS.get(note, "off")
        cartes.append(carte)
    return cartes

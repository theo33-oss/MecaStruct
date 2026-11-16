"""Boutons « Bloc-notes (.txt) » et « Excel de validation » des pages de bureau.

Ce sont les fichiers du site : le calcul passe par le pont (pont/exports.py), avec la base de matériaux de l'application
(matériaux ajoutés par l'utilisateur compris). Un seul code fabrique donc les deux versions.
"""

import base64
import copy
import json
import re

from mecastruct.bureau import state
from mecastruct.bureau.widgets import Zone
from mecastruct.core.errors import MecaStructError
from mecastruct.services import project_io

TAB_IDENT = {"Beam": "beam", "Tr": "truss", "Sec": "sec", "Tra": "tra", "Cis": "cis", "Tor": "tor", "Fle": "fle",
             "Fla": "fla", "Ten": "ten", "Hoo": "hoo", "Jau": "jau"}  # fmt: skip


def appel(calcul: str, saisie: dict) -> dict:
    """Sortie du calcul `calcul` du pont pour `saisie` ; erreur lisible (MecaStructError) si le calcul échoue."""
    from mecastruct.pont import noyau

    noyau.utiliser(state.dm())
    r = json.loads(noyau.appeler(calcul, project_io._json(copy.deepcopy(saisie))))
    if not r["ok"]:
        raise MecaStructError("MecaStruct:App:export", r["erreur"])
    return r["sortie"]


def nom_de_fichier(titre: str, fin: str) -> str:
    return "MecaStruct_" + re.sub(r"[^\w]+", "_", titre).strip("_") + fin


def boutons(z: Zone, ident: str, saisie: dict, titre: str) -> None:
    """Deux boutons d'enregistrement pour le calcul `ident` du pont avec la saisie actuelle de la page."""
    z.telecharger(
        "Bloc-notes (.txt)",
        lambda: appel(f"{ident}.texte", saisie)["texte"],
        nom_de_fichier(titre, "_note.txt"),
        aide="Données, modes de ruine, résultats et démarche dans un fichier texte lisible partout.",
    )
    z.telecharger(
        "Excel de validation",
        lambda: base64.b64decode(appel(f"{ident}.validation", saisie)["base64"]),
        nom_de_fichier(titre, "_validation.xlsx"),
        aide="Classeur où le calcul est refait par des formules Excel à côté de MecaStruct, avec les coefficients de "
        "sécurité. Pour les poutres, treillis et ossatures, le solveur n'est pas refait : seuls les critères sont en formules.",
    )

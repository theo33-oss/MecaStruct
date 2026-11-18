"""Boutons « Bloc-notes (.txt) », « Excel de validation » et « Demander à une IA » des pages de bureau.

Ce sont les fichiers du site : le calcul passe par le pont (pont/exports.py), avec la base de matériaux de l'application
(matériaux ajoutés par l'utilisateur compris). Un seul code fabrique donc les deux versions.
"""

import base64
import copy
import json
import re

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QPushButton

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


IA = (("Ouvrir Claude", "https://claude.ai/new"), ("Ouvrir ChatGPT", "https://chatgpt.com/"))  # mêmes que le site


def demander_a_une_ia(bouton: QPushButton, ident: str, saisie: dict) -> None:
    """Copie l'étude (consigne + note de calcul) puis propose d'ouvrir une IA où la coller (Ctrl+V)."""
    try:
        texte = appel(f"{ident}.ia", {**saisie, "_securite": state.lire("securite", "coef")})["texte"]
    except MecaStructError as e:
        QMessageBox.warning(bouton, "Export impossible", str(getattr(e, "message", e)))
        return
    QApplication.clipboard().setText(texte)
    menu = QMenu(bouton)
    menu.setToolTipsVisible(True)
    menu.addAction("Étude copiée : collez-la (Ctrl+V) dans l'IA").setEnabled(False)
    for nom, adresse in IA:
        menu.addAction(nom, lambda a=adresse: QDesktopServices.openUrl(QUrl(a)))
    montrer_menu(menu, bouton.mapToGlobal(bouton.rect().bottomLeft()))


def montrer_menu(menu: QMenu, position) -> None:
    """Affiche le menu (à part : les tests le remplacent, l'affichage réel attend un clic)."""
    menu.exec(position)


def boutons(z: Zone, ident: str, saisie: dict, titre: str) -> None:
    """Trois boutons pour le calcul `ident` du pont avec la saisie actuelle de la page : deux fichiers et l'IA."""
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
    bouton = z.bouton(
        "Demander à une IA",
        lambda: demander_a_une_ia(bouton, ident, saisie),
        aide="Copie l'étude (données, résultats, démarche) avec une consigne : l'IA présente le problème, puis vous lui "
        "posez vos questions. Rien n'est envoyé : vous collez le texte dans Claude ou ChatGPT.",
    )

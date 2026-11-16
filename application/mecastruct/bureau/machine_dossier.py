"""Bouton « Dossier de validation de cette page » des pages de cours « Éléments de machines ».

Chaque calcul de la page garde son résultat sous « <clé>.res » = {res, empreinte de la saisie} (machine_page.calcul).
Le dossier réunit les calculs dont le résultat est à jour, sans les recalculer (services/machine_validation.py).
"""

from datetime import datetime

from mecastruct.bureau import dossier, state, tache
from mecastruct.bureau.widgets import Zone
from mecastruct.services import machine_validation


def _etat(calculs: list[tuple[str, str, dict, str]]) -> tuple[list[tuple], tuple]:
    """Calculs pour machine_validation.generate (résultat None s'il n'est pas à jour) et leurs empreintes."""
    liste, empreintes = [], []
    for cle, nom, defaut, typ in calculs:
        s = {k: state.v.get(f"{cle}.{k}", v) for k, v in defaut.items()}  # comme machine_page.saisie
        calc = state.v.get(f"{cle}.res")
        res = calc["res"] if calc is not None and calc["empreinte"] == repr(s) else None
        liste.append((nom, typ, s, res))
        empreintes.append(None if res is None else repr(s))
    return liste, tuple(empreintes)


def _genere(z: Zone, nom: str, titre: str, calculs: list[tuple[str, str, dict, str]]) -> None:
    """Écrit le dossier avec les résultats à jour et le garde sous « validation.<nom> »."""
    liste, empreintes = _etat(calculs)
    dm = state.dm()

    def fin(html: str) -> None:
        state.v.pop(f"validation.{nom}.erreur", None)
        heure = datetime.now().strftime("%H:%M:%S")
        state.v[f"validation.{nom}"] = (machine_validation.fileName(titre), html, heure, empreintes)
        z.section_.rafraichir()

    def echec(err: Exception) -> None:
        state.v[f"validation.{nom}.erreur"] = err
        state.v.pop(f"validation.{nom}", None)
        z.section_.rafraichir()

    tache.lancer(lambda: machine_validation.generate(titre, liste, dm), fin, echec)


def bouton(z: Zone, nom: str, titre: str, calculs: list[tuple[str, str, dict, str]]) -> None:
    """« Dossier de validation de cette page », puis l'enregistrement du fichier tant que la saisie n'a pas changé.

    Entrées : nom (clé du dossier), titre (de la page), calculs = [(clé du calcul, titre du calcul, saisie par défaut,
    type de machine_validation.TYPES)]. Actif si au moins un calcul a un résultat à jour.
    """
    liste, empreintes = _etat(calculs)
    absents = [n for n, _, _, res in liste if res is None]
    z.bouton(
        "Dossier de validation de cette page",
        lambda: _genere(z, nom, titre, calculs),
        actif=len(absents) < len(liste),
        aide="Cliquez d'abord sur « Calculer » dans au moins un onglet." if len(absents) == len(liste) else None,
    )
    if absents and len(absents) < len(liste):
        z.legende(f"Non inclus dans le dossier (pas de résultat à jour) : {', '.join(absents)}.")
    err = state.v.get(f"validation.{nom}.erreur")
    if err is not None:
        z.erreurCalcul(err)
    doss = state.v.get(f"validation.{nom}")
    if doss is not None and doss[3] != empreintes:  # le dossier ne correspond plus à la page
        doss = None
    dossier.dossier_download(z, f"validation.{nom}", doss)

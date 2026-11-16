"""État de la fenêtre : DataManager, saisie par onglet et résultats, partagés par toutes les pages.

`v` garde aussi les valeurs des champs libres (clés texte) ; une clé (onglet, champ) désigne saisie[onglet][champ].
"""

import copy
import pickle
from collections.abc import Callable
from typing import Any

from mecastruct.core.data_manager import DataManager
from mecastruct.services.examples import loadExample
from mecastruct.services.project_io import PROJECT_KEYS as ONGLETS

v: dict[str, Any] = {}
extra: dict[str, dict] = {}  # saisies hors projet (ossature 3D), servies par saisie() comme les autres
abonnes: dict[str, list[Callable[[], None]]] = {}  # onglet → fonctions qui redessinent la saisie de sa page


def init() -> None:
    """Crée dm, saisie (exemple d'école de chaque onglet, comme au démarrage de MATLAB) et res, s'ils sont absents."""
    if "dm" not in v:
        v["dm"] = DataManager()
    if "saisie" not in v:
        v["saisie"] = {tab: loadExample(tab) for tab in ONGLETS}
    v.setdefault("res", {})


def dm() -> DataManager:
    """Base de matériaux et de profilés."""
    init()
    return v["dm"]


def saisie(tab: str) -> dict:
    """Saisie courante de l'onglet `tab` (dict, unités d'affichage de MATLAB)."""
    init()
    return extra[tab] if tab in extra else v["saisie"][tab]


def remplacer_saisie(tab: str, nouvelle: dict) -> None:
    """Remplace la saisie de l'onglet et redessine sa page (les champs repartent de la nouvelle saisie)."""
    init()
    v["saisie"][tab] = nouvelle
    reset_widgets(tab)


def lire(cle: Any, defaut: Any = None) -> Any:
    """Valeur d'un champ : (onglet, champ) → saisie ; texte → dictionnaire libre."""
    if isinstance(cle, tuple):
        return saisie(cle[0]).get(cle[1], defaut)
    return v.get(cle, defaut)


def ecrire(cle: Any, valeur: Any) -> None:
    """Écrit la valeur d'un champ (voir lire)."""
    if isinstance(cle, tuple):
        saisie(cle[0])[cle[1]] = valeur
    else:
        v[cle] = valeur


def set_result(tab: str, res: Any, source: str | None = None) -> None:
    """Enregistre le dernier résultat `tab` et la saisie qui l'a donné (voir is_current).

    `source` : onglet dont la saisie a servi, si ce n'est pas `tab` (résultats annexes : « BeamEC3 » vient de « Beam »).
    """
    init()
    v["res"][tab] = res
    v.pop(f"validation.{tab}", None)  # un dossier généré pour l'ancien résultat n'est plus à jour
    v[f"saisie_calculee_{tab}"] = repr(v["saisie"].get(source or tab))


def is_current(tab: str, source: str | None = None) -> bool:
    """Vrai si le résultat `tab` a été calculé avec la saisie actuelle de `source` (par défaut `tab`)."""
    init()
    return result(tab) is not None and v.get(f"saisie_calculee_{tab}") == repr(v["saisie"].get(source or tab))


def result(tab: str) -> Any:
    """Dernier résultat de l'onglet `tab`, ou None s'il n'a pas encore été calculé."""
    init()
    return v["res"].get(tab)


def effacer_resultat(tab: str) -> None:
    """Oublie le résultat de l'onglet `tab`."""
    init()
    v["res"].pop(tab, None)


def reset_widgets(tab: str) -> None:
    """Redessine la saisie de la page de l'onglet `tab` (à appeler après un changement de la saisie par programme)."""
    for f in abonnes.get(tab, []):
        f()


def abonner(tab: str, fonction: Callable[[], None]) -> None:
    """Enregistre la fonction qui redessine la saisie de la page de `tab`."""
    abonnes.setdefault(tab, []).append(fonction)


HISTORIQUE_MAX = 10


def push_beam_history() -> None:
    """Empile la saisie Poutres courante (état de départ, après un calcul ou un exemple) ; ignore un état identique."""
    h = v.setdefault("beam_history", [])
    pos = v.get("beam_history_pos", -1)
    snap = copy.deepcopy(saisie("Beam"))
    if 0 <= pos < len(h) and pickle.dumps(h[pos]) == pickle.dumps(snap):
        return
    del h[pos + 1 :]  # un nouvel état efface ce qui pouvait être rétabli
    h.append(snap)
    del h[:-HISTORIQUE_MAX]
    v["beam_history_pos"] = len(h) - 1


def move_beam_history(step: int) -> str:
    """Annule (step = -1) ou rétablit (step = +1) la saisie Poutres ; renvoie le message d'état."""
    h = v.get("beam_history", [])
    cible = v.get("beam_history_pos", -1) + step
    if not 0 <= cible < len(h):
        return "Rien à annuler." if step < 0 else "Rien à rétablir."
    remplacer_saisie("Beam", copy.deepcopy(h[cible]))
    v["beam_history_pos"] = cible
    verbe = "annulée" if step < 0 else "rétablie"
    return f"Modification {verbe}. Cliquez sur « Calculer » pour mettre à jour les résultats."

"""Socle du pont : conversion en JSON, registre des calculs, appel avec capture des erreurs.

Chaque famille de pages (machines.py, structures.py…) déclare ses calculs avec @calcul("id"). Un calcul reçoit la
saisie (dict) et rend la sortie d'un service : {result, tables, status, ok}, plus des figures Plotly éventuelles.
appeler() renvoie toujours un texte JSON : {"ok": true, "sortie": …} ou {"ok": false, "erreur": "…"}.
"""

import importlib
import json
import math
from collections.abc import Callable
from typing import Any

import numpy as np

FAMILLES = ("machines", "outils", "base")  # modules du pont chargés au premier appel (numpy, pandas, plotly suffisent)
FAMILLES_LOURDES = ("structures",)  # chargées par charger() : la page a d'abord chargé scipy et shapely
_REGISTRE: dict[str, Callable[[dict], Any]] = {}
_SOURCES: list[Callable[[], dict]] = []  # fonctions qui décrivent les formulaires d'une famille
_formulaires: dict = {}
_dm = None


def invalider_formulaires() -> None:
    """Les formulaires reprennent la base de matériaux au prochain besoin (après un ajout de l'utilisateur)."""
    _formulaires.clear()


def formulaires_de(source: Callable[[], dict]) -> None:
    """Déclare la fonction qui décrit les formulaires d'une famille (appelée une fois, au premier besoin)."""
    _SOURCES.append(source)


def calcul(ident: str) -> Callable:
    """Déclare un calcul appelable depuis la page sous le nom `ident`."""

    def enregistrer(f: Callable[[dict], Any]) -> Callable[[dict], Any]:
        _REGISTRE[ident] = f
        return f

    return enregistrer


def dm():
    """Base de matériaux et de profilés, créée une seule fois (elle sert à presque tous les calculs)."""
    global _dm
    if _dm is None:
        from mecastruct.core.data_manager import DataManager

        _dm = DataManager()
    return _dm


def _charger() -> None:
    for nom in FAMILLES:
        importlib.import_module(f"mecastruct.pont.{nom}")

    @calcul("formulaires")
    def formulaires(_s: dict) -> dict:
        """Tous les formulaires, par identifiant de calcul (décrits une seule fois)."""
        if not _formulaires:
            for source in _SOURCES:
                _formulaires.update(source())
        return _formulaires


def nombreFr(x: float, chiffres: int = 5) -> str:
    """Nombre lisible à la française : « 1 234,5 », « 0,0012 », « 1,2e-07 » ; NaN et infini en toutes lettres."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    if math.isinf(x):
        return "∞" if x > 0 else "−∞"
    if x == int(x) and abs(x) < 1e12:
        t = f"{int(x):,}".replace(",", " ")
    else:
        t = format(float(x), f".{chiffres}g")
        if "e" not in t and abs(x) >= 1000:
            entier, _, dec = t.partition(".")
            t = f"{int(entier):,}".replace(",", " ") + ("." + dec if dec else "")
    return t.replace(".", ",").replace("-", "−")


def _cellule(v: Any) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "oui" if v else "non"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return nombreFr(float(v))
    if v is None:
        return ""
    return str(v)


def tableJson(df) -> dict:
    """Tableau pandas → {entetes, lignes} de textes prêts à afficher (nombres à la française)."""
    lignes = [[_cellule(v) for v in ligne] for ligne in df.itertuples(index=False)]
    return {"entetes": [str(c) for c in df.columns], "lignes": lignes}


def versJson(o: Any) -> Any:
    """Objet Python du calcul → valeurs JSON : tableaux pandas, tableaux numpy, figures Plotly, NaN et infinis."""
    import pandas as pd

    if isinstance(o, pd.DataFrame):
        return tableJson(o)
    if hasattr(o, "to_plotly_json") and hasattr(o, "to_json"):  # figure Plotly
        return json.loads(o.to_json())  # {data, layout}
    if isinstance(o, dict):
        return {str(k): versJson(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [versJson(v) for v in o]
    if isinstance(o, np.ndarray):
        return versJson(o.tolist())
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, pd.Series):
        return versJson(o.tolist())
    if o is None or isinstance(o, (int, str)):
        return o
    return str(o)


def charger(famille: str) -> str:
    """Charge une famille lourde (ses bibliothèques doivent être là) ; les formulaires seront relus en entier."""
    if not _REGISTRE:
        _charger()
    importlib.import_module(f"mecastruct.pont.{famille}")
    _formulaires.clear()
    return "ok"


def appeler(ident: str, saisie_json: str = "{}") -> str:
    """Lance le calcul `ident` sur la saisie (texte JSON) ; rend un texte JSON, sans jamais lever d'exception."""
    if not _REGISTRE:
        _charger()
    if ident not in _REGISTRE:  # Python ordinaire (tests, bureau) : les familles lourdes se chargent d'elles-mêmes
        for famille in FAMILLES_LOURDES:
            try:
                charger(famille)
            except ImportError:
                pass
    try:
        f = _REGISTRE[ident]
    except KeyError:
        return json.dumps({"ok": False, "erreur": f"Calcul inconnu : {ident}"}, ensure_ascii=False)
    try:
        sortie = f(json.loads(saisie_json or "{}"))
        return json.dumps({"ok": True, "sortie": versJson(sortie)}, ensure_ascii=False, allow_nan=False)
    except Exception as err:  # noqa: BLE001 : toute erreur du calcul devient un message lisible sur la page
        message = getattr(err, "message", None) or str(err) or type(err).__name__
        return json.dumps({"ok": False, "erreur": message}, ensure_ascii=False)


def catalogue() -> str:
    """Liste des calculs disponibles (texte JSON), pour vérifier que la page et le pont sont d'accord."""
    if not _REGISTRE:
        _charger()
    return json.dumps(sorted(_REGISTRE), ensure_ascii=False)


def tous_formulaires() -> dict:
    """Tous les formulaires chargés, par identifiant de calcul (décrits une seule fois)."""
    if not _REGISTRE:
        _charger()
    return json.loads(appeler("formulaires"))["sortie"]

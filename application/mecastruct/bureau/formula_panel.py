"""Bloc « Formulaire rapide » : fiche de formules de la page (port de buildFormulaPanel)."""

from mecastruct.bureau.widgets import Zone
from mecastruct.core import data_manager
from mecastruct.core.utils import load_json
from mecastruct.services.fiches import LIBELLES as _LIBELLES  # libellés partagés avec le site


def _fiche(z: Zone, key: str) -> None:
    """Sélecteur de fiche et formules de la fiche choisie."""
    cles = data_manager.formulaKeys()
    choix = z.liste("Fiche", cles, f"formule.{key}", format=lambda k: _LIBELLES.get(k, k), defaut=key,
                    apres=z.section_.rafraichir)  # fmt: skip
    notes = load_json("formula_notes.json")["notes"]
    for fiche in data_manager.formulaSheet(choix):
        z.texte(f"**{fiche['title']}**")
        if fiche["title"] in notes:
            z.legende(str(notes[fiche["title"]]))
        z.formule(str(fiche["latex"]))
        if fiche.get("vars"):
            z.legende(str(fiche["vars"]))


def formula_panel(z: Zone, key: str | None) -> None:
    """Formules de la clé `key` dans un bloc repliable « Formulaire rapide » (rien si `key` vaut None)."""
    if key is not None:
        z.repliable("Formulaire rapide", rendu=lambda c: c.section(lambda s: _fiche(s, key)), cle=f"formulaire.{key}")

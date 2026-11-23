"""Exports communs à tous les calculs du pont : bloc-notes (.txt) et Excel de validation (.xlsx).

declarer("tra") ajoute les calculs « tra.texte » et « tra.validation ». Ils relancent le calcul « tra » du registre :
mêmes verdict, tableaux, démarche et critères que la page.
"""

import base64
import re

from mecastruct.pont import noyau
from mecastruct.pont.noyau import calcul, dm
from mecastruct.services import fiches


def _nom(titre: str, suffixe: str) -> str:
    return "MecaStruct_" + re.sub(r"[^\w]+", "_", titre).strip("_") + suffixe


def _calcul(ident: str, s: dict) -> tuple[dict, dict, dict]:
    """(formulaire, sortie du calcul, résultat brut du service) pour la saisie `s`."""
    formulaire = noyau.tous_formulaires()[ident]
    sortie = noyau._REGISTRE[ident](s)
    brut = sortie.get("_brut") or {}
    return formulaire, sortie, brut.get("result") or {}


DECLARES: set[str] = set()


def marquer(formulaires: dict) -> dict:
    """Complète les formulaires pour la page : exports disponibles, famille de chaque matériau ; rend le même dict."""
    base = dm()
    noms = base.listMaterials()
    familles = [str(base.getMaterial(n).get("Category") or "Autres") for n in noms]
    for ident, f in formulaires.items():
        f["exports"] = ident in DECLARES
        f["fiche"] = fiches.PAR_CALCUL.get(ident)  # fiche du « Formulaire rapide » proposée en tête de page
        for g in f.get("groupes", []):
            for c in g["champs"]:
                if c.get("type") == "liste" and c.get("options") == noms:
                    c["familles"] = familles  # la page range la liste des matériaux par famille
    return formulaires


def declarer(ident: str) -> None:
    DECLARES.add(ident)

    @calcul(f"{ident}.texte")
    def texte(s):
        """Note de calcul en texte brut (bloc-notes)."""
        from mecastruct.services import export_texte

        f, sortie, _ = _calcul(ident, s)
        return {"nom": _nom(f["titre"], "_note.txt"),
                "texte": export_texte.texte(f["titre"], f, s, sortie, sortie.get("criteres") or [], ident=ident)}  # fmt: skip

    @calcul(f"{ident}.ia")
    def ia(s):
        """Étude à coller dans une IA : consigne (présenter le problème, attendre les questions) + note de calcul."""
        from mecastruct.services import export_texte

        f, sortie, _ = _calcul(ident, s)
        note = export_texte.texte(f["titre"], f, s, sortie, sortie.get("criteres") or [], ident=ident)
        return {"texte": export_texte.invite_ia(f["titre"], note)}

    @calcul(f"{ident}.validation")
    def validation(s):
        """Classeur Excel où le calcul est refait par des formules (base64)."""
        from mecastruct.services import export_validation

        f, sortie, resultat = _calcul(ident, s)
        refait = export_validation.formules(ident, s, resultat, dm())
        donnees = export_validation.classeur(f["titre"], f, s, sortie, sortie.get("criteres") or [], refait)
        return {"nom": _nom(f["titre"], "_validation.xlsx"), "base64": base64.b64encode(donnees).decode("ascii")}

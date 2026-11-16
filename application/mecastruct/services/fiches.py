"""Fiches de formules (« Formulaire rapide ») : libellés, fiche proposée par calcul, contenu d'une fiche.

Source commune du bureau (bureau/formula_panel.py) et du site (calcul « fiche » du pont).
"""

from mecastruct.core import data_manager
from mecastruct.core.utils import load_json

LIBELLES = {
    "materiaux": "Matériaux",
    "geometrie": "Géométrie des sections",
    "equilibre": "Équilibre (PFS)",
    "cohesion": "Torseur de cohésion",
    "treillis": "Treillis",
    "traction": "Traction / compression",
    "cisaillement": "Cisaillement",
    "matage": "Matage",
    "torsion": "Torsion",
    "flexion": "Flexion",
    "deformee": "Déformée",
    "energie": "Énergie",
    "mohr_integrales": "Intégrales de Mohr",
    "flambage": "Flambage",
    "tenseurs": "Tenseurs",
    "mohr_cercle": "Cercle de Mohr",
    "criteres": "Critères",
    "hooke": "Loi de Hooke",
    "extensometrie": "Extensométrie",
}

# calcul du pont → fiche affichée par défaut (la même que « fiche = … » des pages du bureau) ; rien pour les machines
PAR_CALCUL = {"beam": "equilibre", "truss": "treillis", "sec": "geometrie", "tra": "traction", "cis": "cisaillement",
              "tor": "torsion", "fle": "flexion", "fla": "flambage", "ten": "tenseurs", "hoo": "hooke",
              "jau": "extensometrie"}  # fmt: skip


def fiche(cle: str | None = None) -> dict:
    """{cles: [{id, titre}], cle, fiches: [{titre, note, latex, vars}]} pour la fiche `cle` (la première par défaut)."""
    cles = list(data_manager.formulaKeys())
    cle = cle if cle in cles else cles[0]
    notes = load_json("formula_notes.json")["notes"]
    feuille = [
        {"titre": str(f["title"]), "note": str(notes.get(f["title"], "")), "latex": str(f["latex"]),
         "vars": str(f.get("vars") or "")}
        for f in data_manager.formulaSheet(cle)
    ]  # fmt: skip
    return {"cles": [{"id": k, "titre": LIBELLES.get(k, k)} for k in cles], "cle": cle, "fiches": feuille}

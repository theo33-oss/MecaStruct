"""Pont des pages « Données et aide » : convertisseur d'unités."""

import math

from mecastruct.core import units
from mecastruct.core.utils import load_json
from mecastruct.pont.noyau import calcul

UNITES_ATTENDUES = [
    ("Matériaux", "E, G", "GPa"),
    ("Matériaux", "Re, Rm, contraintes", "MPa"),
    ("Sections", "dimensions b, h, D, d, B, H, t, tw, tf", "mm"),
    ("Sections", "N, Ty ; Mfz, Mfy", "kN ; kN·m"),
    ("Poutres", "L, positions, a, b", "m"),
    ("Poutres", "S ; Iz, Iy, Ix ; vy, vz", "mm² ; mm⁴ ; mm"),
    ("Poutres", "forces ; couples ; charges réparties", "kN ; kN·m ; kN/m"),
    ("Treillis", "coordonnées ; S ; forces", "m ; mm² ; kN"),
    ("Traction", "N ; S0 ; L0 ; ΔT ; α", "kN ; mm² ; m ; °C ; 10⁻⁶/°C"),
    ("Cisaillement", "T, F ; S ; C ; D, a, b, L, d, e", "kN ; mm² ; kN·m ; mm"),
    ("Torsion", "Mt ; D, d ; L ; θ adm", "kN·m ; mm ; m ; °/m"),
    ("Flexion", "N ; Mfz, Mfy", "kN ; kN·m"),
    ("Flambage", "L ; S ; Iz, Iy ; P", "m ; mm² ; mm⁴ ; kN"),
    ("Tenseurs", "σij", "MPa"),
    ("Hooke", "σ ; ε, γ ; E", "MPa ; µdéf ; GPa"),
    ("Jauges", "ε ; R0 ; Vin ; Vout", "µdéf ; Ω ; V ; mV"),
    ("Résultats", "tous les rapports et graphes", "mm, kN, kN·m, MPa, mrad"),
]

EQUIVALENCES = [
    ("1 MPa", "= 1 N/mm² = 10⁶ Pa"),
    ("1 GPa", "= 1000 MPa (E acier = 210 GPa = 210 000 MPa)"),
    ("1 daN", "= 10 N"),
    ("1 kgf", "= 9,80665 N"),
    ("1 bar", "= 0,1 MPa"),
    ("1 ksi", "≈ 6,895 MPa"),
    ("1 psi", "≈ 6,895 kPa"),
    ("1 kN·m", "= 10⁶ N·mm"),
    ("1 in", "= 25,4 mm"),
    ("1 µdéf", "= 10⁻⁶ = 0,0001 %"),
    ("1 rad", "≈ 57,2958 °"),
]


def _tableau(lignes, entetes):
    return {"entetes": entetes, "lignes": [list(x) for x in lignes]}


@calcul("references")
def references(_s):
    """Normes citées par l'application (numéro, titre, année, rôle) : data/references.json, comme sur le bureau."""
    return load_json("references.json")


@calcul("glossaire")
def glossaire(_s):
    """Glossaire des symboles (symbole, LaTeX, nom, unité, pages du site, aide) : lu dans les formulaires et les fiches, comme sur le bureau.

    La page du site charge d'abord la famille « structures » : sans elle, les formulaires des poutres, sections… manquent."""
    from mecastruct.services import glossaire as g

    return {"entrees": [{k: v for k, v in e.items() if k != "source"} for e in g.entrees()]}


@calcul("fiche")
def fiche_de_formules(s):
    """« Formulaire rapide » : fiches de formules (clés, fiche choisie, formules LaTeX, variables, notes)."""
    from mecastruct.services import fiches

    return fiches.fiche(s.get("cle"))


@calcul("conv.catalogue")
def catalogue(_s):
    """Grandeurs et unités, avec les unités proposées par défaut, et les deux tableaux d'aide."""
    grandeurs = [
        {"nom": g["name"], "unites": [u["label"] for u in g["units"]], "de": g["defFrom"] - 1, "vers": g["defTo"] - 1}
        for g in units.unitCatalog()
    ]
    return {
        "grandeurs": grandeurs,
        "attendues": _tableau(UNITES_ATTENDUES, ["Où", "Champ", "Unité attendue"]),
        "equivalences": _tableau(EQUIVALENCES, ["Équivalence", "Valeur"]),
    }


@calcul("conv")
def convertir(s):
    """Valeur convertie de l'unité « de » vers « vers », et dans toutes les unités de la grandeur."""
    g = next(x for x in units.unitCatalog() if x["name"] == s["grandeur"])
    valeur = float(s["valeur"])
    if g["name"] == "Température absolue" and float(units.convertUnits(valeur, g["name"], s["de"], "K")) < -1e-9:
        raise ValueError("Cette température est sous le zéro absolu (0 K, soit −273,15 °C ou −459,67 °F) : elle n'existe pas.")
    resultat = float(units.convertUnits(valeur, g["name"], s["de"], s["vers"]))
    if not all(math.isfinite(float(units.convertUnits(valeur, g["name"], s["de"], u["label"]))) for u in g["units"]):
        raise ValueError("Valeur trop grande : un des résultats dépasse les nombres que le calcul sait écrire. Essayez une valeur plus petite.")
    def texte(x: float) -> str:
        return f"{float(x):.10g}".replace(".", ",")

    def affiche(x: float) -> str:
        """Même nombre avec l'espace fine des milliers (à partir de 5 chiffres) : « 1 000 000 » et non « 1000000 »."""
        t = texte(x)
        if "e" in t:
            return t
        entier, virgule, decimales = t.partition(",")
        signe, chiffres = ("-", entier[1:]) if entier.startswith("-") else ("", entier)
        if len(chiffres) >= 5:
            chiffres = f"{int(chiffres):,}".replace(",", "\u202f")
        return signe + chiffres + virgule + decimales

    lignes = [[u["label"], affiche(units.convertUnits(valeur, g["name"], s["de"], u["label"]))] for u in g["units"]]
    tableau = {"entetes": ["Unité", "Valeur équivalente"], "lignes": lignes}
    # texte : sans espace, pour « Copier la valeur » (collé dans Excel, il reste un nombre) ; affiche : pour l'écran
    return {"resultat": resultat, "texte": texte(resultat), "affiche": affiche(resultat), "tableau": tableau}

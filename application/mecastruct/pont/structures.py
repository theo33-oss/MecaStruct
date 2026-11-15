"""Pont des pages « Structures » et « Sections et contraintes » : formulaires, calculs, schémas, dossier de validation.

Ces calculs demandent scipy et shapely : la page web les charge avant le premier appel (noyau.charger). Le calcul,
les explications et le dossier passent par services.validation_report, comme dans l'application de bureau.
"""

import copy
import math
import re

import numpy as np

from mecastruct.core import geometry
from mecastruct.core.pp import asPP
from mecastruct.plots import beam_plots, other_plots
from mecastruct.pont.formulaire import case, col, groupe, liste, nb, tableau, texte
from mecastruct.pont.noyau import calcul, dm, formulaires_de
from mecastruct.services import beam_services, compute, validation_report
from mecastruct.services.examples import exampleNames, loadExample

TYPES_APPUI = ["appui_simple", "rotule", "pivot", "pivot_glissant", "encastrement"]
CAS = ["G", "Q", "W", "S"]
COMPOSANTES = ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]
FAMILLES_PROFILES = ["IPE", "HEA", "HEB", "IPN", "UPN", "UAP"]


# --------------------------------------------------------------------------------------------- outils communs


def _ok(status: str):
    """Verdict lu dans la ligne d'état du calcul : « NON vérifié » → False, « vérifié » → True, sinon None."""
    if re.search(r"NON vérifi", status):
        return False
    return True if re.search(r"vérifi", status) else None


def _figure(f):
    try:
        return f()
    except Exception:  # noqa: BLE001 : un dessin impossible n'empêche pas d'afficher le calcul
        return None


def _explications(tab: str, saisie: dict, calc: dict) -> list[dict]:
    """Équations appliquées aux données, chacune refaite à la main et comparée au solveur."""
    lignes = []
    for row in validation_report.explanationRows(tab, saisie, calc, dm()):
        if row["hand"] is None:
            lignes.append({"titre": row["label"]})
            continue
        ecart, ok = validation_report.explanationVerdict(row)
        note = (f"Concorde avec le solveur : {row['solver']:.6g} {row['unit']}" if ok
                else f"Écart avec le solveur : {ecart:.3g} {row['unit']} (solveur : {row['solver']:.6g})")  # fmt: skip
        lignes.append({"label": row["label"], "latex": row["latex"], "note": note, "ok": bool(ok)})
    return lignes


def _sortie(tab: str, saisie: dict, calc: dict, figures: list, metriques=None, rapport=None, latex=None) -> dict:
    status = str(calc.get("status", ""))
    return {
        "status": status,
        "ok": _ok(status),
        "metriques": metriques or [],
        "figures": [{"titre": t, "figure": f} for t, f in figures if f is not None],
        "tables": calc.get("tables", {}),
        "rapport": rapport if rapport is not None else list(calc.get("result", {}).get("rapport", []))[1:],
        "latex": latex if latex is not None else [],
        "explications": _figure(lambda: _explications(tab, saisie, calc)) or [],
        "blocs": [{"nom": n, "formules": f} for n, f in (_figure(lambda: validation_report.solverEquations(tab, calc)) or [])],
    }


def _enregistrer_communs(ident: str, tab: str) -> None:
    """Exemples et dossier de validation du calcul `ident` (onglet `tab` de l'application de bureau)."""

    @calcul(f"{ident}.exemple")
    def exemple(s):
        return loadExample(tab, s.get("nom"))

    @calcul(f"{ident}.dossier")
    def dossierValidation(s):
        calc = validation_report.recompute(tab, copy.deepcopy(s), dm(), None)
        return {"nom": validation_report.fileName(tab), "html": validation_report.generate(tab, s, calc, dm())}


@calcul("materiau")
def materiau(s):
    """Valeurs du matériau `nom` dans les unités d'affichage, pour les champs demandés (None si absente)."""
    valeurs = compute._materiau(dm(), s["nom"], list(s["champs"]))
    return {k: (None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)) for k, v in valeurs.items()}


@calcul("profils")
def profils(s):
    """Noms des profilés d'une famille."""
    return list(dm().Profiles[s["famille"]]["Name"])


# ----------------------------------------------------------------------------------------------------- poutres


@calcul("beam")
def poutre(s):
    calc = validation_report.recompute("Beam", s, dm(), None)
    sol, d = calc["sol"], calc["defl"]
    comps = [c for c in COMPOSANTES if any(np.any(k != 0) for k in asPP(sol[c]).coefs)] or ["Ty", "Mfz"]
    e, bd, sh = sol["extrema"], calc["check"]["bend"], calc["check"]["shear"]
    reaction = max((float(np.linalg.norm([r["Rx"], r["Ry"], r["Rz"]])) for r in sol["reactions"]), default=0.0)
    ok = bool(calc["check"]["ok"])
    metriques = [
        ["Réaction max", f"{reaction / 1e3:.4g} kN"],
        ["|T| max", f"{max(abs(e[c][b]) for c in ('Ty', 'Tz') for b in ('max', 'min')) / 1e3:.4g} kN"],
        ["|Mf| max", f"{max(abs(e[c][b]) for c in ('Mfy', 'Mfz') for b in ('max', 'min')) / 1e3:.4g} kN·m"],
        ["Flèche max", f"{d['integration']['fmax'] * 1e3:.4g} mm"],
        ["Kt·σ max", f"{bd['sigmaMaxKt'] / 1e6:.4g} MPa (σadm {bd['sigmaAdm'] / 1e6:.4g})"],
    ]
    if sh is not None:
        metriques.append(["VEd/Vpl,Rd", f"{sh['ratio']:.3g}"])
    figures = [
        ("Schéma", _figure(lambda: beam_plots.beamSchematic(calc["model"], sol))),
        ("Diagrammes", _figure(lambda: beam_plots.internalForces(sol, comps))),
        ("Déformée", _figure(lambda: beam_plots.deflection(calc["model"], d))),
    ]
    sortie = _sortie("Beam", s, calc, figures, metriques, rapport=calc["rapport"][1:], latex=sol.get("latex", []))
    sortie["status"], sortie["ok"] = calc["rapport"][0].removeprefix("Verdict : "), ok
    return sortie


@calcul("beam.apercu")
def poutreApercu(s):
    return beam_plots.beamSchematic(beam_services.buildBeamModel(s, dm()), None)


@calcul("beam.profil")
def poutreProfil(s):
    """Section d'un profilé du catalogue : S, inerties, fibres extrêmes (valeurs du catalogue)."""
    p = dm().getProfile(s["pfam"], s["choix"])
    sec = geometry.fromProfile(p)
    P, Pt = geometry.analytical(sec), geometry.tabulated(sec)
    return {"S": p["S"] * 1e6, "Iz": p["Iz"] * 1e12, "Iy": p["Iy"] * 1e12, "Ix": P["J"] * 1e12, "Iyz": 0.0,
            "ky": Pt["ky"], "kz": Pt["kz"], "vy": p["h"] / 2 * 1e3, "vz": p["b"] / 2 * 1e3,
            "section": None, "secTabulated": False}  # fmt: skip


_enregistrer_communs("beam", "Beam")


# ---------------------------------------------------------------------------------------------------- treillis


@calcul("truss")
def treillis(s):
    calc = validation_report.recompute("Tr", s, dm(), None)
    r = calc["result"]
    figure = _figure(lambda: other_plots.truss(r["truss"], r["tsol"], s["scale"] if s["scale"] > 0 else None))
    return _sortie("Tr", s, calc, [("Treillis", figure)], latex=r["tsol"].get("latex", []))


@calcul("truss.apercu")
def treillisApercu(s):
    return other_plots.truss(compute._readTruss(s))


_enregistrer_communs("truss", "Tr")


# -------------------------------------------------------------------------------------------------- formulaires


def _formulaires() -> dict:
    noms = dm().listMaterials()
    return {
        "beam": {
            "titre": "Poutre 2D", "defaut": loadExample("Beam"), "apercu": True, "auto": False, "dossier": True,
            "exemples": exampleNames("Beam"), "paquets": ["scipy", "shapely"],
            "caches": ["supx", "hg", "combo", "na", "gM0", "gM1", "Cmy", "CmLT", "Lcr", "LcrF", "C1", "ecsrc", "fR", "fka",
                       "fkb", "mvP", "mvE", "mvN", "mvFixed", "pdef", "secTabulated", "section"],
            "suites": {"mat": {"calcul": "materiau", "champs": ["E", "G", "Re"]}},
            "groupes": [
                groupe("Poutre et matériau",
                       nb("L", "Longueur L", "m", 0.0, aide="Longueur de la poutre entre ses deux extrémités."),
                       liste("mat", "Matériau", noms, aide="Remplit E, G et Re avec les valeurs de la base."),
                       nb("E", "E", "GPa", aide="Module d'Young : rigidité du matériau (acier 210 GPa)."),
                       nb("G", "G", "GPa", aide="Module de cisaillement : G = E / (2(1+ν))."),
                       nb("Re", "Re", "MPa", aide="Limite élastique.")),
                groupe("Section",
                       liste("pfam", "Famille de profilés", FAMILLES_PROFILES),
                       {"id": "profil", "type": "action", "libelle": "Profilé du catalogue", "options_de": {"calcul": "profils", "cle": "famille", "depuis": "pfam"},
                        "bouton": "Utiliser ce profilé", "calcul": "beam.profil", "aide": "Remplit S, inerties et fibres extrêmes avec les valeurs du catalogue."},
                       nb("S", "S", "mm²", aide="Aire de la section droite."),
                       nb("Iz", "Iz, flexion (x,y)", "mm⁴", aide="Moment quadratique pour la flexion dans le plan (x,y), charges verticales."),
                       nb("Iy", "Iy, flexion (x,z)", "mm⁴", aide="Moment quadratique pour la flexion dans le plan (x,z)."),
                       nb("Ix", "Ix, constante de torsion", "mm⁴"),
                       nb("Iyz", "Iyz, produit d'inertie (0 si axes principaux)", "mm⁴"),
                       nb("ky", "ky, section réduite (Ty)", "", aide="Le cisaillement est repris par S/ky ; 1 par défaut."),
                       nb("kz", "kz, section réduite (Tz)", ""),
                       nb("vy", "Fibre extrême |y|max", "mm"), nb("vz", "Fibre extrême |z|max", "mm")),
                groupe("Appuis et charges",
                       tableau("sup", "Appuis", [col("pos", "Position (m)"), col("type", "Type", "liste", TYPES_APPUI, "appui_simple"), col("name", "Nom", "texte", defaut="")],
                               aide="appui_simple et pivot_glissant bloquent y et z ; rotule et pivot bloquent x, y et z ; encastrement bloque tout."),
                       tableau("pl", "Forces ponctuelles", [col("pos", "Position (m)"), col("Fx", "Fx (kN)"), col("Fy", "Fy (kN)"), col("Fz", "Fz (kN)"),
                                                            col("name", "Nom", "texte", defaut=""), col("case", "Cas", "liste", CAS, "G")],
                               aide="Fy < 0 : force vers le bas."),
                       tableau("pm", "Couples ponctuels", [col("pos", "Position (m)"), col("Mx", "Mx (kN·m)"), col("My", "My (kN·m)"), col("Mz", "Mz (kN·m)"),
                                                           col("name", "Nom", "texte", defaut=""), col("case", "Cas", "liste", CAS, "G")]),
                       tableau("dl", "Charges réparties", [col("a", "a (m)"), col("b", "b (m)"), col("dir", "Dir.", "liste", ["x", "y", "z"], "y"),
                                                           col("type", "Type", "liste", ["uniforme", "linéaire", "polynomiale"], "uniforme"),
                                                           col("vals", "Valeurs (kN/m)", "texte", defaut="-10"), col("name", "Nom", "texte", defaut=""),
                                                           col("case", "Cas", "liste", CAS, "G")],
                               aide="Uniforme « p0 » ; linéaire « p1 p2 » (de a à b) ; polynomiale : coefficients en ξ = s − a, ordre décroissant."),
                       note="Signes : Fy < 0 = vers le bas ; Fx > 0 = vers la droite ; Mz > 0 = sens trigonométrique."),
                groupe("Calcul",
                       liste("plane", "Plan de la déformée", ["xy", "xz"], etiquettes=["(x,y) : v, Mfz, Iz", "(x,z) : w, Mfy, Iy"]),
                       case("shear", "Tranchant dans Castigliano"),
                       nb("s", "Coefficient de sécurité s", "", 0.0, aide="On exige σ ≤ Re / s (typiquement 1,5 à 3)."),
                       nb("Kt", "Kt", "", 0.0, aide="Concentration de contrainte (1 sans trou ni épaulement)."),
                       nb("thDT", "ΔT uniforme", "°C"), nb("thGy", "Gradient selon y : T(+y) − T(−y)", "°C"),
                       nb("thGz", "Gradient selon z : T(+z) − T(−z)", "°C"),
                       case("selfw", "Poids propre (ρ·S·g, cas G)"), ouvert=False),
            ],
            "note": "Combinaisons, Eurocode 3, fatigue, charge mobile et recherche du profilé le plus léger : dans l'application de bureau.",
        },
        "truss": {
            "titre": "Treillis", "defaut": loadExample("Tr"), "apercu": True, "auto": False, "dossier": True,
            "exemples": exampleNames("Tr"), "paquets": ["scipy", "shapely"],
            "suites": {"mat": {"calcul": "materiau", "champs": ["E"]}},
            "groupes": [
                groupe("Matériau et section", liste("mat", "Matériau", noms), nb("E", "E", "GPa"), nb("S", "S", "mm²", 0.0),
                       nb("scale", "Amplification de la déformée (0 = auto)", "", 0.0)),
                groupe("Nœuds et barres",
                       tableau("nodes", "Nœuds (coordonnées en m)", [col("name", "Nom", "texte", defaut=""), col("x", "x (m)"), col("y", "y (m)")], mini=2),
                       tableau("bars", "Barres (numéros des nœuds, à partir de 1)", [col("i", "Nœud i", defaut=1, entier=True), col("j", "Nœud j", defaut=2, entier=True)], mini=1)),
                groupe("Appuis et charges",
                       tableau("sup", "Appuis (déplacements bloqués)", [col("node", "Nœud", defaut=1, entier=True), col("bx", "Bloqué x", "case", defaut=True), col("by", "Bloqué y", "case", defaut=True)]),
                       tableau("loads", "Charges nodales", [col("node", "Nœud", defaut=1, entier=True), col("Fx", "Fx (kN)"), col("Fy", "Fy (kN)", defaut=-10.0)])),
            ],
            "note": "Barres articulées à leurs extrémités, charges aux nœuds seulement.",
        },
    }


formulaires_de(_formulaires)
_ = texte  # brique disponible pour les pages suivantes

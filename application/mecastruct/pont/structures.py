"""Pont des pages « Structures » et « Sections et contraintes » : formulaires, calculs, schémas, dossier de validation.

Ces calculs demandent scipy et shapely : la page web les charge avant le premier appel (noyau.charger). Le calcul,
les explications et le dossier passent par services.validation_report, comme dans l'application de bureau.
"""

import copy
import math
import re

import numpy as np

from mecastruct.core import buckling, geometry
from mecastruct.core.data_manager import sectionPresets
from mecastruct.core.pp import asPP
from mecastruct.plots import beam_plots, other_plots, section_plots, sollicitation_plots
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


# ----------------------------------------------------------------------- sections, sollicitations, flambage…


def _simple(ident: str, tab: str, figures) -> None:
    """Calcul `ident` : recalcul de l'onglet `tab`, puis graphiques figures(saisie, calc) → [(titre, figure)]."""

    @calcul(ident)
    def f(s):
        calc = validation_report.recompute(tab, s, dm(), None)
        r = calc["result"]
        return _sortie(tab, s, calc, [(t, _figure(g)) for t, g in figures(s, calc)], latex=list(r.get("latex", []) or []))

    _enregistrer_communs(ident, tab)


def _figuresSection(s, calc):
    r = calc["result"]
    return [("Section", lambda: section_plots.section(r["sec"], r["P"])),
            ("Contraintes σ(y) et τ(y)", lambda: section_plots.sectionStress(r["sec"], r["P"], r["bend"], r["jour"]))]


def _figuresTraction(s, calc):
    r = calc["result"]
    return [("Contrainte σ(x)", lambda: sollicitation_plots.tractionStress(r["x"], s["N"] * 1e3, r["Sx"], s["Kt"], r["sigmaAdm"])),
            ("Allongements", lambda: sollicitation_plots.elongations(r["dL"]))]


def _figuresCisaillement(s, calc):
    r, sec = calc["result"], s["section"]
    P = geometry.analytical(sec)
    taux = [abs(r["shear"]["tauMax"]) / r["shear"]["tauAdm"], abs(r["jour"]["tauMax"]) / r["shear"]["tauAdm"],
            abs(r["bearing"]["P"]) / (s["Padm"] * 1e6)]
    return [("Taux d'utilisation", lambda: sollicitation_plots.ratios(["τmax/τadm", "τJourawski/τadm", "P/Padm"], taux,
                                                                      "Taux d'utilisation (cisaillement et matage)")),
            ("Section", lambda: section_plots.section(sec, P)),
            ("Jourawski τ(y)", lambda: section_plots.sectionStress(sec, P, None, r["jour"]))]


def _figuresTorsion(s, calc):
    r = calc["result"]
    return [("Contrainte τ(r)", lambda: sollicitation_plots.torsionStress(r, s["D"] * 1e-3)),
            ("Angle de torsion", lambda: sollicitation_plots.torsionAngle(s["L"], r["theta"], r["phi"]["analytique"]))]


def _figuresFlexion(s, calc):
    r = calc["result"]
    return [("Section et axe neutre", lambda: sollicitation_plots.bendingMarks(section_plots.section(r["sec"], r["P"]), r["P"], r["bend"])),
            ("Contrainte σ(y)", lambda: section_plots.sectionStress(r["sec"], r["P"], r["bend"], None))]


def _figuresFlambage(s, calc):
    r = calc["result"]
    return [("Courbe de flambement", lambda: other_plots.bucklingCurve(r["curve"], r["analysis"])),
            ("Mode de flambement", lambda: other_plots.bucklingMode(r["analysis"]))]


def _figuresTenseur(s, calc):
    r = calc["result"]
    fa, pr = r["facet"], r["principal"]
    sig = np.array(s["sig"], dtype=float)
    if np.all(np.abs(sig[2, :]) <= 1e-12 * max(1.0, np.max(np.abs(sig)))):
        point = [r["plane2D"]["sigma1"], r["plane2D"]["sigma2"]]
    else:
        point = [pr["sigmaI"] - pr["sigmaII"], pr["sigmaIII"] - pr["sigmaII"]]
    return [("Tricercle de Mohr", lambda: other_plots.mohr3D(r["mohr3D"], [fa["sigmaN"], fa["tauNorm"]])),
            ("Mohr 2D (plan x, y)", lambda: other_plots.mohr2D(r["plane2D"], r["plane2D"]["theta"])),
            ("Lieu de plasticité", lambda: other_plots.yieldLocus(r["loci"], point))]


def _figuresHooke(s, calc):
    return [("Cercle de Mohr", lambda: other_plots.mohr2D(calc["result"]["mohr"]))]


def _figuresJauges(s, calc):
    r = calc["result"]
    return [("Mohr des déformations (rosette)", lambda: other_plots.mohr2D(r["mohrDeformations"])),
            ("Mohr des contraintes (rosette)", lambda: other_plots.mohr2D(r["mohrContraintes"]))]


for _ident, _tab, _figures in (("sec", "Sec", _figuresSection), ("tra", "Tra", _figuresTraction),
                               ("cis", "Cis", _figuresCisaillement), ("tor", "Tor", _figuresTorsion),
                               ("fle", "Fle", _figuresFlexion), ("fla", "Fla", _figuresFlambage),
                               ("ten", "Ten", _figuresTenseur), ("hoo", "Hoo", _figuresHooke), ("jau", "Jau", _figuresJauges)):
    _simple(_ident, _tab, _figures)


@calcul("sec.apercu")
def sectionApercu(s):
    sec = compute._sectionFromSaisie(s, dm())
    return section_plots.section(sec, geometry.analytical(sec))


@calcul("sec.preset")
def sectionPreset(s):
    p = next(p for p in sectionPresets() if p["name"] == s["choix"])
    return {"type": p["type"], **{k: float(v) for k, v in p["dims"].items()}}


@calcul("fla.profil")
def flambageProfil(s):
    p = dm().getProfile(s["fam"], s["prof"])
    return {"S": p["S"] * 1e6, "Iz": p["Iz"] * 1e12, "Iy": p["Iy"] * 1e12}


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


CRITERES = (["Tresca", "VonMises"], ["Tresca (τe = Re/2)", "Von Mises (τe = Re/√3)"])
DIMENSIONS = {"b": "b, largeur selon z", "h": "h, hauteur selon y", "D": "D, diamètre extérieur", "d": "d, diamètre intérieur",
              "B": "B, largeur", "H": "H, hauteur", "t": "t, épaisseur", "tw": "tw = a, âme", "tf": "tf = e, aile"}
TYPES_PAR_DIMENSION = {"b": ["rectangle", "I", "T", "U", "L"], "h": ["rectangle", "I", "T", "U", "L"], "D": ["disque", "couronne"],
                       "d": ["couronne"], "B": ["rectangle_creux"], "H": ["rectangle_creux"], "t": ["rectangle_creux", "L"],
                       "tw": ["I", "T", "U"], "tf": ["I", "T", "U"]}


def si(champ, ident, *valeurs):
    """Champ affiché seulement si le champ `ident` vaut l'une des `valeurs`."""
    return {**champ, "si": {"id": ident, "valeurs": list(valeurs)}}


def _formulaires_rdm() -> dict:
    noms = dm().listMaterials()
    familles = dm().listProfileFamilies()
    types = geometry.sectionTypes()
    conditions = buckling.listConditions()
    commun = {"apercu": False, "auto": False, "dossier": True, "paquets": ["scipy", "shapely"]}
    return {
        "sec": {
            **commun, "titre": "Section", "defaut": loadExample("Sec"), "apercu": True, "exemples": exampleNames("Sec"),
            "caches": ["s0"],
            "groupes": [
                groupe("Type de section",
                       liste("type", "Type de section", [t["type"] for t in types], etiquettes=[t["label"] for t in types]),
                       si(liste("fam", "Famille de profilé", familles), "type", "profile"),
                       si({**liste("prof", "Profilé du catalogue", []), "options_de": {"calcul": "profils", "cle": "famille", "depuis": "fam"}}, "type", "profile"),
                       {"id": "preset", "type": "action", "libelle": "Tube ou cornière courant", "options": [p["name"] for p in sectionPresets()],
                        "bouton": "Remplir les dimensions", "calcul": "sec.preset"},
                       *[si(nb(k, v, "mm", 0.0), "type", *TYPES_PAR_DIMENSION[k]) for k, v in DIMENSIONS.items()],
                       si(tableau("rects", "Rectangles pleins (repère O1, coin bas-gauche)", [col(k, f"{k} (mm)") for k in ("z1", "z2", "y1", "y2")]), "type", "composite"),
                       si(tableau("holes", "Trous rectangulaires", [col(k, f"{k} (mm)") for k in ("z1", "z2", "y1", "y2")]), "type", "composite")),
                groupe("Matériau, méthode et efforts pour σ(y) et τ(y)",
                       liste("mode", "Méthode intégrale", ["symbolique", "numerique"], etiquettes=["symbolique (int)", "numérique (integral2)"]),
                       liste("mat", "Matériau", noms),
                       nb("N", "N : traction > 0", "kN"), nb("Mfz", "Mfz : plan (x, y), fibres du haut comprimées si > 0", "kN·m"),
                       nb("Mfy", "Mfy : plan (x, z), fibres z > 0 tendues si > 0", "kN·m"), nb("Ty", "Ty : tranchant en y", "kN"),
                       nb("Kt", "Kt", "", 1.0)),
            ],
        },
        "tra": {
            **commun, "titre": "Traction", "defaut": loadExample("Tra"), "exemples": exampleNames("Tra"),
            "suites": {"mat": {"calcul": "materiau", "champs": ["E", "nu", "alpha", "Re"]}},
            "groupes": [
                groupe("Barre et chargement", nb("N", "N (> 0 traction)", "kN"), nb("S0", "S0", "mm²", 0.0), nb("L0", "L0", "m", 0.0),
                       liste("mat", "Matériau", noms), nb("E", "E", "GPa"), nb("nu", "ν", ""), nb("alpha", "α", "10⁻⁶/°C"), nb("Re", "Re", "MPa"),
                       nb("dT", "ΔT", "°C"), nb("Kt", "Kt", "", 1.0), nb("s", "Coefficient de sécurité s", ""),
                       nb("dLmax", "ΔL max (0 = sans limite)", "mm", 0.0)),
                groupe("Section variable", case("varS", "Utiliser S(x)"), texte("Sexpr", "S(x) (mm², x en m)"), ouvert=False),
            ],
        },
        "cis": {
            **commun, "titre": "Cisaillement", "defaut": loadExample("Cis"), "caches": ["section"],
            "suites": {"mat": {"calcul": "materiau", "champs": ["Re", "G"]}},
            "groupes": [
                groupe("Matériau et critère", liste("mat", "Matériau", noms), nb("Re", "Re", "MPa"), nb("G", "G", "GPa"),
                       liste("crit", "Critère (τe)", CRITERES[0], etiquettes=CRITERES[1]), nb("s", "Coefficient de sécurité s", "")),
                groupe("Cisaillement simple et Jourawski", nb("T", "T", "kN"), nb("S", "S cisaillée", "mm²", 0.0), nb("k", "k = τmax/τmoy", ""),
                       note="Jourawski : section de l'exemple (dans l'application de bureau, celle de la page Sections), Ty = T."),
                groupe("Matage", nb("Fm", "F", "kN"), nb("Sm", "S matée", "mm²", 0.0), nb("Padm", "P_adm", "MPa", 0.0)),
                groupe("Clavette", nb("C", "Couple C", "kN·m"), nb("Dk", "Diamètre d'arbre D", "mm"), nb("ak", "Largeur a", "mm"),
                       nb("bk", "Hauteur b", "mm"), nb("Lk", "Longueur L (0 = dimensionner)", "mm", 0.0), ouvert=False),
                groupe("Goupille", nb("Fp", "F", "kN"), nb("dp", "d", "mm"), nb("ep", "e, épaisseur matée", "mm"),
                       nb("np", "Sections cisaillées n", "", 1, entier=True), ouvert=False),
            ],
        },
        "tor": {
            **commun, "titre": "Torsion", "defaut": loadExample("Tor"),
            "suites": {"mat": {"calcul": "materiau", "champs": ["G", "Re"]}},
            "groupes": [groupe("Arbre circulaire", nb("Mt", "Mt", "kN·m"), nb("D", "D", "mm", 0.0), nb("d", "d, alésage (0 = plein)", "mm", 0.0),
                               nb("L", "L", "m", 0.0), liste("mat", "Matériau", noms), nb("G", "G", "GPa"), nb("Re", "Re", "MPa"),
                               liste("crit", "Critère (τe)", CRITERES[0], etiquettes=CRITERES[1]), nb("s", "Coefficient de sécurité s", ""),
                               nb("Kt", "Kt", "", 1.0), nb("thetaAdm", "θ admissible (0 = sans)", "°/m", 0.0))],
        },
        "fle": {
            **commun, "titre": "Flexion", "defaut": loadExample("Fle"), "caches": ["s0", "section"],
            "suites": {"mat": {"calcul": "materiau", "champs": ["Re"]}},
            "groupes": [
                groupe("Efforts dans la section étudiée", nb("N", "N : traction > 0", "kN"), nb("Mfz", "Mfz : plan (x,y)", "kN·m"),
                       nb("Mfy", "Mfy : plan (x,z)", "kN·m"),
                       note="Section de l'exemple ; dans l'application de bureau, celle de la page Sections et les efforts de la poutre."),
                groupe("Kt, matériau et sécurité", nb("Kt", "Kt", "", 1.0), liste("mat", "Matériau", noms), nb("Re", "Re", "MPa"),
                       nb("s", "Coefficient de sécurité s", "")),
            ],
        },
        "fla": {
            **commun, "titre": "Flambage", "defaut": loadExample("Fla"), "exemples": exampleNames("Fla"),
            "suites": {"mat": {"calcul": "materiau", "champs": ["E", "Re"]}},
            "groupes": [
                groupe("Section", liste("fam", "Famille de profilé", familles),
                       {**liste("prof", "Profilé", []), "options_de": {"calcul": "profils", "cle": "famille", "depuis": "fam"}},
                       {"id": "charger", "type": "bouton", "libelle": "Charger le profilé", "calcul": "fla.profil",
                        "aide": "Remplit S, Iz et Iy avec les valeurs du catalogue."},
                       nb("S", "S", "mm²", 0.0), nb("Iz", "Iz", "mm⁴", 0.0), nb("Iy", "Iy", "mm⁴", 0.0)),
                groupe("Poutre comprimée", liste("mat", "Matériau", noms), nb("E", "E", "GPa"), nb("Re", "Re", "MPa"),
                       nb("L", "Longueur L", "m", 0.0),
                       liste("cond", "Conditions aux limites", [c["Condition"] for c in conditions],
                             etiquettes=[f"{c['Libelle']} (L' = {c['CoefficientTexte']} L)" for c in conditions]),
                       nb("P", "P appliquée (compression > 0, 0 = aucune)", "kN"), nb("s", "Coefficient de sécurité s", "")),
            ],
        },
        "ten": {
            **commun, "titre": "Tenseurs", "defaut": loadExample("Ten"),
            "suites": {"mat": {"calcul": "materiau", "champs": ["Re", "Rm"]}},
            "groupes": [
                groupe("Tenseur des contraintes σ (MPa)", {"id": "sig", "type": "matrice", "libelle": "σ (MPa)", "noms": ["x", "y", "z"], "symetrique": True,
                                                           "aide": "Une case modifiée est recopiée en position symétrique (σij = σji)."}),
                groupe("Facette", liste("fmode", "Définition", ["theta", "n"], etiquettes=["Angle θ dans le plan (x, y)", "Normale n (nx, ny, nz)"]),
                       si(nb("theta", "θ", "°"), "fmode", "theta"),
                       si(nb("nx", "nx", ""), "fmode", "n"), si(nb("ny", "ny", ""), "fmode", "n"), si(nb("nz", "nz", ""), "fmode", "n")),
                groupe("Critères", liste("mat", "Matériau", noms), nb("Re", "Re = σe", "MPa"), nb("Rm", "σR (fragiles : Rm)", "MPa"),
                       nb("s", "Coefficient de sécurité s", "")),
            ],
        },
        "hoo": {
            **commun, "titre": "Loi de Hooke", "defaut": loadExample("Hoo"), "exemples": exampleNames("Hoo"),
            "suites": {"mat": {"calcul": "materiau", "champs": ["E", "nu", "alpha"]}},
            "groupes": [
                groupe("Loi", liste("mode", "Loi", ["iso3D", "planeStress", "planeStrain", "ortho"],
                                    etiquettes=["Hooke 3D isotrope", "Contraintes planes", "Déformations planes", "Orthotrope (9 constantes)"])),
                groupe("Matériau isotrope", si(liste("mat", "Matériau", noms), "mode", "iso3D", "planeStress", "planeStrain"),
                       si(nb("E", "E", "GPa"), "mode", "iso3D", "planeStress", "planeStrain"),
                       si(nb("nu", "ν", ""), "mode", "iso3D", "planeStress", "planeStrain"),
                       si(nb("alpha", "α", "10⁻⁶/°C"), "mode", "iso3D"), si(nb("dT", "ΔT", "°C"), "mode", "iso3D")),
                groupe("Contraintes (MPa)", *[si(nb(k, n, "MPa"), "mode", *m) for k, n, m in (
                    ("sxx", "σxx", ("iso3D", "planeStress", "ortho")), ("syy", "σyy", ("iso3D", "planeStress", "ortho")),
                    ("szz", "σzz", ("iso3D", "ortho")), ("syz", "σyz", ("iso3D", "ortho")), ("sxz", "σxz", ("iso3D", "ortho")),
                    ("sxy", "σxy", ("iso3D", "planeStress", "ortho")))]),
                groupe("Déformations planes (µdéf)", *[si(nb(k, n, "µdéf"), "mode", "planeStrain") for k, n in (("exx", "εxx"), ("eyy", "εyy"), ("gxy", "γxy = 2εxy"))]),
                groupe("Orthotrope (axes 1, 2, 3 = x, y, z)", *[si(nb(k, n, u), "mode", "ortho") for k, n, u in (
                    ("E1", "E1", "GPa"), ("E2", "E2", "GPa"), ("E3", "E3", "GPa"), ("nu12", "ν12", ""), ("nu13", "ν13", ""), ("nu23", "ν23", ""),
                    ("G12", "G12", "GPa"), ("G13", "G13", "GPa"), ("G23", "G23", "GPa"))]),
            ],
        },
        "jau": {
            **commun, "titre": "Jauges et rosettes", "defaut": loadExample("Jau"),
            "suites": {"mat": {"calcul": "materiau", "champs": ["E", "nu"]}},
            "groupes": [
                groupe("Jauge (loi de Bridgman)", nb("K", "Facteur de jauge K", ""), nb("eps", "ε", "µdéf"), nb("R0", "R0", "Ω")),
                groupe("Pont de Wheatstone", liste("cfg", "Montage", ["quart", "demi", "complet"], etiquettes=["Quart de pont", "Demi-pont", "Pont complet"]),
                       nb("Vin", "Alimentation Vin", "V"), *[nb(f"e{i}", f"ε{i}", "µdéf") for i in range(1, 5)], nb("Vout", "Vout mesurée", "mV")),
                groupe("Rosette", liste("rtype", "Type", ["45", "60"], etiquettes=["Rectangulaire 0°/90°/45°", "Delta 0°/60°/120°"]),
                       nb("ra", "ε à 0°", "µdéf"), nb("rb", "ε à 90° (rect.) / 60° (delta)", "µdéf"), nb("rc", "ε à 45° (rect.) / 120° (delta)", "µdéf"),
                       liste("mat", "Matériau", noms), nb("E", "E", "GPa"), nb("nu", "ν", "")),
            ],
        },
    }


formulaires_de(_formulaires)
formulaires_de(_formulaires_rdm)

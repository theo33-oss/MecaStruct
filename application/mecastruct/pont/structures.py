"""Pont des pages « Structures » et « Sections et contraintes » : formulaires, calculs, schémas, dossier de validation.

Ces calculs demandent scipy et shapely : la page web les charge avant le premier appel (noyau.charger). Le calcul,
les explications et le dossier passent par services.validation_report, comme dans l'application de bureau.
"""

import base64
import copy
import math
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mecastruct.core import beam_solver, buckling, frame3d, geometry
from mecastruct.core.data_manager import sectionPresets
from mecastruct.core.pp import asPP
from mecastruct.core.units import fromSI
from mecastruct.plots import beam_plots, other_plots, section_plots, sollicitation_plots
from mecastruct.pont import exports
from mecastruct.pont.formulaire import case, col, groupe, liste, nb, tableau, texte
from mecastruct.pont.noyau import calcul, dm, formulaires_de
from mecastruct.services import (
    beam_design,
    beam_services,
    compute,
    criteres,
    ossature3d,
    project_io,
    valeurs_cles,
    validation_report,
)
from mecastruct.services.examples import exampleNames, loadExample
from mecastruct.services.sources import avec_sources

TYPES_APPUI = ["appui_simple", "rotule", "pivot", "pivot_glissant", "encastrement"]
CAS = ["G", "Q", "W", "S"]
COMPOSANTES = ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]
FAMILLES_PROFILES = ["IPE", "HEA", "HEB", "IPN", "UPN", "UAP"]


# --------------------------------------------------------------------------------------------- outils communs


_ok = criteres.verdict  # verdict lu dans la ligne d'état du calcul


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
        "criteres": criteres.criteres(tab, saisie, calc),
        "valeurs": valeurs_cles.valeurs(status),
        "_brut": calc,
    }


def _enregistrer_communs(ident: str, tab: str) -> None:
    """Exemples et dossier de validation du calcul `ident` (onglet `tab` de l'application de bureau)."""

    @calcul(f"{ident}.exemple")
    def exemple(s):
        ex = loadExample(tab, s.get("nom"))
        if tab == "Beam":  # sa section vient du catalogue (IPE) ou de la page Sections : elle est dessinée
            ex["secSrc"] = "catalogue" if isinstance(ex.get("section"), dict) and ex["section"].get("type") == "profile" else "sections"
        return ex

    @calcul(f"{ident}.dossier")
    def dossierValidation(s):
        calc = validation_report.recompute(tab, copy.deepcopy(s), dm(), None)
        return {"nom": validation_report.fileName(tab), "html": validation_report.generate(tab, s, calc, dm())}

    @calcul(f"{ident}.enregistrer")
    def enregistrer(s):
        """Fichier de problème de l'application de bureau (même format : il s'ouvre dans les deux versions)."""
        return {"nom": f"MecaStruct_{validation_report.meta(tab)['title'].replace(' ', '_')}.json",
                "texte": project_io.problemToJson(tab, s)}  # fmt: skip

    @calcul(f"{ident}.ouvrir")
    def ouvrir(s):
        """Saisie d'un fichier de problème, vérifiée (onglet, taille, genre de chaque champ)."""
        return project_io.problemFromJson(s["texte"], tab)[1]

    @calcul(f"{ident}.excel")
    def excel(s):
        """Classeur Excel des tableaux de résultats (base64) ; un texte ne devient jamais une formule."""
        calc = validation_report.recompute(tab, copy.deepcopy(s), dm(), None)
        donnees = project_io.toXlsx(project_io.resultSheets(tab, calc))
        return {"nom": f"MecaStruct_{validation_report.meta(tab)['title'].replace(' ', '_')}_resultats.xlsx",
                "base64": base64.b64encode(donnees).decode("ascii")}  # fmt: skip

    exports.declarer(ident)


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
    modele = beam_services.buildBeamModel(s, dm())
    beam_solver._normalizeModel(modele)  # appui ou charge hors de la poutre : le message du calcul, pas un schéma faux
    return beam_plots.beamSchematic(modele, None)


@calcul("beam.profil")
def poutreProfil(s):
    """Section d'un profilé du catalogue : S, inerties, fibres extrêmes (valeurs du catalogue) et sa géométrie."""
    p = dm().getProfile(s["pfam"], s["choix"])
    sec = geometry.fromProfile(p)
    P, Pt = geometry.analytical(sec), geometry.tabulated(sec)
    return {"S": p["S"] * 1e6, "Iz": p["Iz"] * 1e12, "Iy": p["Iy"] * 1e12, "Ix": P["J"] * 1e12, "Iyz": 0.0,
            "ky": Pt["ky"], "kz": Pt["kz"], "vy": p["h"] / 2 * 1e3, "vz": p["b"] / 2 * 1e3,
            "section": sec, "secTabulated": True, "secSrc": "catalogue"}  # fmt: skip


# --------------------------------------------------------------------- section de la poutre : forme ou tige filetée
# Formes paramétrées proposées dans Poutres (celles de la page Sections, sans profilé ni section composée)
FORMES_POUTRE = ["rectangle", "disque", "couronne", "rectangle_creux", "I", "T", "U", "L"]
# Filetage métrique à pas gros (ISO 261) : diamètre nominal d (mm) → pas P (mm)
PAS_ISO = {"M3": 0.5, "M4": 0.7, "M5": 0.8, "M6": 1.0, "M8": 1.25, "M10": 1.5, "M12": 1.75, "M14": 2.0, "M16": 2.0,
           "M18": 2.5, "M20": 2.5, "M22": 2.5, "M24": 3.0, "M27": 3.0, "M30": 3.5, "M33": 3.5, "M36": 4.0}  # fmt: skip


def tige_filetee(nom: str, diametre: str) -> dict:
    """Diamètres d'une tige filetée ISO : d, pas P, d2 = d − 0,6495·P, noyau d3 = d − 1,2269·P, ds = (d2 + d3)/2 et
    section résistante As = π·ds²/4 (ISO 898-1), en mm et mm². `diametre` choisit le disque de calcul : « noyau » (d3,
    prudent) ou « resistant » (ds, section As)."""
    d, P = float(nom[1:]), PAS_ISO[nom]
    d2, d3 = d - 0.649519 * P, d - 1.226869 * P
    ds = (d2 + d3) / 2
    return {"d": d, "P": P, "d2": d2, "d3": d3, "ds": ds, "As": math.pi * ds**2 / 4, "D": d3 if diametre == "noyau" else ds}


def _section_parametree(s: dict) -> tuple[dict, str] | None:
    """Section (dimensions en m) décrite par la saisie de Poutres si son origine est une forme ou une tige, sinon None."""
    if s.get("secSrc") == "forme":
        forme = s.get("secForme", "rectangle")
        dims = {k: float(s["f_" + k]) / 1e3 for k, types in TYPES_PAR_DIMENSION.items() if forme in types}
        sec = geometry.validateSection({"type": forme, **dims})
        return sec, compute._sectionLabel(sec)
    if s.get("secSrc") == "tige":
        t = tige_filetee(s.get("tigeM", "M10"), s.get("tigeD", "noyau"))
        sec = geometry.validateSection({"type": "disque", "D": t["D"] / 1e3})
        quoi = "noyau d3" if s.get("tigeD", "noyau") == "noyau" else "diamètre résistant ds"
        return sec, (f"Tige filetée {s.get('tigeM', 'M10')} × {t['P']:g} : calcul sur le {quoi} = {t['D']:.3f} mm "
                     f"(d3 = {t['d3']:.3f} mm, As = {t['As']:.1f} mm²)")  # fmt: skip
    return None


@calcul("beam.forme")
def poutreForme(s):
    """Suite des champs de la section : S, inerties, ky, kz, fibres et géométrie d'une forme paramétrée ou d'une tige.

    Entrée : {nom, champs, saisie} (la saisie entière de Poutres). Sortie : champs à recopier ({} si l'origine de la
    section n'est ni une forme ni une tige : les valeurs saisies restent).
    """
    saisie = s.get("saisie") or {}
    trouve = _section_parametree(saisie)
    if trouve is None:
        return {}
    sec, _ = trouve
    out = beam_design.sectionToBeamInput(saisie, sec, geometry.analytical(sec), None)
    return {k: out[k] for k in ("S", "Iz", "Iy", "Ix", "Iyz", "ky", "kz", "vy", "vz", "section", "secTabulated")}


@calcul("beam.section")
def poutreSection(s):
    """Image de la section de la poutre, avec ses dimensions principales, pour la saisie ; rien si elle est inconnue."""
    trouve = _section_parametree(s)
    if trouve is not None:
        sec, titre = trouve
    elif s.get("secSrc") != "saisie" and isinstance(s.get("section"), dict):
        sec = geometry.validateSection(s["section"])
        titre = compute._sectionLabel(sec)
    else:
        return {"vide": "Valeurs saisies à la main : la forme de la section n'est pas connue, elle n'est pas dessinée."}
    fig = section_plots.section(sec, geometry.analytical(sec))
    fig.update_layout(title=titre, showlegend=False, height=300, margin=dict(l=40, r=20, t=60, b=40))
    return fig


_enregistrer_communs("beam", "Beam")


def _complement(status, ok, tables, figures=(), crit=None):
    return {"status": status, "ok": ok, "tables": tables, "figures": [{"titre": t, "figure": f} for t, f in figures if f is not None],
            "metriques": [], "rapport": [], "latex": [], "explications": [], "blocs": [], "criteres": crit or []}  # fmt: skip


@calcul("annexe")
def annexe(s):
    """Annexe nationale EN ou FR : γM0 = γM1 = 1 (champs libres pour « autre »)."""
    return {"gM0": 1.0, "gM1": 1.0} if s["nom"] in ("EN", "FR") else {}


@calcul("beam.combos")
def poutreCombinaisons(s):
    T = beam_services.computeCombinations(s, dm())
    env = T.iloc[-1]
    ok = env["Résistance"] == "vérifié"
    status = f"Combinaisons : {len(T) - 1} calculée(s), enveloppe Kt·σ max = {env['Kt·σ max (MPa)']:.4g} MPa ({env['Résistance']})"
    return _complement(status, ok, {"Combinaisons": T}, [("Combinaisons", _figure(lambda: beam_plots.combinations(T)))])


@calcul("beam.ec3")
def poutreEurocode(s):
    source = "enveloppe" if s["ecsrc"] == "enveloppe" else "poutre"
    e, T = beam_design.checkEurocode(s, dm(), source)
    if not e["okAll"]:
        verdict, ok = "NON vérifié", False
    elif e["pondere"]:
        verdict, ok = "vérifié", True
    else:  # efforts non pondérés : pas de verdict « vérifié »
        verdict, ok = "indicatif, efforts non pondérés : refaire avec l'enveloppe ELU", None
    status = (f"Eurocode 3 : classe {e['class']['class']}, MEd/MRd = {e['ratioM']:.3f}, VEd/Vpl,Rd = {e['ratioV']:.3f}, "
              f"MEd/Mb,Rd = {e['ltb']['ratio']:.3f} ({verdict})")  # fmt: skip
    if e["inter"]:
        status += f", N + M (6.61/6.62) = {e['inter']['ratio']:.3f}"
    return _complement(status, ok, {"Eurocode 3": T}, crit=_figure(lambda: criteres.eurocode(e)))


@calcul("beam.fatigue")
def poutreFatigue(s):
    r, T = beam_design.checkFatigue(s, dm())
    ok = r["n"] >= s["s"]
    return _complement(f"Fatigue (Goodman) : n = {r['n']:.3g} pour s = {s['s']:.3g} ({'vérifié' if ok else 'NON vérifié'})", ok, {"Fatigue": T},
                       crit=_figure(lambda: criteres.fatigue(r, s["s"])))  # fmt: skip


@calcul("beam.mobile")
def poutreMobile(s):
    T, d = beam_design.computeMovingLoad(s, dm())
    e = d["extrema"]
    status = (f"Charge mobile ({d['positions']} positions) : Mfz de {e['Mmin'] / 1e3:.4g} à {e['Mmax'] / 1e3:.4g} kN·m, "
              f"Ty de {e['Tmin'] / 1e3:.4g} à {e['Tmax'] / 1e3:.4g} kN")  # fmt: skip
    return _complement(status, None, {"Enveloppe": T}, [("Enveloppe", _figure(lambda: beam_plots.movingEnvelope(d)))])


@calcul("beam.leger")
def poutreLeger(s):
    T, best = beam_design.findLightestProfile(s, dm(), s["pfam"], s["pdef"])
    if best is None:
        return _complement(f"Aucun profilé {s['pfam']} ne vérifie ce chargement : essayez une autre famille.", False, {"Profilés": T})
    return _complement(f"Profilé {s['pfam']} le plus léger qui vérifie : {best['Name']}. La saisie de la section est inchangée.", True, {"Profilés": T})


# ---------------------------------------------------------------------------------------------------- treillis


@calcul("truss")
def treillis(s):
    calc = validation_report.recompute("Tr", s, dm(), None)
    r = calc["result"]
    figure = _figure(lambda: other_plots.truss(r["truss"], r["tsol"], s["scale"] if s["scale"] > 0 else None))
    sortie = _sortie("Tr", s, calc, [("Treillis", figure)], latex=r["tsol"].get("latex", []))
    # « h = 0 (isostatique) » ne dit rien à qui ne connaît pas la notation
    sortie["ok"] = calc.get("ok")  # barres : contrainte et flambage (None si le flambage n'est pas vérifié)
    sortie["status"] = re.sub(r"^h = (-?\d+) \((\w+)\)", r"Treillis \2 (degré d'hyperstaticité h = \1)", sortie["status"])
    sortie["valeurs"] = valeurs_cles.valeurs(calc["status"])  # cartes tirées de la ligne d'origine (« h = 0 … »)
    return sortie


@calcul("truss.apercu")
def treillisApercu(s):
    return other_plots.truss(compute._readTruss(s))


_enregistrer_communs("truss", "Tr")


# ------------------------------------------------------------------------------------------------- ossature 3D


def _tables_3d(s: dict) -> dict:
    return {k: pd.DataFrame(s.get(k) or []) for k in ossature3d.TABLES}


@calcul("ossature")
def ossature(s):
    """Ossature 3D : solveur de poutres 3D (frame3d), vue 3D, efforts internes, vérification à la main."""
    base = dm()
    data = ossature3d._donnees(_tables_3d(s), bool(s.get("pp")), base)
    if not data["noeuds"] or not data["elements"]:
        raise ValueError("Saisissez au moins deux nœuds et une pièce.")
    res = frame3d.solveFrame3D(data)
    ampli = float(s.get("ampli") or 0) or ossature3d._amplification_auto(res, data)
    sig = [c["sigma_max"] for c in res["contraintes"].values() if c["sigma_max"] is not None]
    dmax, eq = res["deplacement_max"], res["equilibre"]
    formules, contraintes, manquante = ossature3d.bilan_latex(res, data)
    piece = int(s.get("piece") or 0)
    if piece not in res["efforts"]:
        piece = next(iter(res["efforts"]))
    ef, s_mm = res["efforts"][piece], np.array(res["efforts"][piece]["s"]) * 1e3
    titres = [f"{c} ({u})" for c, u in ossature3d.COMPOSANTES]
    fig = make_subplots(rows=3, cols=2, subplot_titles=titres, vertical_spacing=0.12)
    for k, (c, _u) in enumerate(ossature3d.COMPOSANTES):
        trace = go.Scatter(x=s_mm, y=ef[c], mode="lines", fill="tozeroy", line={"color": ossature3d.C_DEFORMEE}, showlegend=False)
        fig.add_trace(trace, row=k // 2 + 1, col=k % 2 + 1)
    fig.update_layout(height=640, margin={"l": 50, "r": 10, "t": 60, "b": 30}, title=f"Efforts internes de la pièce {piece}")
    fig.update_xaxes(title_text="s (mm)")
    crit = criteres.ossature(res["contraintes"], {e["id"]: e.get("Re") for e in data["elements"]})
    if eq["ok"]:
        status = "Équilibre global vérifié (réactions + charges = 0). σ est comparée à Re sans coefficient de sécurité : à vous de juger la marge."
    else:
        status = f"Écart d'équilibre : ΣF = {np.round(eq['forces'], 6).tolist()} N, ΣM = {np.round(eq['moments'], 6).tolist()} N·m."
    tables = {"Déplacements": ossature3d._table_deplacements(res), "Réactions": ossature3d._table_reactions(res),
              "Contraintes": ossature3d._table_contraintes(res), "Contraintes refaites à la main": contraintes}  # fmt: skip
    rapport = list(res["rapport"])
    if manquante:
        rapport.append("σ non calculée pour une pièce sans module de flexion Wy ou Wz : saisissez-les (section « perso »).")
    metriques = [["Déplacement max", f"{dmax['valeur'] * 1e3:.4g} mm (nœud {dmax['noeud']})"],
                 ["σmax", f"{max(sig) / 1e6:.4g} MPa" if sig else "non calculée"], ["Amplification de la vue", f"× {ampli:g}"]]  # fmt: skip
    # ok : None si l'équilibre est juste (pas de verdict de résistance, aucun coefficient de sécurité n'est demandé)
    return {"status": status, "ok": None if eq["ok"] else False, "criteres": crit, "metriques": metriques,
            "figures": [{"titre": "Vue 3D", "figure": ossature3d._vue_3d(res, data, ampli)}, {"titre": "Efforts internes", "figure": fig}],
            "tables": tables, "latex": [*formules, *res["latex"]], "rapport": rapport, "explications": [], "blocs": []}  # fmt: skip


exports.declarer("ossature")


@calcul("ossature.exemple")
def ossatureExemple(s):
    base = dm()
    exemples = ossature3d.exemples(base)
    nom = s.get("nom") or next(iter(exemples))
    return {**ossature3d._tables_exemple(nom, base), "pp": bool(exemples[nom].get("poids_propre", False)), "piece": 0, "ampli": 0}


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


# --------------------------------------------------------------------------- échanges entre les pages
# Chaque transfert reçoit les saisies des pages concernées et rend les champs à recopier ; la page web les écrit
# dans la saisie de la page cible (mêmes règles que bureau/transfert.py et les boutons de bureau/pages).


def _transfert(nom: str, entrees: dict, sorties: dict, params: dict | None = None, **autres) -> dict:
    """Bouton de transfert : `entrees` {clé: page source ou "self"}, `sorties` {clé: page cible ou "self"}."""
    return {"id": f"t-{nom}", "type": "transfert", "calcul": f"transfert.{nom}", "entrees": entrees, "sorties": sorties,
            "params": params or {}, **autres}  # fmt: skip


@calcul("transfert.section")
def transfertSection(s):
    """Section calculée de la page Sections → Poutres (S, inerties, ky, kz, fibres, matériau) et Flambage (S, Iz, Iy…)."""
    base = dm()
    saisie = s["sec"]
    res = compute.computeSection(saisie, base)["result"]
    mat = saisie["mat"]
    beam = beam_design.sectionToBeamInput(s.get("beam") or loadExample("Beam"), res["sec"], res["P"], base.getMaterial(mat))
    P = res["P"]
    fla = {"S": beam["S"], "Iz": beam["Iz"], "Iy": beam["Iy"], "mat": mat, **compute._materiau(base, mat, ["E", "Re"])}
    info = f"Section utilisée : {compute._sectionLabel(res['sec'])} (importée de Sections)."
    if res["sec"]["type"] != "profile" and abs(P["Iyz"]) > 1e-9 * (P["Iz"] * P["Iy"]) ** 0.5:
        fla.update(Iz=fromSI(P["I1"], "mm^4"), Iy=fromSI(P["I2"], "mm^4"))
        info = (f"Section utilisée : {compute._sectionLabel(res['sec'])} (importée de Sections, Iyz ≠ 0 : moments principaux "
                f"I1, I2, axes tournés de {P['alphaP'] * 180 / math.pi:.4g}°).")  # fmt: skip
    return {"beam": beam, "fla": fla, "info": info}


@calcul("transfert.section_seule")
def transfertSectionSeule(s):
    """Section de la page Sections pour Cisaillement ou Flexion (Jourawski, axe neutre)."""
    res = compute.computeSection(s["sec"], dm())["result"]
    return {"cible": {"section": res["sec"]}, "info": f"Section utilisée : {compute._sectionLabel(res['sec'])} (page Sections)."}


@calcul("transfert.efforts")
def transfertEfforts(s):
    """Efforts de la poutre (N, Mfz, Mfy, Ty) → Sections ou Flexion, en s ou au point le plus sollicité."""
    res = beam_services.computeBeam(s["beam"], dm())
    cible = beam_design.loadFromBeam(s["cible"], res, s["key"], s["mode"])
    note = "Résultats NON fiables (hyperstatique, Iyz ≠ 0). " if res["unreliable"] else ""
    info = (f"{note}Efforts lus sur la poutre en s = {cible['s0']:.4g} m : N = {cible['N']:.4g} kN, "
            f"Mfz = {cible['Mfz']:.4g} kN·m, Mfy = {cible['Mfy']:.4g} kN·m.")  # fmt: skip
    return {"cible": cible, "info": info}


@calcul("transfert.tenseur")
def transfertTenseur(s):
    """État de contrainte du point le plus sollicité de la poutre → Tenseurs et critères."""
    base = dm()
    beam = s["beam"]
    etat = beam_design.sendToTensor(beam_services.computeBeam(beam, base))
    y, z = etat["loc"][0] * 1e3, etat["loc"][1] * 1e3
    ten = {"sig": etat["sig"].tolist(), "mat": beam["mat"], "Re": beam["Re"], "Rm": base.getMaterial(beam["mat"])["Rm"] / 1e6, "s": beam["s"]}
    info = f"État de la poutre transmis : s = {etat['s']:.4g} m, (y, z) = ({y:.4g} ; {z:.4g}) mm, σxx = {etat['sig'][0, 0]:.5g} MPa."
    return {"ten": ten, "info": info}


# -------------------------------------------------------------------------------------------------- formulaires


def _formulaires() -> dict:
    noms = dm().listMaterials()
    return {
        "beam": {
            "titre": "Poutre 2D", "defaut": {**loadExample("Beam"), **DEFAUT_SECTION}, "apercu": True, "auto": False, "dossier": True,
            "exemples": exampleNames("Beam"), "paquets": ["scipy", "shapely"],
            "caches": ["secTabulated", "section"],
            "suites": {"mat": {"calcul": "materiau", "champs": ["E", "G", "Re"]}, "na": {"calcul": "annexe", "champs": []},
                       **{k: {"calcul": "beam.forme", "champs": [], "discret": True}
                          for k in ("secSrc", "secForme", "tigeM", "tigeD", *["f_" + d for d in DIMENSIONS])}},
            "groupes": [
                groupe("Poutre et matériau",
                       nb("L", "Longueur L", "m", 0.0, aide="Longueur de la poutre entre ses deux extrémités."),
                       liste("mat", "Matériau", noms, aide="Remplit E, G et Re avec les valeurs de la base."),
                       nb("E", "E", "GPa", aide="Module d'Young : rigidité du matériau (acier 210 GPa)."),
                       nb("G", "G", "GPa", aide="Module de cisaillement : G = E / (2(1+ν))."),
                       nb("Re", "Re", "MPa", aide="Limite élastique.")),
                groupe("Section",
                       liste("secSrc", "Origine de la section", list(ORIGINES_SECTION), etiquettes=list(ORIGINES_SECTION.values()),
                             aide="D'où viennent S, les inerties et les fibres extrêmes de la poutre."),
                       si(liste("pfam", "Famille de profilés", FAMILLES_PROFILES), "secSrc", "catalogue"),
                       si({"id": "profil", "type": "action", "libelle": "Profilé du catalogue", "options_de": {"calcul": "profils", "cle": "famille", "depuis": "pfam"},
                           "bouton": "Utiliser ce profilé", "calcul": "beam.profil", "aide": "Remplit S, inerties et fibres extrêmes avec les valeurs du catalogue."}, "secSrc", "catalogue"),
                       si(liste("secForme", "Forme", FORMES_POUTRE, etiquettes=[t["label"] for t in geometry.sectionTypes() if t["type"] in FORMES_POUTRE]), "secSrc", "forme"),
                       *[{**nb("f_" + k, v, "mm", 0.0), "si": [{"id": "secSrc", "valeurs": ["forme"]}, {"id": "secForme", "valeurs": TYPES_PAR_DIMENSION[k]}]}
                         for k, v in DIMENSIONS.items()],
                       si(liste("tigeM", "Tige filetée (ISO, pas gros)", list(PAS_ISO), aide="Diamètre nominal ; le pas normal ISO 261 est pris d'office."), "secSrc", "tige"),
                       si(liste("tigeD", "Diamètre de calcul", ["noyau", "resistant"], etiquettes=["Noyau d3 (prudent)", "Diamètre résistant ds (section As, ISO 898-1)"],
                                aide="Le noyau d3 donne la plus petite section ; ds donne la section résistante As des normes de boulonnerie."), "secSrc", "tige"),
                       si(_transfert("section_poutre", {"sec": "sec", "beam": "self"}, {"beam": "self"}, calcul="transfert.section", libelle="← Reprendre la section de la page Sections",
                                     aide="S, inerties, ky, kz, fibres extrêmes et matériau de la section calculée dans la page Sections."), "secSrc", "sections"),
                       {"id": "secImage", "type": "figure", "calcul": "beam.section", "libelle": "Section",
                        "depend": ["secSrc", "secForme", "tigeM", "tigeD", "pfam", "section", *["f_" + k for k in DIMENSIONS]]},
                       *[si(c, "secSrc", "catalogue", "sections", "saisie") for c in (
                           nb("S", "S", "mm²", aide="Aire de la section droite."),
                           nb("Iz", "Iz, flexion (x,y)", "mm⁴", aide="Moment quadratique pour la flexion dans le plan (x,y), charges verticales."),
                           nb("Iy", "Iy, flexion (x,z)", "mm⁴", aide="Moment quadratique pour la flexion dans le plan (x,z)."),
                           nb("Ix", "Ix, constante de torsion", "mm⁴"),
                           nb("Iyz", "Iyz, produit d'inertie (0 si axes principaux)", "mm⁴"),
                           nb("ky", "ky, section réduite (Ty)", "", aide="Le cisaillement est repris par S/ky ; 1 par défaut."),
                           nb("kz", "kz, section réduite (Tz)", ""),
                           nb("vy", "Fibre extrême |y|max", "mm"), nb("vz", "Fibre extrême |z|max", "mm"))]),
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
                groupe("Ressorts, tassements, rotules",
                       tableau("supx", "Appuis élastiques et tassements (appui désigné par son nom)",
                               [col("name", "Appui (nom)", "texte", defaut=""), col("k", "Ressort k (kN/m)"), col("dx", "Tassement x (mm)"),
                                col("dy", "Tassement y (mm)"), col("dz", "Tassement z (mm)")],
                               aide="Ressort : appui élastique de raideur k (0 = appui rigide). Tassement : déplacement imposé de l'appui."),
                       tableau("hg", "Rotules intermédiaires (poutre Gerber)", [col("pos", "Position (m)"), col("name", "Nom", "texte", defaut="")],
                               aide="Le moment de flexion y est nul au point choisi. Pas sur un appui."), ouvert=False),
                groupe("Combinaisons de cas",
                       tableau("combo", "Combinaisons (G permanentes, Q exploitation, W vent, S neige)",
                               [col("name", "Combinaison", "texte", defaut=""), col("gG", "γG"), col("gQ", "γQ"), col("gW", "γW"), col("gS", "γS")],
                               aide="Chaque charge porte un cas. Le calcul principal additionne tous les cas avec le coefficient 1 ; ici chaque ligne est résolue avec ses coefficients, puis on donne l'enveloppe."),
                       {"id": "b-combos", "type": "extra", "libelle": "Calculer les combinaisons", "calcul": "beam.combos", "titre": "Combinaisons"}, ouvert=False),
                groupe("Eurocode 3 simplifié",
                       liste("na", "Annexe nationale", ["EN", "FR", "autre"], etiquettes=["Valeurs recommandées de l'EN", "France (NF EN 1993-1-1/NA)", "Autre : saisir γM0 et γM1"]),
                       nb("gM0", "γM0, résistance des sections"), nb("gM1", "γM1, stabilité (déversement)"),
                       nb("Cmy", "Cmy, moment équivalent (flambement)", "", aide="Tableau B.3 de l'EN 1993-1-1 : entre 0,4 et 1. 1 = prudent."),
                       nb("CmLT", "CmLT, moment équivalent (déversement)", "", aide="Entre 0,4 et 1 ; 1 est toujours du côté de la sécurité."),
                       nb("Lcr", "Lcr : longueur entre maintiens latéraux (0 = L)", "m"),
                       nb("LcrF", "Lcr,y : longueur de flambement, plan fort (0 = L)", "m"),
                       nb("C1", "C1 : forme du moment (1 = uniforme, prudent)", "", aide="NCCI SN003 : 1,13 charge uniforme sur appuis simples ; 1,35 charge ponctuelle centrée."),
                       liste("ecsrc", "Efforts de calcul", ["enveloppe", "courant"], etiquettes=["Enveloppe des combinaisons (ELU)", "Dernier calcul (non pondéré, indicatif)"]),
                       {"id": "b-ec3", "type": "extra", "libelle": "Vérifier selon l'Eurocode 3", "calcul": "beam.ec3", "titre": "Eurocode 3"},
                       note="Profilés IPE, HEA, HEB, IPN et sections en I, classes 1 à 3, fy = Re. Non vérifiés : voilement sous charges concentrées, flexion déviée, ELS, classe 4. Seules γM0 et γM1 sont paramétrables.",
                       ouvert=False),
                groupe("Fatigue (Goodman)", nb("fR", "R = σmin / σmax (−1 alterné, 0 répété)", ""),
                       nb("fSd", "σD : limite d'endurance connue (0 = estimer 0,5·Rm, acier)", "MPa", 0.0, aide="Valeur d'essai du matériau (cours de fatigue de Master, p. 44 et 84). L'estimation 0,5·Rm ne vaut que pour l'acier."),
                       nb("fKf", "Kf (0 = Kf = Kt)", "", 0.0, aide="Coefficient de fatigue en entaille, 1 ≤ Kf ≤ Kt (cours de fatigue de Master, p. 59)."),
                       case("fKfMoy", "Kf aussi appliqué à la contrainte moyenne", "Le cours (p. 95) applique les coefficients d'influence aux amplitudes et aux valeurs moyennes."),
                       nb("fka", "ka (KS du cours) : état de surface", "", aide="Poli 1 ; usiné 0,7 à 0,9 ; laminé 0,6 à 0,8 ; brut de forge 0,4 à 0,6."),
                       nb("fkb", "kb (Ke du cours) : effet de taille", "", aide="d ≤ 8 mm : 1 ; 0,85 à 0,9 pour 10 à 50 mm ; 0,7 à 0,8 au-delà."),
                       {"id": "b-fat", "type": "extra", "libelle": "Vérifier la fatigue", "calcul": "beam.fatigue", "titre": "Fatigue"}, ouvert=False),
                groupe("Charge mobile (convoi d'essieux)",
                       texte("mvP", "Essieux (kN, de gauche à droite)", "F < 0 = vers le bas."), texte("mvE", "Écartement(s) entre essieux (m)"),
                       nb("mvN", "Positions de base du convoi", "", 2, entier=True), case("mvFixed", "Ajouter les charges fixes saisies"),
                       {"id": "b-mob", "type": "extra", "libelle": "Calculer l'enveloppe de la charge mobile", "calcul": "beam.mobile", "titre": "Charge mobile"},
                       ouvert=False),
                groupe("Échanges avec les autres pages",
                       _transfert("section", {"sec": "sec", "beam": "self"}, {"beam": "self"}, libelle="← Importer la section de la page Sections",
                                  aide="Recopie S, Iz, Iy, Ix, Iyz, ky, kz, fibres extrêmes et matériau de la page Sections (à utiliser après l'avoir calculée)."),
                       _transfert("tenseur", {"beam": "self"}, {"ten": "ten"}, libelle="Envoyer le point le plus sollicité vers Tenseurs et critères", ouvrir=["tenseurs", "Ouvrir Tenseurs et critères"],
                                  aide="Transmet l'état de contrainte σxx de la fibre la plus sollicitée, avec le matériau et la sécurité de la poutre."), ouvert=False),
                groupe("Profilé le plus léger", nb("pdef", "Flèche max L / … (0 = ignorée)", "", 0.0, aide="300 impose f ≤ L/300, en plus de Kt·σ ≤ Re/s."),
                       {"id": "b-leger", "type": "extra", "libelle": "Chercher le profilé le plus léger (famille choisie dans Section)", "calcul": "beam.leger", "titre": "Profilé le plus léger"},
                       ouvert=False),
            ],
            "note": "Pour une structure en 3D : onglet Ossature 3D.",
        },
        "ossature": {
            "titre": "Ossature 3D", "defaut": {**ossature3d._tables_exemple(next(iter(ossature3d.exemples(dm()))), dm()), "pp": False, "piece": 0, "ampli": 0},
            "apercu": False, "auto": False, "dossier": False, "exemples": list(ossature3d.exemples(dm())), "paquets": ["scipy", "shapely"],
            "groupes": [
                groupe("Nœuds et pièces",
                       tableau("noeuds", "Nœuds (mm)", [col("id", "id", defaut=1, entier=True), col("x", "x (mm)"), col("y", "y (mm)"), col("z", "z (mm)"),
                                                          col("appui", "Appui", "liste", ossature3d.APPUIS, "libre"), col("ddl", "DDL perso", "texte", defaut="")],
                               aide="Appui « perso » : 6 chiffres 0/1 pour ux uy uz θx θy θz (1 = bloqué)."),
                       tableau("pieces", "Pièces", [col("id", "id", defaut=1, entier=True), col("debut", "Nœud début", defaut=1, entier=True), col("fin", "Nœud fin", defaut=2, entier=True),
                                                    col("materiau", "Matériau", "liste", noms, "S235"), col("section", "Section", "liste", ossature3d.SECTIONS, "rond"),
                                                    col("dimensions", "Dimensions (mm)", "texte", defaut="d=40"), col("beta", "β (°)"),
                                                    col("liaison_debut", "Liaison début", "liste", ossature3d.LIAISONS, "rigide"), col("liaison_fin", "Liaison fin", "liste", ossature3d.LIAISONS, "rigide")],
                               aide="Dimensions : " + " ; ".join(f"{k} : « {v} »" for k, v in ossature3d.EXEMPLES_DIM.items()))),
                groupe("Charges (repère global)",
                       tableau("charges_nodales", "Charges nodales", [col("noeud", "Nœud", defaut=1, entier=True), *[col(c, f"{c} (N)") for c in ("Fx", "Fy", "Fz")], *[col(c, f"{c} (N·m)") for c in ("Mx", "My", "Mz")]]),
                       tableau("charges_reparties", "Charges réparties", [col("piece", "Pièce", defaut=1, entier=True), *[col(c, f"{c} (N/m)") for c in ("qx", "qy", "qz")]]),
                       case("pp", "Poids propre (ρ·g·A selon −Z, g = 9,81 m/s²)")),
                groupe("Affichage", nb("ampli", "Amplification de la déformée (0 = automatique)", "", 0.0), nb("piece", "Pièce des efforts internes (0 = première)", "", 0.0, entier=True), ouvert=False),
            ],
            "note": "Poutres d'Euler-Bernoulli (déformation d'effort tranchant négligée). Repère local : x de début vers fin, z vertical pour une pièce horizontale (Iy = axe fort). β tourne la section autour de son axe. Exemples : " + " ; ".join(f"{n} : {t}" for n, t in ossature3d.EXPLICATIONS.items()),
        },
        "truss": {
            "titre": "Treillis", "defaut": loadExample("Tr"), "apercu": True, "auto": False, "dossier": True,
            "exemples": exampleNames("Tr"), "paquets": ["scipy", "shapely"],
            "suites": {"mat": {"calcul": "materiau", "champs": ["E", "Re"]}},
            "groupes": [
                groupe("Matériau et section", liste("mat", "Matériau", noms), nb("E", "E", "GPa"), nb("Re", "Re", "MPa", 0.0),
                       nb("S", "S, aire d'une barre", "mm²", 0.0),
                       nb("Imin", "Imin, moment quadratique minimal d'une barre (0 = flambage non vérifié)", "mm⁴", 0.0,
                          aide="Toutes les barres ont la même section. Sert au flambage d'Euler des barres comprimées (barre articulée aux deux bouts). Tube Ø60 × 3 : environ 200 000 mm⁴."),
                       nb("s", "Coefficient de sécurité s", "", 0.0, aide="On exige σ ≤ Re / s et |N| ≤ Pcr / s (typiquement 1,5 à 3)."),
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


ORIGINES_SECTION = {"catalogue": "Profilé du catalogue", "forme": "Forme paramétrée (mes dimensions)", "tige": "Tige filetée",
                    "sections": "Section de la page Sections", "saisie": "Valeurs saisies à la main"}
# section de départ de Poutres : l'exemple (IPE 300 du catalogue), puis des dimensions prêtes pour chaque forme
DEFAUT_SECTION = {"secSrc": "catalogue", "secForme": "disque", "tigeM": "M10", "tigeD": "noyau",
                  "f_b": 20.0, "f_h": 40.0, "f_D": 20.0, "f_d": 16.0, "f_B": 40.0, "f_H": 60.0, "f_t": 3.0, "f_tw": 5.0, "f_tf": 8.0}


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
                groupe("Échanges avec les autres pages",
                       _transfert("section", {"sec": "self", "beam": "beam", "fla": "fla"}, {"beam": "beam", "fla": "fla"}, libelle="Envoyer la section vers Poutres et Flambage", ouvrir=["poutres", "Ouvrir Poutres"],
                                  aide="Poutres reçoit S, inerties, ky, kz, fibres extrêmes et matériau ; Flambage reçoit S, Iz, Iy, E et Re (moments principaux si Iyz ≠ 0)."),
                       nb("s0", "Abscisse s sur la poutre", "m", aide="Position de la coupure dans la page Poutres (de 0 à L)."),
                       _transfert("efforts_s", {"beam": "beam", "cible": "self"}, {"cible": "self"}, {"key": "Sec", "mode": "abscisse"}, calcul="transfert.efforts", libelle="← Lire les efforts de la poutre en s"),
                       _transfert("efforts_max", {"beam": "beam", "cible": "self"}, {"cible": "self"}, {"key": "Sec", "mode": "max"}, calcul="transfert.efforts", libelle="← Lire les efforts au point le plus sollicité"), ouvert=False),
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
            **commun, "titre": "Cisaillement", "defaut": {**loadExample("Cis"), "S": 200.0, "Lk": 60.0}, "caches": ["section"],  # exemple du site : admissible
            "suites": {"mat": {"calcul": "materiau", "champs": ["Re", "G"]}},
            "groupes": [
                groupe("Section pour Jourawski",
                       _transfert("section_seule", {"sec": "sec"}, {"cible": "self"}, libelle="← Prendre la section de la page Sections",
                                  aide="Sans cela, Jourawski utilise la section de l'exemple (IPE 200)."), ouvert=False),
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
            **commun, "titre": "Torsion", "defaut": {**loadExample("Tor"), "D": 65.0},  # exemple du site : admissible
            "suites": {"mat": {"calcul": "materiau", "champs": ["G", "Re"]}},
            "groupes": [groupe("Arbre circulaire", nb("Mt", "Mt", "kN·m"), nb("D", "D", "mm", 0.0), nb("d", "d, alésage (0 = plein)", "mm", 0.0),
                               nb("L", "L", "m", 0.0), liste("mat", "Matériau", noms), nb("G", "G", "GPa"), nb("Re", "Re", "MPa"),
                               liste("crit", "Critère (τe)", CRITERES[0], etiquettes=CRITERES[1]), nb("s", "Coefficient de sécurité s", ""),
                               nb("Kt", "Kt", "", 1.0), nb("thetaAdm", "θ admissible (0 = sans)", "°/m", 0.0))],
        },
        "fle": {
            **commun, "titre": "Flexion", "defaut": loadExample("Fle"), "caches": ["section"],
            "suites": {"mat": {"calcul": "materiau", "champs": ["Re"]}},
            "groupes": [
                groupe("Efforts dans la section étudiée", nb("N", "N : traction > 0", "kN"), nb("Mfz", "Mfz : plan (x,y)", "kN·m"),
                       nb("Mfy", "Mfy : plan (x,z)", "kN·m"),
                       note="Section de l'exemple ; dans l'application de bureau, celle de la page Sections et les efforts de la poutre."),
                groupe("Reprendre la section et les efforts",
                       _transfert("section_seule", {"sec": "sec"}, {"cible": "self"}, libelle="← Prendre la section de la page Sections"),
                       nb("s0", "Abscisse s sur la poutre", "m", aide="Position de la coupure dans la page Poutres (de 0 à L)."),
                       _transfert("efforts_s", {"beam": "beam", "cible": "self"}, {"cible": "self"}, {"key": "Fle", "mode": "abscisse"}, calcul="transfert.efforts", libelle="← Lire les efforts de la poutre en s"),
                       _transfert("efforts_max", {"beam": "beam", "cible": "self"}, {"cible": "self"}, {"key": "Fle", "mode": "max"}, calcul="transfert.efforts", libelle="← Lire les efforts au point le plus sollicité"), ouvert=False),
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
                       _transfert("section", {"sec": "sec"}, {"fla": "self"}, libelle="← Importer depuis Sections", aide="Recopie S, Iz, Iy et le matériau de la page Sections (à calculer d'abord)."),
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
                groupe("Reprendre l'état de la poutre",
                       _transfert("tenseur", {"beam": "beam"}, {"ten": "self"}, libelle="← Prendre le point le plus sollicité de la poutre",
                                  aide="σxx de la fibre la plus sollicitée de la page Poutres, avec son matériau et sa sécurité."), ouvert=False),
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


formulaires_de(lambda: exports.marquer(avec_sources(_formulaires())))
formulaires_de(lambda: exports.marquer(avec_sources(_formulaires_rdm())))

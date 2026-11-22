"""Excel de validation : un classeur simple où le calcul est refait par des formules Excel, à côté de MecaStruct.

Feuilles : « Lisez-moi », « Données » (cellules modifiables), « Calcul » (formule Excel, valeur de MecaStruct, écart),
« Critères » (coefficient de sécurité, taux et verdict en formules), puis les tableaux de résultats (valeurs).

Les formules sont écrites ici, calcul par calcul (FORMULES). Dans un gabarit, {id} désigne une donnée et [cle] une
ligne déjà calculée. Seuls ces gabarits deviennent des formules : tout texte venant de la saisie ou des résultats
passe par project_io._neutre (aucune injection de formule). Poutres, treillis, ossature, sections, tenseurs, Hooke,
jauges, ajustements et paliers ne sont pas refaits dans Excel : leurs valeurs sont celles de MecaStruct.
"""

import io
import math
import re

import pandas as pd

from mecastruct import __version__
from mecastruct.services import export_texte, project_io

TOLERANCE = 1e-3  # écart relatif accepté entre la formule Excel et MecaStruct


# ------------------------------------------------------------------------------------------- formules par calcul
# Chaque fonction rend (extras, lignes) ou None si le cas saisi n'est pas refait dans Excel.
# extras : (id, libellé, valeur, unité), valeurs lues par MecaStruct dans une table ou un catalogue.
# lignes : (clé, libellé, formule en clair, unité, gabarit Excel, valeur de MecaStruct).


def _tra(s, r, _dm):
    if s.get("varS"):
        return None
    return [], [
        ("sn", "Contrainte nominale σ", "N / S0", "MPa", "{N}*1000/{S0}", r["sigmaNom"] / 1e6),
        ("sm", "Contrainte maximale σmax", "Kt · σ", "MPa", "{Kt}*[sn]", r["sigmaMax"] / 1e6),
        ("sa", "Contrainte admissible σadm", "Re / s", "MPa", "{Re}/{s}", r["sigmaAdm"] / 1e6),
        ("dl", "Allongement ΔL", "N·L0 / (E·S0) + α·ΔT·L0", "mm", "{N}*{L0}*1000/({E}*{S0})+{alpha}*0.000001*{dT}*{L0}*1000",
         r["dL"]["analytique"] * 1e3),
    ]  # fmt: skip


def _cis(s, r, _dm):
    sh = r["shear"]
    return [], [
        ("tm", "Contrainte moyenne τmoy", "T / S", "MPa", "{T}*1000/{S}", sh["tauMoy"] / 1e6),
        ("tx", "Contrainte maximale τmax", "k · τmoy", "MPa", "{k}*[tm]", sh["tauMax"] / 1e6),
        ("te", "Limite élastique en cisaillement τe", "Re/2 (Tresca) ou Re/√3 (Von Mises)", "MPa",
         'IF({crit}="Tresca",{Re}/2,{Re}/SQRT(3))', sh["tauE"] / 1e6),
        ("ta", "Contrainte admissible τadm", "τe / s", "MPa", "[te]/{s}", sh["tauAdm"] / 1e6),
        ("ga", "Glissement γ", "τmoy / G", "rad", "[tm]/({G}*1000)", sh["gamma"]),
        ("pm", "Pression de matage P", "F / S matée", "MPa", "{Fm}*1000/{Sm}", r["bearing"]["P"] / 1e6),
    ]  # fmt: skip


def _tor(s, r, _dm):
    return [], [
        ("ix", "Moment quadratique polaire Ix", "π (D⁴ − d⁴) / 32", "mm⁴", "PI()*({D}^4-{d}^4)/32", r["Ix"] * 1e12),
        ("tn", "Contrainte nominale τ", "Mt · (D/2) / Ix", "MPa", "{Mt}*1000000*({D}/2)/[ix]", r["tauMaxNom"] / 1e6),
        ("tx", "Contrainte maximale τmax", "Kt · τ", "MPa", "{Kt}*[tn]", r["tauMax"] / 1e6),
        ("ta", "Contrainte admissible τadm", "τe / s, τe = Re/2 (Tresca) ou Re/√3 (Von Mises)", "MPa",
         'IF({crit}="Tresca",{Re}/2,{Re}/SQRT(3))/{s}', r["tauAdm"] / 1e6),
        ("th", "Angle unitaire θ", "Mt / (G · Ix)", "rad/m", "{Mt}*1000000/({G}*[ix])", r["theta"]),
        ("td", "Angle unitaire θ", "θ · 180 / π", "°/m", "[th]*180/PI()", math.degrees(r["theta"])),
        ("ph", "Angle de torsion φ", "θ · L", "rad", "[th]*{L}", r["phi"]["analytique"]),
    ]  # fmt: skip


def _fle(s, r, _dm):
    b, P = r["bend"], r["P"]
    if b.get("usedGeneralFormula"):
        return None
    traction = abs(b["sigmaMaxTraction"]) >= abs(b["sigmaMaxCompression"])
    y, z = (b["locMaxTraction"] if traction else b["locMaxCompression"])[:2]
    sig = b["sigmaMaxTraction"] if traction else b["sigmaMaxCompression"]
    extras = [("xS", "Aire de la section S", P["S"] * 1e6, "mm²"), ("xIz", "Moment quadratique Iz", P["Iz"] * 1e12, "mm⁴"),
              ("xIy", "Moment quadratique Iy", P["Iy"] * 1e12, "mm⁴"),
              ("xy", "y du point le plus sollicité (depuis G)", float(y) * 1e3, "mm"),
              ("xz", "z du point le plus sollicité (depuis G)", float(z) * 1e3, "mm")]  # fmt: skip
    return extras, [
        ("sg", "Contrainte σ au point le plus sollicité", "N/S − Mfz·y/Iz + Mfy·z/Iy", "MPa",
         "{N}*1000/{xS}-{Mfz}*1000000*{xy}/{xIz}+{Mfy}*1000000*{xz}/{xIy}", sig / 1e6),
        ("sk", "Contrainte maximale Kt·|σ|", "Kt · |σ|", "MPa", "{Kt}*ABS([sg])", b["sigmaMaxKt"] / 1e6),
        ("sa", "Contrainte admissible σadm", "Re / s", "MPa", "{Re}/{s}", b["sigmaAdm"] / 1e6),
    ]  # fmt: skip


def _fla(s, r, _dm):
    a = r["analysis"]
    extras = [("xk", "Coefficient de longueur de flambement (L' = coefficient × L)", a["coefLp"], ""),
              ("xc", "Élancement en dessous duquel il n'y a pas de flambage", a["lambdaCompression"], "")]
    return extras, [
        ("im", "Moment quadratique minimal Imin", "min(Iz, Iy)", "mm⁴", "MIN({Iz},{Iy})", a["Imin"] * 1e12),
        ("rg", "Rayon de giration r", "√(Imin / S)", "mm", "SQRT([im]/{S})", a["rmin"] * 1e3),
        ("lp", "Longueur de flambement L'", "coefficient × L", "m", "{xk}*{L}", a["Lp"]),
        ("la", "Élancement λ", "L' / r", "", "[lp]*1000/[rg]", a["lambda"]),
        ("ll", "Élancement limite λlim", "π √(E / Re)", "", "PI()*SQRT({E}*1000/{Re})", a["lambdaLim"]),
        ("pe", "Charge critique d'Euler PE", "π² E Imin / L'²", "kN", "PI()^2*{E}*1000*[im]/([lp]*1000)^2/1000", a["PE"] / 1e3),
        ("pr", "Charge critique de Rankine PR", "Re·S / (1 + (λ/λlim)²)", "kN", "{Re}*{S}/(1+([la]/[ll])^2)/1000", a["PR"] / 1e3),
        ("pc", "Charge critique retenue Pcrit", "Euler si λ ≥ λlim, Rankine sinon, Re·S si λ très petit", "kN",
         "IF([la]>=[ll],[pe],IF([la]>={xc},[pr],{Re}*{S}/1000))", a["Pcrit"] / 1e3),
        ("pa", "Charge admissible Padm", "Pcrit / s", "kN", "[pc]/{s}", a["Padm"] / 1e3),
    ]  # fmt: skip


def _fre(s, r, dm):
    Re = dm.getMaterial(s["matArbre"])["Re"] / 1e6
    extras = [("xpn", "Pression au serrage normalisé mini (calculée par MecaStruct)", r["pMinNorm"], "MPa"),
              ("xpx", "Pression au serrage normalisé maxi (calculée par MecaStruct)", r["pMax"], "MPa"),
              ("xRe", f"Re de l'arbre ({s['matArbre']})", Re, "MPa")]
    return extras, [
        ("R", "Effort à transmettre R", "s · √((2C/d)² + Fa²)", "N", "{s}*SQRT((2*{C}*1000/{d})^2+{Fa}^2)", r["R"]),
        ("p", "Pression mini nécessaire p", "R / (f · π · d · L)", "MPa", "[R]/({f}*PI()*{d}*{L})", r["pMin"]),
        ("ct", "Couple transmissible au serrage mini", "p mini normalisée · f · π · d · L · d/2", "N·m",
         "{xpn}*{f}*PI()*{d}*{L}*{d}/2/1000", r["couple"]),
        ("sa", "Contrainte équivalente de l'arbre", "2 p maxi / (1 − (di/d)²)", "MPa", "2*{xpx}/(1-({di}/{d})^2)", r["sigmaArbre"]),
        ("ca", "Coefficient de sécurité de l'arbre", "Re / σ", "", "{xRe}/[sa]", r["sArbre"]),
    ]  # fmt: skip


def _rlt(s, r, _dm):
    if s["Fr"] <= 0 or s["N"] <= 0:
        return None
    extras = [("xe", "e (table ou saisie)", r["e"], ""), ("xX", "X", r["X"], ""), ("xY", "Y", r["Y"], ""),
              ("xa", "a1, coefficient de fiabilité", r["a1"], "")]
    return extras, [
        ("P", "Charge équivalente P", "Fr si Fa/Fr ≤ e, sinon X·Fr + Y·Fa", "N", "IF({Fa}/{Fr}<={xe},{Fr},{xX}*{Fr}+{xY}*{Fa})", r["P"]),
        ("L", "Durée L10", "(C/P)^n, n = 3 (billes) ou 10/3 (rouleaux)", "millions de tours", '({C}/[P])^IF({type}="billes",3,10/3)', r["L10"]),
        ("H", "Durée L10h", "L10 · 10⁶ / (60 · N)", "h", "[L]*1000000/(60*{N})", r["L10h"]),
        ("F", "Durée corrigée Lnh", "a1 · L10h", "h", "{xa}*[H]", r["Lnh"]),
    ]  # fmt: skip


def _eng(s, r, dm):
    Re = dm.getMaterial(s["materiau"])["Re"] / 1e6
    extras = [("xRe", f"Re du pignon ({s['materiau']})", Re, "MPa")]
    if "alpha" in s:
        alpha = "RADIANS({alpha})"  # donnée modifiable du classeur
    else:  # ancien fichier de projet sans angle de pression : 20°
        extras.append(("xAl", "Angle de pression α", r["alpha"], "°"))
        alpha = "RADIANS({xAl})"
    return extras, [
        ("r", "Rapport de transmission", "−Z1 / Z2", "", "-{Z1}/{Z2}", r["r"]),
        ("a", "Entraxe a", "m (Z1 + Z2) / 2", "mm", "{m}*({Z1}+{Z2})/2", r["a"]),
        ("d", "Diamètre primitif du pignon d1", "m · Z1", "mm", "{m}*{Z1}", r["d"]),
        ("C", "Couple au pignon C1", "30 P / (π N)", "N·m", "30*{P}/(PI()*{N})", r["C1"]),
        ("t", "Effort tangentiel Ft", "2 C1 / d1", "N", "2*[C]*1000/[d]", r["Ft"]),
        ("f", "Effort radial Fr", "Ft · tan α", "N", f"[t]*TAN({alpha})", r["Fr"]),
        ("n", "Effort normal Fn", "Ft / cos α", "N", f"[t]/COS({alpha})", r["Fn"]),
        ("s", "Contrainte en pied de dent σ", "54 Ft / (π² k m²)", "MPa", "54*[t]/(PI()^2*{k}*{m}^2)", r["sigma"]),
        ("R", "Résistance pratique Rpe", "Re / s", "MPa", "{xRe}/{s}", r["Rpe"]),
        ("m", "Module minimal", "√(54 Ft / (π² k Rpe))", "mm", "SQRT(54*[t]/(PI()^2*{k}*[R]))", r["mMini"]),
    ]  # fmt: skip


def _frn(s, r, _dm):
    return [], [
        ("p", "Couple de freinage, pression constante", "n f F (2/3)(Re³ − Ri³)/(Re² − Ri²)", "N·m",
         "{n}*{f}*{F}*(2/3)*({Re}^3-{Ri}^3)/({Re}^2-{Ri}^2)/1000", r["Cp"]),
        ("u", "Couple de freinage, usure constante", "n f F (Re + Ri)/2", "N·m", "{n}*{f}*{F}*({Re}+{Ri})/2/1000", r["Cu"]),
    ]  # fmt: skip


def _emb(s, r, _dm):
    return [], [
        ("w", "Vitesse du moteur ω", "2π NM / 60", "rad/s", "2*PI()*{NM}/60", 2 * math.pi * s["NM"] / 60),
        ("a", "Couple d'accélération", "JR · ω / ts", "N·m", "{JR}*[w]/{ts}", r["Cacc"]),
        ("c", "Couple d'embrayage CT", "|CR| + JR · ω / ts", "N·m", "ABS({CR})+[a]", r["CT"]),
        ("e", "Énergie dissipée par manœuvre", "CT · ω · ts / 2", "J", "[c]*[w]*{ts}/2", r["E"]),
        ("p", "Puissance moyenne dissipée", "E · cadence / 3600", "W", "[e]*{cadence}/3600", r["Pmoy"]),
    ]  # fmt: skip


def _mot(s, r, _dm):
    return [], [
        ("t", "Couple équivalent thermique C_th", "√(Σ C²·t / Σ t)", "N·m",
         "SQRT(({Ca}^2*{ta}+{Cc}^2*{tc}+{Cfr}^2*{tfr})/({ta}+{tc}+{tfr}))", r["Cth"]),
        ("p", "Couple de pointe", "max |C| des phases de durée non nulle", "N·m",
         "MAX(IF({ta}>0,ABS({Ca}),0),IF({tc}>0,ABS({Cc}),0),IF({tfr}>0,ABS({Cfr}),0))", r["Cpointe"]),
        ("j", "Inertie ramenée à l'arbre moteur", "Jm + Js / rs²", "kg·m²", "{Jm}+{Js}/{rs}^2", r["J"]),
    ]  # fmt: skip


def _truss(s, r, _dm):
    c, tsol = r["check"], r["tsol"]
    if c["iSigma"] is None:
        return None
    k = c["iSigma"]
    extras = [("xN", f"Effort normal N de la barre {k + 1} (le plus grand, solveur MecaStruct)", abs(float(tsol["N"][k])) / 1e3, "kN")]
    lignes = [
        ("sg", f"Contrainte σ de la barre {k + 1}", "|N| / S", "MPa", "{xN}*1000/{S}", c["sigma"][k] / 1e6),
        ("sa", "Contrainte admissible σadm", "Re / s", "MPa", "{Re}/{s}", c["sigmaAdm"] / 1e6),
    ]  # fmt: skip
    if c["iFlambage"] is not None:
        f = c["iFlambage"]
        extras += [("xNc", f"Effort de compression de la barre {f + 1} (le plus critique, solveur MecaStruct)", abs(float(tsol["N"][f])) / 1e3, "kN"),
                   ("xLc", f"Longueur de la barre {f + 1}", float(tsol["L0"][f]), "m")]  # fmt: skip
        lignes += [
            ("pc", f"Charge critique d'Euler de la barre {f + 1}", "π² E Imin / L²", "kN", "PI()^2*{E}*1000*{Imin}/({xLc}*1000)^2/1000", c["Pcr"][f] / 1e3),
            ("pa", "Charge admissible au flambage", "Pcr / s", "kN", "[pc]/{s}", c["Pcr"][f] / s["s"] / 1e3),
        ]
    return extras, lignes


FORMULES = {"truss": _truss, "tra": _tra, "cis": _cis, "tor": _tor, "fle": _fle, "fla": _fla, "fre": _fre, "rlt": _rlt, "eng": _eng,
            "frn": _frn, "emb": _emb, "mot": _mot}  # fmt: skip


def formules(ident: str, saisie: dict, resultat: dict, dm) -> tuple[list, list] | None:
    """(extras, lignes) du calcul `ident`, ou None s'il n'est pas refait dans Excel (ou si le cas ne s'y prête pas)."""
    f = FORMULES.get(ident)
    if f is None:
        return None
    try:
        return f(saisie, resultat, dm)
    except (KeyError, TypeError, ValueError, IndexError):
        return None


# ------------------------------------------------------------------------------------------------------ classeur

_REF = re.compile(r"\{(\w+)\}|\[(\w+)\]")


def traduire(gabarit: str, donnees: dict[str, str], calculs: dict[str, str]) -> str:
    """Gabarit → formule Excel : {id} et [cle] remplacés par leurs cellules."""
    return "=" + _REF.sub(lambda m: donnees[m.group(1)] if m.group(1) else calculs[m.group(2)], gabarit)


def _valeur(v):
    """Valeur d'une cellule : nombre tel quel, texte neutralisé (jamais une formule)."""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, (int, float)):
        return None if isinstance(v, float) and not math.isfinite(v) else v
    if hasattr(v, "item"):  # nombre numpy
        return _valeur(v.item())
    return project_io._neutre("" if v is None else str(v))


_NOMBRE = re.compile(r"^[-−+]?\d+(\.\d+)?(e[-+]?\d+)?$")


def _cellule(v):
    """Cellule d'un tableau de résultats : un nombre écrit en texte par le calcul (« 159.155 ») redevient un nombre."""
    if isinstance(v, str) and _NOMBRE.match(v.strip()):
        return float(v.strip().replace("−", "-"))
    return _valeur(v)


def classeur(titre: str, formulaire: dict, saisie: dict, sortie: dict, crit: list[dict], refait: tuple | None) -> bytes:
    """Classeur de validation (.xlsx). `sortie` : {status, ok, tables} ; `refait` : résultat de formules() ou None."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    gras, saisie_fond = Font(bold=True), PatternFill("solid", fgColor="FFF2CC")
    entete_fond = PatternFill("solid", fgColor="E4DFF5")
    wb = Workbook()

    def feuille(nom, entetes, largeurs):
        ws = wb.create_sheet(nom)
        ws.append(entetes)
        for c in ws[1]:
            c.font, c.fill = gras, entete_fond
        for lettre, w in zip("ABCDEFGHIJ", largeurs, strict=False):
            ws.column_dimensions[lettre].width = w
        ws.freeze_panes = "A2"
        return ws

    # --- Lisez-moi
    lm = wb.active
    lm.title = "Lisez-moi"
    lm.column_dimensions["A"].width = 110
    ok = sortie.get("ok")
    notes = [
        f"MecaStruct RdM {__version__} - {titre}",
        "Verdict de MecaStruct : " + ("vérifié" if ok is True else "NON vérifié" if ok is False else "sans verdict"),
        str(sortie.get("status", "")),
        "",
        "Feuille « Données » : les cellules jaunes sont vos données. Vous pouvez les modifier, les formules suivent.",
        ("Feuille « Calcul » : chaque grandeur est refaite par une formule Excel (colonne C) et comparée à la valeur de "
         "MecaStruct (colonne D). « OK » = écart relatif inférieur à 0,1 %." if refait else
         "Ce calcul passe par un solveur qui n'est pas refait dans Excel : les valeurs des feuilles de résultats sont "
         "celles de MecaStruct. Le dossier de validation du site refait chaque grandeur à la main."),
        "Feuille « Critères » : coefficient de sécurité, taux de travail et verdict sont des formules Excel.",
        "Si vous modifiez une donnée, la colonne « MecaStruct » garde l'ancien résultat : relancez le calcul sur le site.",
        "",
        "Outil pédagogique et d'aide au pré-dimensionnement, fourni sans garantie : vérifiez les résultats avant tout usage réel.",
    ]  # fmt: skip
    for n in notes:
        lm.append([_valeur(n)])
    lm["A1"].font = Font(bold=True, size=14)
    for r in lm.iter_rows():
        r[0].alignment = Alignment(wrap_text=True, vertical="top")

    # --- Données
    wd = feuille("Données", ["Donnée", "Valeur", "Unité", "Rubrique"], [58, 18, 14, 40])
    cellules: dict[str, str] = {}
    lignes = [(d["id"], d["libelle"], d["brut"], d["unite"], d["groupe"]) for d in export_texte.donnees(formulaire, saisie)]
    extras, calculs = refait or ([], [])
    lignes += [(i, lib, v, u, "Valeurs reprises de MecaStruct (tables, catalogue)") for i, lib, v, u in extras]
    for ident, lib, v, unite, groupe in lignes:
        wd.append([_valeur(lib), _valeur(v), _valeur(unite), _valeur(groupe)])
        wd.cell(wd.max_row, 2).fill = saisie_fond
        cellules[ident] = f"'Données'!$B${wd.max_row}"
    for ident, v in saisie.items():  # champs sans ligne dans le formulaire affiché (cachés par une condition)
        if ident not in cellules and isinstance(v, (int, float, str)) and not isinstance(v, bool):
            wd.append([_valeur(ident), _valeur(v), "", "Autres champs de l'étude"])
            cellules[ident] = f"'Données'!$B${wd.max_row}"

    # --- Calcul
    if calculs:
        wc = feuille("Calcul", ["Grandeur", "Formule", "Excel", "MecaStruct", "Unité", "Écart relatif", "Contrôle"],
                     [44, 50, 16, 16, 16, 14, 12])  # fmt: skip
        faits: dict[str, str] = {}
        for cle, lib, clair, unite, gabarit, valeur in calculs:
            n = wc.max_row + 1
            wc.append([_valeur(lib), _valeur(clair), traduire(gabarit, cellules, faits), _valeur(float(valeur)), _valeur(unite),
                       f"=IF(D{n}=0,ABS(C{n}),ABS(C{n}-D{n})/ABS(D{n}))", f'=IF(F{n}<{TOLERANCE},"OK","ÉCART")'])  # fmt: skip
            wc.cell(n, 6).number_format = "0.00E+00"
            faits[cle] = f"Calcul!$C${n}"

    # --- Critères
    wk = feuille("Critères", ["Mode de ruine", "Valeur", "Limite", "Unité", "Sens", "s demandé", "s obtenu", "Taux de travail", "Verdict"],
                 [50, 14, 14, 10, 8, 12, 12, 16, 18])  # fmt: skip
    for c in crit:
        n = wk.max_row + 1
        wk.append([_valeur(c["mode"]), c["valeur"], c["limite"], _valeur(c["unite"]), c["sens"], c["s_demande"],
                   f'=IF(E{n}="max",C{n}*F{n}/B{n},B{n}*F{n}/C{n})', f'=IF(E{n}="max",B{n}/C{n},C{n}/B{n})',
                   f'=IF(H{n}<=1,"Admissible","Non admissible")'])  # fmt: skip
        wk.cell(n, 8).number_format = "0.0%"
        wk.cell(n, 7).number_format = "0.00"
    if not crit:
        wk.append(["Ce calcul ne compare pas de valeur à une limite."])
    else:
        wk.append([])
        wk.append(["Sens « max » : la valeur doit rester sous la limite ; « min » : au-dessus. s obtenu = limite × s demandé / valeur."])

    # --- Tableaux saisis et résultats (valeurs)
    tables = {**{f"Saisie {n}": t for n, t in export_texte.tableaux_saisie(formulaire, saisie).items()},
              **{n: t for n, t in (sortie.get("tables") or {}).items() if isinstance(t, pd.DataFrame)}}  # fmt: skip
    for nom, t in project_io.resultSheets("", {"tables": tables}).items():
        if nom in wb.sheetnames:
            nom = (nom[:29] + "_2")
        ws = feuille(nom, [_valeur(str(c)) for c in t.columns], [22] * 10)
        for r in t.itertuples(index=False):
            ws.append([_cellule(v) for v in r])

    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()

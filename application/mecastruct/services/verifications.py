"""Vérifications indépendantes : MecaStruct contre des formules fermées de manuel, écrites en clair ici.

Chaque ligne compare deux nombres :
- `valeur_cible` : calculée dans ce module, à la main, par la formule de manuel donnée dans `formule` (aucune valeur
  n'est tirée d'une norme ni de la mémoire : seulement des formules fermées et des données d'entrée choisies ici) ;
- `valeur_calculee` : rendue par le vrai moteur de MecaStruct (`core/`), appelé comme le font les pages.
`ecart` est l'écart relatif |calculée − cible| / |cible| ; la ligne est `ok` quand il ne dépasse pas `tolerance`.

Tolérances : 1e-9 relatif pour tous les cas. Les moteurs portent des calculs en arithmétique flottante double (écarts
observés de l'ordre de 1e-15) ; 1e-9 laisse la marge des intégrations numériques (quadrature de la traction et de la
torsion) sans jamais cacher un écart de formule. Aucune tolérance n'est plus large que 1e-6.

Module sans Qt ni réseau, partagé par le site (pont/outils.py) et le bureau (bureau/pages/limites.py). Les cas ne se
calculent qu'à l'appel de `verifier()` : rien n'est fait à l'import. Un cas dont le moteur échoue donne une ligne
rouge (ok = False, `erreur` renseignée), jamais une exception.
"""

from __future__ import annotations

import math
from collections.abc import Callable

# Données d'entrée communes aux poutres (acier : E = 210 GPa, valeur du projet ; Iz = 8e-6 m⁴, poutre des tests).
E_ACIER = 210e9
G_ACIER = 80e9
IZ = 8e-6
EI = E_ACIER * IZ

TOLERANCE = 1e-9
REF_RDM = "Formule de manuel de résistance des matériaux"
REF_STATIQUE = "Équilibre statique (calcul à la main)"
REF_EULER = "Formule de manuel : charge critique d'Euler"
REF_MOHR = "Formule de manuel : cercle de Mohr, état plan de contraintes"
REF_HOOKE = "Formule de manuel : loi de Hooke isotrope"
REF_JAUGES = "Formule de manuel d'extensométrie"


# ----------------------------------------------------------------------------------------------- affichage


def formater(x: float, chiffres: int = 6) -> str:
    """Nombre à la française avec `chiffres` chiffres significatifs : « 1 586,98 », « 1,2·10⁻⁵ »."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    if x == 0:
        return "0"
    if math.isinf(x):
        return "∞" if x > 0 else "−∞"
    t = format(float(x), f".{chiffres}g")
    if "e" in t:
        mantisse, _, exposant = t.partition("e")
        n = int(exposant)
        sup = str(abs(n)).translate(str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹"))
        return (mantisse.replace(".", ",") + "·10" + ("⁻" if n < 0 else "") + sup).replace("-", "−")
    entier, _, dec = t.lstrip("-").partition(".")
    entier = f"{int(entier):,}".replace(",", " ")
    return ("−" if t.startswith("-") else "") + entier + ("," + dec if dec else "")


def _ligne(
    ident: str,
    page: str,
    titre: str,
    donnees: str,
    formule: str,
    reference: str,
    cible: float,
    calculee: float,
    unite: str,
    echelle: float = 1.0,
    tolerance: float = TOLERANCE,
) -> dict:
    """Une ligne de vérification ; `echelle` convertit les deux valeurs (SI) vers l'unité affichée."""
    cible = float(cible) * echelle
    calculee = float(calculee) * echelle
    ecart = abs(calculee - cible) / abs(cible) if cible != 0 else abs(calculee - cible)
    ok = math.isfinite(calculee) and ecart <= tolerance
    return {
        "id": ident,
        "page": page,
        "titre": titre,
        "donnees": donnees,
        "formule": formule,
        "reference": reference,
        "unite": unite,
        "valeur_cible": cible,
        "valeur_calculee": calculee,
        "tolerance": tolerance,
        "ecart": ecart,
        "ok": bool(ok),
        "erreur": "",
        "cible_txt": formater(cible),
        "calculee_txt": formater(calculee),
        "ecart_txt": "0" if ecart == 0 else formater(ecart, 2),
        "tolerance_txt": formater(tolerance, 1),
    }


# ------------------------------------------------------------------------------------------------ poutres


def _modele(L: float, appuis: list[tuple[float, str]]) -> dict:
    """Poutre acier E = 210 GPa, Iz = 8e-6 m⁴ (S, G, ky, kz des tests), sans charge."""
    return {
        "L": L,
        "E": E_ACIER,
        "G": G_ACIER,
        "S": 2e-3,
        "Iz": IZ,
        "Iy": 3e-6,
        "Ix": 1e-6,
        "ky": 5 / 6,
        "kz": 5 / 6,
        "supports": [{"pos": p, "type": t, "name": n} for (p, t), n in zip(appuis, "ABC", strict=False)],
        "pointLoads": [],
        "pointMoments": [],
        "distLoads": [],
    }


def _console() -> list[dict]:
    from mecastruct.core import beam_solver, deflection
    from mecastruct.core.pp import ppEval

    L, P = 2.0, 1000.0
    m = _modele(L, [(0.0, "encastrement")])
    m["pointLoads"] = [{"pos": L, "Fx": 0, "Fy": -P, "Fz": 0, "name": "F"}]
    d = deflection.deflection(m, None)
    sol = beam_solver.solveBeam(m)
    donnees = "console L = 2 m, P = 1 000 N en bout, E = 210 GPa, Iz = 8·10⁻⁶ m⁴"
    p = "Poutres"
    return [
        _ligne("poutre-console-fleche", p, "Console, charge en bout : flèche en bout", donnees,
               "f = P·L³ / (3·E·I)", REF_RDM, P * L**3 / (3 * EI), d["integration"]["fmax"], "mm", 1e3),
        _ligne("poutre-console-rotation", p, "Console, charge en bout : rotation en bout", donnees,
               "α = P·L² / (2·E·I)", REF_RDM, P * L**2 / (2 * EI),
               abs(ppEval(d["integration"]["alphaPP"], L)), "rad"),
        _ligne("poutre-console-moment", p, "Console, charge en bout : moment d'encastrement", donnees,
               "M = P·L", REF_STATIQUE, P * L, abs(sol["reactions"][0]["Mz"]), "N·m"),
        _ligne("poutre-console-reaction", p, "Console, charge en bout : réaction d'encastrement", donnees,
               "R = P", REF_STATIQUE, P, sol["reactions"][0]["Ry"], "N"),
    ]


def _deux_appuis_repartie() -> list[dict]:
    from mecastruct.core import beam_solver, deflection

    L, q = 5.0, 2e4
    m = _modele(L, [(0.0, "rotule"), (L, "appui_simple")])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": -q, "name": "q"}]
    d = deflection.deflection(m, None)
    sol = beam_solver.solveBeam(m)
    donnees = "poutre de L = 5 m sur deux appuis, q = 20 000 N/m sur toute la longueur, E·Iz = 210 GPa × 8·10⁻⁶ m⁴"
    p = "Poutres"
    return [
        _ligne("poutre-2appuis-q-fleche", p, "Deux appuis, charge répartie : flèche maximale", donnees,
               "f = 5·q·L⁴ / (384·E·I)", REF_RDM, 5 * q * L**4 / (384 * EI), d["integration"]["fmax"], "mm", 1e3),
        _ligne("poutre-2appuis-q-moment", p, "Deux appuis, charge répartie : moment maximal", donnees,
               "M = q·L² / 8", REF_RDM, q * L**2 / 8, sol["extrema"]["Mfz"]["max"], "N·m"),
        _ligne("poutre-2appuis-q-reaction", p, "Deux appuis, charge répartie : réaction d'appui", donnees,
               "R = q·L / 2", REF_STATIQUE, q * L / 2, sol["reactions"][0]["Ry"], "N"),
    ]


def _deux_appuis_ponctuelle() -> list[dict]:
    from mecastruct.core import beam_solver, deflection

    L, P = 4.0, 1e4
    m = _modele(L, [(0.0, "rotule"), (L, "appui_simple")])
    m["pointLoads"] = [{"pos": L / 2, "Fx": 0, "Fy": -P, "Fz": 0, "name": "F"}]
    d = deflection.deflection(m, None)
    sol = beam_solver.solveBeam(m)
    donnees = "poutre de L = 4 m sur deux appuis, P = 10 000 N au milieu, E·Iz = 210 GPa × 8·10⁻⁶ m⁴"
    p = "Poutres"
    return [
        _ligne("poutre-2appuis-P-fleche", p, "Deux appuis, charge au milieu : flèche maximale", donnees,
               "f = P·L³ / (48·E·I)", REF_RDM, P * L**3 / (48 * EI), d["integration"]["fmax"], "mm", 1e3),
        _ligne("poutre-2appuis-P-moment", p, "Deux appuis, charge au milieu : moment maximal", donnees,
               "M = P·L / 4", REF_RDM, P * L / 4, sol["extrema"]["Mfz"]["max"], "N·m"),
    ]


def _hyperstatiques() -> list[dict]:
    from mecastruct.core import beam_solver, deflection

    p = "Poutres"
    lignes = []
    L, q = 5.0, 1e3
    m = _modele(L, [(0.0, "encastrement"), (L, "appui_simple")])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": -q, "name": "q"}]
    sol = beam_solver.solveBeam(m)
    donnees = "poutre encastrée en A et appuyée en B, L = 5 m, q = 1 000 N/m (hyperstatique de degré 1)"
    lignes += [
        _ligne("poutre-encastree-appuyee-reaction", p, "Encastrée-appuyée, charge répartie : réaction de l'appui B",
               donnees, "R_B = 3·q·L / 8", "Formule de manuel : poutre hyperstatique (méthode des forces)",
               3 * q * L / 8, sol["reactions"][1]["Ry"], "N"),
        _ligne("poutre-encastree-appuyee-moment", p, "Encastrée-appuyée, charge répartie : moment d'encastrement",
               donnees, "M_A = q·L² / 8", "Formule de manuel : poutre hyperstatique (méthode des forces)",
               q * L**2 / 8, abs(sol["reactions"][0]["Mz"]), "N·m"),
    ]
    L, q = 6.0, 1e4
    m = _modele(L, [(0.0, "encastrement"), (L, "encastrement")])
    m["distLoads"] = [{"a": 0, "b": L, "dir": "y", "coeffs": -q, "name": "q"}]
    sol = beam_solver.solveBeam(m)
    d = deflection.deflection(m, None)
    donnees = "poutre bi-encastrée, L = 6 m, q = 10 000 N/m, E·Iz = 210 GPa × 8·10⁻⁶ m⁴ (hyperstatique de degré 2)"
    lignes += [
        _ligne("poutre-biencastree-moment", p, "Bi-encastrée, charge répartie : moment d'encastrement", donnees,
               "M_A = q·L² / 12", "Formule de manuel : poutre hyperstatique (méthode des forces)",
               q * L**2 / 12, abs(sol["reactions"][0]["Mz"]), "N·m"),
        _ligne("poutre-biencastree-fleche", p, "Bi-encastrée, charge répartie : flèche maximale", donnees,
               "f = q·L⁴ / (384·E·I)", "Formule de manuel : poutre hyperstatique (méthode des forces)",
               q * L**4 / (384 * EI), d["integration"]["fmax"], "mm", 1e3),
    ]
    return lignes


# ------------------------------------------------------------------------------------------------ treillis


def _treillis() -> list[dict]:
    from mecastruct.core import truss_solver

    P, H = 12000.0, 6000.0  # charge verticale vers le bas et horizontale vers +x au nœud 3
    t = truss_solver.solveTruss(
        {
            "nodes": [[0, 0], [6, 0], [3, 4]],
            "bars": [[1, 3], [2, 3]],
            "E": E_ACIER,
            "S": 5e-4,
            "supports": [[True, True], [True, True], [False, False]],
            "loads": [[0, 0], [0, 0], [H, -P]],
        }
    )
    # Barre 1-3 : de (0 ; 0) à (3 ; 4), longueur 5, direction (3/5 ; 4/5) ; barre 2-3 : direction (−3/5 ; 4/5).
    c, s = 3 / 5, 4 / 5
    # Équilibre du nœud 3 (effort N > 0 en traction : la barre tire le nœud vers son autre extrémité) :
    #   x : −c·N1 + c·N2 + H = 0 ;  y : −s·N1 − s·N2 − P = 0   ⇒   N1 = (−P/s + H/c)/2,  N2 = (−P/s − H/c)/2
    n1 = (-P / s + H / c) / 2
    n2 = (-P / s - H / c) / 2
    # Moment des actions extérieures autour du nœud 1 : 6·R_y2 + 3·(−P) − 4·H = 0
    ry2 = (3 * P + 4 * H) / 6
    donnees = "nœuds (0 ; 0), (6 ; 0) appuyés et (3 ; 4) m ; barres 1-3 et 2-3 ; au nœud 3 : H = 6 000 N, P = 12 000 N vers le bas"
    ref = "Méthode des nœuds (calcul à la main)"
    p = "Treillis"
    return [
        _ligne("treillis-effort-barre-1", p, "Treillis à deux barres : effort dans la barre 1-3", donnees,
               "N₁ = (−P/sinα + H/cosα) / 2, cosα = 3/5, sinα = 4/5", ref, n1, t["N"][0], "N"),
        _ligne("treillis-effort-barre-2", p, "Treillis à deux barres : effort dans la barre 2-3", donnees,
               "N₂ = (−P/sinα − H/cosα) / 2", ref, n2, t["N"][1], "N"),
        _ligne("treillis-reaction-appui-2", p, "Treillis à deux barres : réaction verticale du nœud 2", donnees,
               "R_y2 = (3·P + 4·H) / 6 (moment autour du nœud 1)", REF_STATIQUE, ry2, t["reactions"][1][1], "N"),
    ]


# ------------------------------------------------------------------------------------------------ flambage


def _flambage() -> list[dict]:
    from mecastruct.core import buckling

    d, L, Re = 0.02, 1.0, 235e6  # barre ronde pleine Ø 20 mm, 1 m : élancement ≥ 100, donc régime d'Euler
    I = math.pi * d**4 / 64
    S = math.pi * d**2 / 4
    donnees = "barre ronde Ø 20 mm, L = 1 m, E = 210 GPa, Re = 235 MPa, I = π·d⁴/64"
    lignes = []
    for ident, condition, K, nom in (
        ("flambage-euler-articule-articule", "articule-articule", 1.0, "articulé-articulé (K = 1)"),
        ("flambage-euler-encastre-libre", "encastre-libre", 2.0, "encastré-libre (K = 2)"),
        ("flambage-euler-encastre-encastre", "encastre-encastre", 0.5, "encastré-encastré (K = 1/2)"),
    ):
        b = buckling.analyze({"E": E_ACIER, "Re": Re, "S": S, "Iz": I, "Iy": I, "L": L, "condition": condition})
        lignes.append(
            _ligne(ident, "Flambage", f"Charge critique d'Euler, {nom}", donnees,
                   "Pcr = π²·E·I / (K·L)²", REF_EULER, math.pi**2 * E_ACIER * I / (K * L) ** 2, b["Pcrit"], "kN", 1e-3)
        )
    return lignes


def _flambage_ec3() -> list[dict]:
    """Courbes de flambement de l'Eurocode 3 : Φ, χ et Nb,Rd refaits à la main pour trois élancements réduits.

    La barre est choisie pour que λ̄ = √(A·fy/Ncr) soit exactement la valeur voulue : I = A·fy·L² / (π²·E·λ̄²). Les
    facteurs α sont ceux des courbes (a0 0,13 ; a 0,21 ; b 0,34 ; c 0,49 ; d 0,76), choisies ici comme le fait
    l'utilisateur ; le tableau 6.2 qui les attribue aux profilés n'est pas utilisé (à vérifier sur la norme).
    """
    from mecastruct.core import buckling

    A, fy, L = 1e-3, 235e6, 2.0
    npl = A * fy
    ref = "Formule de l'EN 1993-1-1 (6.3.1), refaite à la main ; courbe choisie, tableau 6.2 non utilisé"
    p = "Flambage"
    lignes = []
    # (identifiant, courbe, α, λ̄, nom de la barre)
    for ident, courbe, alpha, lam in (("ec3-b-lambda1", "b", 0.34, 1.0), ("ec3-d-lambda2", "d", 0.76, 2.0)):
        I = npl * L**2 / (math.pi**2 * E_ACIER * lam**2)  # noqa: E741
        e = buckling.eurocode3({"E": E_ACIER, "fy": fy, "A": A, "I": I, "Lcr": L, "curve": courbe, "gM1": 1.0})
        phi = 0.5 * (1 + alpha * (lam - 0.2) + lam**2)
        chi = 1 / (phi + math.sqrt(phi**2 - lam**2))
        donnees = (f"barre A = 1 000 mm², fy = 235 MPa, E = 210 GPa, Lcr = 2 m, I réglée pour λ̄ = {lam:g}, "
                   f"courbe {courbe} (α = {alpha:g}), γM1 = 1")  # fmt: skip
        lignes += [
            _ligne(f"flambage-{ident}-lambda", p, f"Eurocode 3, courbe {courbe} : élancement réduit λ̄", donnees,
                   "λ̄ = √(A·fy / Ncr), Ncr = π²·E·I / Lcr²", ref, lam, e["lambda"], "sans unité"),
            _ligne(f"flambage-{ident}-phi", p, f"Eurocode 3, courbe {courbe} : Φ", donnees,
                   "Φ = 0,5·[1 + α·(λ̄ − 0,2) + λ̄²]", ref, phi, e["Phi"], "sans unité"),
            _ligne(f"flambage-{ident}-chi", p, f"Eurocode 3, courbe {courbe} : coefficient de réduction χ", donnees,
                   "χ = 1 / (Φ + √(Φ² − λ̄²))", ref, chi, e["chi"], "sans unité"),
            _ligne(f"flambage-{ident}-nbrd", p, f"Eurocode 3, courbe {courbe} : résistance Nb,Rd", donnees,
                   "Nb,Rd = χ·A·fy / γM1", ref, chi * npl, e["NbRd"], "kN", 1e-3),
        ]
    # λ̄ ≤ 0,2 : la formule donne χ ≥ 1, on retient χ = 1 et Nb,Rd = A·fy / γM1
    lam, gm = 0.15, 1.2
    I = npl * L**2 / (math.pi**2 * E_ACIER * lam**2)  # noqa: E741
    e = buckling.eurocode3({"E": E_ACIER, "fy": fy, "A": A, "I": I, "Lcr": L, "curve": "a", "gM1": gm})
    donnees = f"même barre, I réglée pour λ̄ = {lam:g} (≤ 0,2), courbe a, γM1 = {gm:g} (valeur d'essai)"
    lignes.append(
        _ligne("flambage-ec3-lambda-petit", p, "Eurocode 3 : λ̄ ≤ 0,2, pas de flambement (χ = 1), Nb,Rd", donnees,
               "χ = 1 donc Nb,Rd = A·fy / γM1", ref, npl / gm, e["NbRd"], "kN", 1e-3)
    )
    return lignes


# ------------------------------------------------------------------------------------------------- sections


def _sections() -> list[dict]:
    from mecastruct.core import geometry, solicitations

    p = "Sections"
    lignes = []

    b, h = 0.1, 0.2
    P = geometry.analytical({"type": "rectangle", "b": b, "h": h})
    d = "rectangle b = 100 mm (largeur) × h = 200 mm (hauteur)"
    lignes += [
        _ligne("section-rectangle-aire", p, "Rectangle : aire", d, "S = b·h", REF_RDM, b * h, P["S"], "mm²", 1e6),
        _ligne("section-rectangle-inertie", p, "Rectangle : moment quadratique Iz", d, "Iz = b·h³ / 12", REF_RDM,
               b * h**3 / 12, P["Iz"], "mm⁴", 1e12),
        _ligne("section-rectangle-module", p, "Rectangle : module de flexion Wz", d, "Wz = Iz / (h/2) = b·h² / 6",
               REF_RDM, b * h**2 / 6, P["Wz"], "mm³", 1e9),
    ]

    D = 0.1
    P = geometry.analytical({"type": "disque", "D": D})
    d = "disque plein D = 100 mm"
    lignes += [
        _ligne("section-disque-aire", p, "Disque : aire", d, "S = π·D² / 4", REF_RDM, math.pi * D**2 / 4, P["S"],
               "mm²", 1e6),
        _ligne("section-disque-inertie", p, "Disque : moment quadratique I", d, "I = π·D⁴ / 64", REF_RDM,
               math.pi * D**4 / 64, P["Iz"], "mm⁴", 1e12),
        _ligne("section-disque-module", p, "Disque : module de flexion W", d, "W = I / (D/2) = π·D³ / 32", REF_RDM,
               math.pi * D**3 / 32, P["Wz"], "mm³", 1e9),
        _ligne("section-disque-torsion", p, "Disque : constante de torsion J", d, "J = π·D⁴ / 32", REF_RDM,
               math.pi * D**4 / 32, P["J"], "mm⁴", 1e12),
    ]

    D, di = 0.1, 0.08
    P = geometry.analytical({"type": "couronne", "D": D, "d": di})
    d = "tube D = 100 mm extérieur, d = 80 mm intérieur"
    lignes += [
        _ligne("section-tube-aire", p, "Tube : aire", d, "S = π·(D² − d²) / 4", REF_RDM,
               math.pi * (D**2 - di**2) / 4, P["S"], "mm²", 1e6),
        _ligne("section-tube-inertie", p, "Tube : moment quadratique I", d, "I = π·(D⁴ − d⁴) / 64", REF_RDM,
               math.pi * (D**4 - di**4) / 64, P["Iz"], "mm⁴", 1e12),
        _ligne("section-tube-module", p, "Tube : module de flexion W", d, "W = I / (D/2) = π·(D⁴ − d⁴) / (32·D)",
               REF_RDM, math.pi * (D**4 - di**4) / (32 * D), P["Wz"], "mm³", 1e9),
    ]

    sec = geometry.validateSection({"type": "rectangle", "b": b, "h": h})
    M, T = 20e3, 60e3
    flexion = solicitations.bendingStress({"sec": sec, "N": 0.0, "Mfz": M, "Mfy": 0.0, "Kt": 1.0, "Re": 235e6})
    jour = solicitations.jourawski(sec, T)
    d = "rectangle b = 100 mm × h = 200 mm ; M = 20 000 N·m, T = 60 000 N"
    lignes += [
        _ligne("section-rectangle-flexion", p, "Rectangle en flexion simple : contrainte normale maximale", d,
               "σ = M / W = 6·M / (b·h²)", REF_RDM, 6 * M / (b * h**2), flexion["sigmaMaxTraction"], "MPa", 1e-6),
        _ligne("section-rectangle-cisaillement", p, "Rectangle sous effort tranchant : τ maximale (Jourawski)", d,
               "τmax = 3·T / (2·b·h)", REF_RDM, 3 * T / (2 * b * h), jour["tauMax"], "MPa", 1e-6),
    ]
    return lignes


# --------------------------------------------------------------------------------------------- sollicitations


def _sollicitations() -> list[dict]:
    from mecastruct.core import solicitations

    p = "Sollicitations"
    N, S0, L0 = 50e3, 200e-6, 2.0
    r = solicitations.traction({"N": N, "S0": S0, "L0": L0, "E": E_ACIER, "Re": 235e6})
    d = "barre en traction N = 50 000 N, S = 200 mm², L = 2 m, E = 210 GPa"
    lignes = [
        _ligne("traction-contrainte", p, "Traction simple : contrainte normale", d, "σ = N / S", REF_RDM, N / S0,
               r["sigmaNom"], "MPa", 1e-6),
        _ligne("traction-allongement", p, "Traction simple : allongement (intégration numérique de N/(E·S))", d,
               "ΔL = N·L / (E·S)", REF_RDM, N * L0 / (E_ACIER * S0), r["dL"]["integrale"], "mm", 1e3),
    ]
    T, D, L = 200.0, 0.04, 1.0
    r = solicitations.torsion({"Mt": T, "D": D, "G": G_ACIER, "L": L, "Re": 235e6})
    d = "arbre plein Ø 40 mm, moment de torsion T = 200 N·m, L = 1 m, G = 80 GPa"
    lignes += [
        _ligne("torsion-contrainte", p, "Torsion d'un arbre plein : contrainte de cisaillement maximale", d,
               "τ = 16·T / (π·d³)", REF_RDM, 16 * T / (math.pi * D**3), r["tauMaxNom"], "MPa", 1e-6),
        _ligne("torsion-angle", p, "Torsion d'un arbre plein : angle de torsion (énergétique ∂U/∂T)", d,
               "φ = T·L / (G·J), J = π·d⁴ / 32", REF_RDM, T * L / (G_ACIER * math.pi * D**4 / 32),
               r["phi"]["energetique"], "rad"),
    ]
    return lignes


# ---------------------------------------------------------------------------------------------- tenseurs


def _tenseurs() -> list[dict]:
    import numpy as np

    from mecastruct.core import tensors

    p = "Tenseurs et critères"
    sx, sy, t = 100e6, 20e6, 30e6
    moyen = (sx + sy) / 2
    rayon = math.sqrt(((sx - sy) / 2) ** 2 + t**2)
    s1, s2 = moyen + rayon, moyen - rayon
    pl = tensors.plane2D(sx, sy, t, 0.0)
    pr = tensors.principal(np.array([[sx, t, 0.0], [t, sy, 0.0], [0.0, 0.0, 0.0]]))
    cr = tensors.criteria([pr["sigmaI"], pr["sigmaII"], pr["sigmaIII"]], 235e6, 1.0)
    d = "état plan σx = 100 MPa, σy = 20 MPa, τxy = 30 MPa (σz = 0)"
    f12 = "σ1,2 = (σx + σy)/2 ± √(((σx − σy)/2)² + τ²)"
    return [
        _ligne("tenseur-contrainte-principale-1", p, "Contrainte principale σ1 (cercle de Mohr)", d, f12, REF_MOHR,
               s1, pl["sigma1"], "MPa", 1e-6),
        _ligne("tenseur-contrainte-principale-2", p, "Contrainte principale σ2 (cercle de Mohr)", d, f12, REF_MOHR,
               s2, pl["sigma2"], "MPa", 1e-6),
        _ligne("tenseur-cisaillement-max-plan", p, "Cisaillement maximal dans le plan (rayon du cercle)", d,
               "τmax = √(((σx − σy)/2)² + τ²)", REF_MOHR, rayon, pl["tauMax2D"], "MPa", 1e-6),
        _ligne("tenseur-principale-3d-1", p, "Contrainte principale σ1 (tenseur 3×3, valeurs propres)", d, f12,
               REF_MOHR, s1, pr["sigmaI"], "MPa", 1e-6),
        _ligne("tenseur-von-mises", p, "Contrainte équivalente de Von Mises (σ3 = 0)", d,
               "σVM = √(σ1² − σ1·σ2 + σ2²)", "Formule de manuel : critère de Von Mises", math.sqrt(s1**2 - s1 * s2 + s2**2),
               cr["sigmaEqVM"], "MPa", 1e-6),
        _ligne("tenseur-tresca", p, "Contrainte équivalente de Tresca (σ3 = 0)", d, "σTresca = σ1 − σ3 = σ1",
               "Formule de manuel : critère de Tresca", s1, cr["sigmaEqTresca"], "MPa", 1e-6),
    ]


# ------------------------------------------------------------------------------------------ hooke et jauges


def _hooke_jauges() -> list[dict]:
    from mecastruct.core import hooke_gauges as hg

    p = "Hooke et jauges"
    E, nu = E_ACIER, 0.3
    G = E / (2 * (1 + nu))
    sig = 100e6
    e = hg.hooke3D([sig, 0, 0, 0, 0, 0], E, nu)
    d = "acier E = 210 GPa, ν = 0,3, traction uniaxiale σx = 100 MPa"
    lignes = [
        _ligne("hooke-deformation-axiale", p, "Hooke, traction uniaxiale : déformation axiale", d, "εx = σx / E",
               REF_HOOKE, sig / E, e[0], "µdéf", 1e6),
        _ligne("hooke-deformation-transversale", p, "Hooke, traction uniaxiale : déformation transversale", d,
               "εy = εz = −ν·σx / E", REF_HOOKE, -nu * sig / E, e[1], "µdéf", 1e6),
    ]
    tau = 50e6
    e = hg.hooke3D([0, 0, 0, 0, 0, tau], E, nu)
    d = "acier E = 210 GPa, ν = 0,3, cisaillement pur τxy = 50 MPa"
    lignes.append(
        _ligne("hooke-glissement", p, "Hooke, cisaillement pur : glissement", d, "γxy = τxy / G, G = E / (2·(1 + ν))",
               REF_HOOKE, tau / G, e[5], "µdéf", 1e6)
    )

    K, eps, R0 = 2.0, 1000e-6, 120.0
    g = hg.gauge(K, eps, R0)
    d = "jauge K = 2, ε = 1 000 µdéf, R₀ = 120 Ω"
    lignes += [
        _ligne("jauge-variation-relative", p, "Jauge de déformation : variation relative de résistance", d,
               "ΔR / R = K·ε", REF_JAUGES, K * eps, g["dRsurR"], "10⁻³", 1e3),
        _ligne("jauge-variation-resistance", p, "Jauge de déformation : variation de résistance", d,
               "ΔR = R₀·K·ε", REF_JAUGES, R0 * K * eps, g["dR"], "Ω"),
    ]

    Vin = 5.0
    w = hg.wheatstone("quart", K, Vin, [eps])
    x = K * eps
    d = "quart de pont, K = 2, ε = 1 000 µdéf, Vin = 5 V"
    lignes += [
        _ligne("pont-quart-lineaire", p, "Pont de Wheatstone en quart de pont : tension de sortie (linéarisée)", d,
               "Vout = Vin·K·ε / 4", REF_JAUGES, Vin * K * eps / 4, w["Vout"], "mV", 1e3),
        _ligne("pont-quart-exact", p, "Pont de Wheatstone en quart de pont : tension de sortie (exacte)", d,
               "Vout = Vin·x / (2·(2 + x)), x = K·ε", REF_JAUGES, Vin * x / (2 * (2 + x)), w["VoutExact"], "mV", 1e3),
    ]

    e1, e2, e3 = 600e-6, -200e-6, 500e-6  # jauges à 0°, 90° et 45°
    r = hg.rosette45(e1, e2, e3, E, nu)
    gxy = 2 * e3 - e1 - e2
    centre = (e1 + e2) / 2
    rayon = math.sqrt(((e1 - e2) / 2) ** 2 + (gxy / 2) ** 2)
    eI, eII = centre + rayon, centre - rayon
    d = "rosette à 45° : ε0° = 600, ε90° = −200, ε45° = 500 µdéf ; E = 210 GPa, ν = 0,3"
    lignes += [
        _ligne("rosette-deformation-principale-1", p, "Rosette à 45° : déformation principale ε1", d,
               "ε1,2 = (ε0 + ε90)/2 ± √(((ε0 − ε90)/2)² + (γxy/2)²), γxy = 2·ε45 − ε0 − ε90", REF_JAUGES, eI,
               r["epsI"], "µdéf", 1e6),
        _ligne("rosette-deformation-principale-2", p, "Rosette à 45° : déformation principale ε2", d,
               "ε1,2 = (ε0 + ε90)/2 ± √(((ε0 − ε90)/2)² + (γxy/2)²)", REF_JAUGES, eII, r["epsII"], "µdéf", 1e6),
        _ligne("rosette-contrainte-principale-1", p, "Rosette à 45° : contrainte principale σ1 (contraintes planes)", d,
               "σ1 = E / (1 − ν²) · (ε1 + ν·ε2)", REF_HOOKE, E / (1 - nu**2) * (eI + nu * eII), r["sigmaI"], "MPa",
               1e-6),
    ]
    return lignes


# ---------------------------------------------------------------------------------------------- ensemble

_GROUPES: list[tuple[str, str, Callable[[], list[dict]]]] = [
    ("poutre-console", "Poutres", _console),
    ("poutre-2appuis-q", "Poutres", _deux_appuis_repartie),
    ("poutre-2appuis-P", "Poutres", _deux_appuis_ponctuelle),
    ("poutre-hyperstatique", "Poutres", _hyperstatiques),
    ("treillis", "Treillis", _treillis),
    ("flambage", "Flambage", _flambage),
    ("flambage-ec3", "Flambage", _flambage_ec3),
    ("section", "Sections", _sections),
    ("sollicitations", "Sollicitations", _sollicitations),
    ("tenseur", "Tenseurs et critères", _tenseurs),
    ("hooke-jauges", "Hooke et jauges", _hooke_jauges),
]


def verifier() -> list[dict]:
    """Calcule tous les cas (moteur MecaStruct contre formule à la main) ; une ligne par grandeur comparée."""
    lignes: list[dict] = []
    for ident, page, groupe in _GROUPES:
        try:
            lignes += groupe()
        except Exception as err:  # noqa: BLE001 : un moteur en panne donne une ligne en échec, pas une page cassée
            lignes.append(
                {
                    "id": f"{ident}-erreur",
                    "page": page,
                    "titre": f"{page} : le calcul de vérification a échoué",
                    "donnees": "",
                    "formule": "",
                    "reference": "",
                    "unite": "",
                    "valeur_cible": math.nan,
                    "valeur_calculee": math.nan,
                    "tolerance": TOLERANCE,
                    "ecart": math.nan,
                    "ok": False,
                    "erreur": str(err) or type(err).__name__,
                    "cible_txt": "–",
                    "calculee_txt": "–",
                    "ecart_txt": "–",
                    "tolerance_txt": formater(TOLERANCE, 1),
                }
            )
    return lignes


def resume(lignes: list[dict]) -> dict:
    """Total, nombre de lignes conformes, écart relatif maximal et verdict de l'ensemble."""
    ecarts = [x["ecart"] for x in lignes if math.isfinite(x["ecart"])]
    ok = sum(1 for x in lignes if x["ok"])
    ecart_max = max(ecarts) if ecarts else math.nan
    return {
        "total": len(lignes),
        "ok": ok,
        "ecart_max": ecart_max,
        "ecart_max_txt": "0" if ecart_max == 0 else formater(ecart_max, 2),
        "tout_ok": bool(lignes) and ok == len(lignes),
    }

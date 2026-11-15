"""Ossature 3D sans interface : tableaux de saisie → données du moteur frame3d, vue 3D, tableaux de résultats.

Partagé par la page de bureau (bureau/pages/ossature3d.py) et le pont web (pont/structures.py).
Saisie en mm, N, N·m et N/m ; conversion en SI (m) avant l'appel à frame3d.solveFrame3D.
"""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from mecastruct.core import frame3d
from mecastruct.core.errors import MecaStructError
from mecastruct.services.exemples_3d import EXPLICATIONS, exemples  # noqa: F401

APPUIS = ["libre", "encastrement", "rotule", "appui_z", "perso"]
LIAISONS = ["rigide", "articulee"]
SECTIONS = ["catalogue", "rond", "tube", "rectangle", "perso"]
COMPOSANTES = [("N", "N"), ("Vy", "N"), ("Vz", "N"), ("T", "N·m"), ("My", "N·m"), ("Mz", "N·m")]
# exemples de saisie de la colonne « Dimensions », par type de section (mm, mm², mm⁴, mm³)
EXEMPLES_DIM = {
    "catalogue": "IPE 200",
    "rond": "d=40",
    "tube": "D=100; t=5",
    "rectangle": "b=30; h=60",
    "perso": "A=2848; Iy=1.943e7; Iz=1.424e6; J=7e4; Wy=1.943e5; Wz=2.847e4; Wt=8e3",
}
TABLES = ("noeuds", "pieces", "charges_nodales", "charges_reparties")
C_STRUCTURE, C_DEFORMEE, C_APPUI, C_CHARGE = "#1E1B2E", "#6E56CF", "#009E73", "#E69F00"
# repère global dessiné à l'origine : X rouge, Y vert, Z bleu (convention des logiciels de CAO)
C_AXES = {"X": "#D55E00", "Y": "#009E73", "Z": "#0072B2"}


# ------------------------------------------------------------------ exemples → tableaux


def _perso(e: dict) -> str:
    """Section d'un exemple en saisie « perso » (mm², mm⁴, mm³)."""
    echelles = {"A": 1e6, "Iy": 1e12, "Iz": 1e12, "J": 1e12, "Wy": 1e9, "Wz": 1e9, "Wt": 1e9}
    return "; ".join(f"{k}={e[k] * f:.6g}" for k, f in echelles.items() if e.get(k) is not None)


def _tables_exemple(nom: str, dm) -> dict[str, list[dict]]:
    """Les quatre tableaux de saisie remplis avec l'exemple `nom` (voir exemples_3d.exemples)."""
    d = exemples(dm)[nom]
    mat = dm.getMaterial("S235")["Name"]  # matériau des exemples de frame3d
    noeuds = [
        {
            "id": n["id"],
            **{c: n[c] * 1e3 for c in "xyz"},
            "appui": n.get("appui", "libre"),
            "ddl": "",
        }
        for n in d["noeuds"]
    ]
    pieces = [
        {
            "id": e["id"],
            "debut": e["ni"],
            "fin": e["nj"],
            "materiau": mat,
            "section": "perso",
            "dimensions": _perso(e),
            "beta": e.get("beta_deg", 0.0),
            "liaison_debut": e.get("liaison_i", "rigide"),
            "liaison_fin": e.get("liaison_j", "rigide"),
        }
        for e in d["elements"]
    ]
    nod = [
        {"noeud": c["noeud"], **{f: c.get(f, 0.0) for f in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}}
        for c in d.get("charges_nodales", [])
    ]
    rep = [
        {"piece": c["element"], **{f: c.get(f, 0.0) for f in ("qx", "qy", "qz")}}
        for c in d.get("charges_reparties", [])
    ]
    return {"noeuds": noeuds, "pieces": pieces, "charges_nodales": nod, "charges_reparties": rep}


# ------------------------------------------------------------------ tableaux → données du moteur


def _lignes(df: pd.DataFrame, cle: str) -> list[dict]:
    """Lignes du tableau sans les lignes vides (identifiant `cle` absent)."""
    return [r for r in df.to_dict("records") if r.get(cle) is not None and not pd.isna(r.get(cle))]


def _f(v) -> float:
    """Case numérique : vide → 0."""
    return 0.0 if v is None or pd.isna(v) else float(v)


def _dims(txt, quoi: str) -> dict[str, float]:
    """« d=40; t=5 » → {d: 40, t: 5} (virgule décimale acceptée). Erreur : ValueError en français."""
    out = {}
    for morceau in str(txt or "").split(";"):
        if not morceau.strip():
            continue
        k, sep, v = morceau.partition("=")
        if not sep:
            raise ValueError(f"{quoi} : « {morceau.strip()} » doit être de la forme nom=valeur.")
        try:
            out[k.strip()] = float(v.strip().replace(",", "."))
        except ValueError:
            raise ValueError(f"{quoi} : valeur « {v.strip()} » invalide pour {k.strip()}.") from None
    return out


def _proprietes(p: dict, dm) -> dict:
    """Propriétés SI (A, Iy, Iz, J, Wy, Wz, Wt) d'une pièce à partir de son type de section et de ses dimensions."""
    quoi, sec = f"Pièce {int(p['id'])}", p.get("section")
    if sec == "catalogue":
        fam, _, taille = str(p.get("dimensions") or "").strip().partition(" ")
        try:
            return frame3d._profil(dm, fam, taille.strip())
        except MecaStructError as err:
            raise ValueError(f"{quoi} : {err.message} (exemple : « IPE 200 »).") from None
    d = _dims(p.get("dimensions"), quoi)

    def mm(k: str) -> float:
        if k not in d:
            raise ValueError(f"{quoi} : dimension « {k} » manquante (exemple : « {EXEMPLES_DIM[sec]} »).")
        return d[k] / 1e3

    if sec == "rond":
        return frame3d.sectionRond(mm("d"))
    if sec == "tube":
        return frame3d.sectionTube(mm("D"), mm("t"))
    if sec == "rectangle":
        return frame3d.sectionRectangle(mm("b"), mm("h"))
    if sec == "perso":
        for k in ("A", "Iy", "Iz", "J"):
            mm(k)
        puissance = {"A": 2, "Iy": 4, "Iz": 4, "J": 4, "Wy": 3, "Wz": 3, "Wt": 3}
        return {k: v / 1e3 ** puissance[k] for k, v in d.items() if k in puissance}
    raise ValueError(f"{quoi} : type de section « {sec} » inconnu.")


def _appui(n: dict) -> str | list[bool]:
    """Appui d'un nœud pour le moteur ; « perso » : 6 chiffres 0/1 de la colonne DDL perso."""
    if n.get("appui") != "perso":
        return n.get("appui") or "libre"
    ddl = str(n.get("ddl") or "").replace(" ", "")
    if len(ddl) != 6 or set(ddl) - {"0", "1"}:
        raise ValueError(f"Nœud {int(n['id'])} : appui perso, la colonne DDL perso doit contenir 6 chiffres 0/1.")
    return [c == "1" for c in ddl]


def _donnees(tables: dict[str, pd.DataFrame], poids_propre: bool, dm) -> dict:
    """Données de frame3d.solveFrame3D (SI) à partir des tableaux de saisie."""
    noeuds = [
        {"id": int(n["id"]), **{c: _f(n[c]) / 1e3 for c in "xyz"}, "appui": _appui(n)}
        for n in _lignes(tables["noeuds"], "id")
    ]
    elements = []
    for p in _lignes(tables["pieces"], "id"):
        mat = dm.getMaterial(p.get("materiau") or "S235")
        if not all(math.isfinite(mat[k]) for k in ("E", "G")):
            raise ValueError(f"Pièce {int(p['id'])} : E ou G inconnu pour le matériau « {mat['Name']} ».")
        elements.append(
            {
                "id": int(p["id"]),
                "ni": None if pd.isna(p.get("debut")) else int(p["debut"]),
                "nj": None if pd.isna(p.get("fin")) else int(p["fin"]),
                "E": mat["E"],
                "G": mat["G"],
                "rho": mat["rho"] if math.isfinite(mat["rho"]) else 0.0,
                "Re": mat["Re"],  # pour comparer σ à la limite élastique ; ignorée par le solveur
                **_proprietes(p, dm),
                "beta_deg": _f(p.get("beta")),
                "liaison_i": p.get("liaison_debut") or "rigide",
                "liaison_j": p.get("liaison_fin") or "rigide",
            }
        )
    nod = [
        {"noeud": int(c["noeud"]), **{f: _f(c.get(f)) for f in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}}
        for c in _lignes(tables["charges_nodales"], "noeud")
    ]
    rep = [
        {"element": int(c["piece"]), **{f: _f(c.get(f)) for f in ("qx", "qy", "qz")}}
        for c in _lignes(tables["charges_reparties"], "piece")
    ]
    return {
        "noeuds": noeuds,
        "elements": elements,
        "charges_nodales": nod,
        "charges_reparties": rep,
        "poids_propre": poids_propre,
    }


# ------------------------------------------------------------------ vue 3D


def _amplification_auto(res: dict, data: dict) -> int:
    """Amplification telle que le déplacement maximal vaille 10 % de la plus grande dimension (entre 1 et 1000)."""
    xyz = np.array([[n[c] for c in "xyz"] for n in data["noeuds"]])
    dim = float(np.max(np.ptp(xyz, axis=0))) if len(xyz) else 0.0
    umax = res["deplacement_max"]["valeur"]
    return int(min(1000, max(1, round(0.1 * dim / umax)))) if umax > 0 and dim > 0 else 1


def _vue_3d(res: dict, data: dict, ampli: float) -> go.Figure:
    """Structure initiale, déformée amplifiée, nœuds numérotés, appuis et charges nodales (mm)."""
    ids = [n["id"] for n in data["noeuds"]]
    P = {n["id"]: np.array([n[c] for c in "xyz"]) * 1e3 for n in data["noeuds"]}
    D = {i: P[i] + ampli * np.array(res["deplacements"][i][:3]) * 1e3 for i in ids}
    fig = go.Figure()
    # shortcut: déformée tracée en segments droits entre nœuds déplacés ; découper les pièces pour une courbe plus fine
    for pos, nom, style in ((P, "Structure", {"color": C_STRUCTURE, "width": 5}), (D, f"Déformée (×{ampli:g})", None)):
        x, y, z = [], [], []
        for e in data["elements"]:
            for k, v in enumerate(np.c_[pos[e["ni"]], pos[e["nj"]], [np.nan] * 3]):
                (x, y, z)[k].extend(v)
        line = style or {"color": C_DEFORMEE, "width": 4, "dash": "dash"}
        fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode="lines", name=nom, line=line, hoverinfo="skip"))
    xyz = np.array([P[i] for i in ids])
    fig.add_trace(
        go.Scatter3d(
            x=xyz[:, 0],
            y=xyz[:, 1],
            z=xyz[:, 2],
            mode="markers+text",
            text=[str(i) for i in ids],
            textposition="top center",
            marker={"size": 3, "color": C_STRUCTURE},
            name="Nœuds",
        )
    )
    appuis = [i for i in ids if i in res["reactions"]]
    if appuis:
        a = np.array([P[i] for i in appuis])
        fig.add_trace(
            go.Scatter3d(
                x=a[:, 0],
                y=a[:, 1],
                z=a[:, 2],
                mode="markers",
                marker={"size": 8, "symbol": "square", "color": C_APPUI},
                name="Appuis",
            )
        )
    dim = float(np.max(np.ptp(xyz, axis=0))) or 1000.0
    charges = [c for c in data["charges_nodales"] if any(c[f] for f in ("Fx", "Fy", "Fz"))]
    if charges:
        pos = np.array([P[c["noeud"]] for c in charges])
        f = np.array([[c["Fx"], c["Fy"], c["Fz"]] for c in charges])
        f = 0.12 * dim * f / np.linalg.norm(f, axis=1)[:, None]  # flèche de 12 % de la structure, en mm
        fig.add_trace(
            go.Cone(
                x=pos[:, 0],
                y=pos[:, 1],
                z=pos[:, 2],
                u=f[:, 0],
                v=f[:, 1],
                w=f[:, 2],
                anchor="tip",
                sizemode="raw",  # « absolute » gonflait les cônes à des millions de mm et écrasait la structure
                colorscale=[[0, C_CHARGE], [1, C_CHARGE]],
                showscale=False,
                name="Charges nodales",
                hovertext=[f"F = ({c['Fx']:g} ; {c['Fy']:g} ; {c['Fz']:g}) N" for c in charges],
            )
        )
    # cube de même échelle sur les trois axes : « aspectmode=data » écrase un axe vide (console plane, treillis plan)
    long_axe = 0.15 * dim
    for k, (nom, couleur) in enumerate(C_AXES.items()):
        bout = np.zeros(3)
        bout[k] = long_axe
        fig.add_trace(
            go.Scatter3d(
                x=[0, bout[0]],
                y=[0, bout[1]],
                z=[0, bout[2]],
                mode="lines+text",
                line={"color": couleur, "width": 6},
                text=["", nom],
                textfont={"color": couleur, "size": 14},
                textposition="middle right",
                name="Repère (0, 0, 0)",
                legendgroup="repere",
                showlegend=k == 0,
                hoverinfo="skip",
            )
        )
    tout = np.vstack([xyz, *D.values(), np.zeros(3), np.eye(3) * long_axe])  # le repère reste dans le cadre
    centre, demi = (tout.min(axis=0) + tout.max(axis=0)) / 2, 0.65 * max(float(np.max(np.ptp(tout, axis=0))), dim)
    fig.update_layout(
        height=550,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        scene={
            "aspectmode": "cube",
            **{
                f"{a}axis": {"title": {"text": f"{a.upper()} (mm)"}, "range": [c - demi, c + demi]}
                for a, c in zip("xyz", centre, strict=True)
            },
        },
        legend={"orientation": "h", "y": 1.02, "x": 0},
    )
    return fig


def _table_deplacements(res: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Nœud": i, **{f"u{c} (mm)": v * 1e3 for c, v in zip("xyz", u[:3], strict=True)}}
            | {f"θ{c} (mrad)": v * 1e3 for c, v in zip("xyz", u[3:], strict=True)}
            for i, u in res["deplacements"].items()
        ]
    )


def _table_reactions(res: dict) -> pd.DataFrame:
    noms = ["Rx (N)", "Ry (N)", "Rz (N)", "Mx (N·m)", "My (N·m)", "Mz (N·m)"]
    return pd.DataFrame([{"Nœud": i, **dict(zip(noms, r, strict=True))} for i, r in res["reactions"].items()])


def _table_contraintes(res: dict) -> pd.DataFrame:
    def mpa(v):
        return None if v is None else v / 1e6

    return pd.DataFrame(
        [
            {"Pièce": i, "σmax (MPa)": mpa(c["sigma_max"]), "τ torsion (MPa)": mpa(c["tau_torsion"])}
            for i, c in res["contraintes"].items()
        ]
    )


def _csv(res: dict) -> bytes:
    """Tableaux de résultats à la suite, séparés par une ligne de titre (UTF-8 avec BOM pour Excel)."""
    parties = [
        ("Déplacements", _table_deplacements(res)),
        ("Réactions", _table_reactions(res)),
        ("Contraintes", _table_contraintes(res)),
    ]
    return "\n".join(f"# {titre}\n{df.to_csv(index=False)}" for titre, df in parties).encode("utf-8-sig")


def _terme(v: float) -> str:
    """Valeur en kN ou kN·m d'un terme de somme LaTeX, entre parenthèses si négative."""
    x = 0.0 if abs(v) < 1e-9 else v / 1e3  # résidu d'arrondi : écrit 0
    return f"({x:.5g})" if x < 0 else f"{x:.5g}"


def bilan_latex(res: dict, data: dict) -> tuple[list[str], pd.DataFrame, bool]:
    """Vérification à la main : (sommes ΣF et ΣM en LaTeX, tableau des contraintes refaites, σ manquante ?)."""
    v = frame3d.verificationAMain(data, res)
    b = v["bilan"]
    termes = (("charges nodales", "nodales"), ("charges réparties", r"r\'eparties"), ("réactions", r"r\'eactions"))
    formules = []
    for grandeur, cle, unite in (("F", "F", r"\mathrm{kN}"), ("M", "M", r"\mathrm{kN\cdot m}")):
        for i, axe in enumerate("xyz"):
            somme = " + ".join(
                r"\underbrace{" + _terme(b[nom][cle][i]) + r"}_{\text{" + leg + "}}" for nom, leg in termes
            )
            formules.append(rf"\sum {grandeur}_{axe}=" + somme + "=" + _terme(b["somme"][cle][i]) + rf"\ {unite}")
    re = {e["id"]: e.get("Re") for e in data["elements"]}
    lignes = []
    for c in v["contraintes"]:
        r = re.get(c["id"])
        ok = c["sigma"] is not None and r is not None and math.isfinite(r)
        lignes.append(
            {
                "Pièce": c["id"],
                "N max (kN)": c["N"] / 1e3,
                "My max (kN·m)": c["My"] / 1e3,
                "Mz max (kN·m)": c["Mz"] / 1e3,
                "A (mm²)": c["A"] * 1e6,
                "Wy (cm³)": None if c["Wy"] is None else c["Wy"] * 1e6,
                "Wz (cm³)": None if c["Wz"] is None else c["Wz"] * 1e6,
                "σ refait (MPa)": None if c["sigma"] is None else c["sigma"] / 1e6,
                "σ solveur (MPa)": None if c["solveur"] is None else c["solveur"] / 1e6,
                "Re (MPa)": r / 1e6 if ok else None,
                "σ/Re": c["sigma"] / r if ok else None,
            }
        )
    return formules, pd.DataFrame(lignes), any(c["sigma"] is None for c in v["contraintes"])


"""Mode « Ossature 3D » de la page Poutres : saisie en tableaux, vue 3D, résultats du moteur frame3d.

Saisie en mm, N, N·m et N/m ; conversion en SI (m) avant l'appel à frame3d.solveFrame3D. La saisie vit dans
state.extra["P3D"] (quatre listes de lignes, la case « poids propre » et l'exemple choisi).
"""

import copy
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from mecastruct.bureau import state
from mecastruct.bureau.exemples_3d import EXPLICATIONS, exemples
from mecastruct.bureau.widgets import Colonne, Zone, liste_col, nombre_col, texte_col
from mecastruct.core import frame3d
from mecastruct.core.errors import MecaStructError

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


def _id(label_cle: str, label: str) -> Colonne:
    return Colonne(label_cle, label, "nombre", defaut=1, entier=True)


def _colonnes(dm) -> dict[str, list[Colonne]]:
    """Colonnes des quatre tableaux de saisie."""
    return {
        "noeuds": [
            _id("id", "id"), nombre_col("x", "x (mm)"), nombre_col("y", "y (mm)"), nombre_col("z", "z (mm)"),
            liste_col("appui", "Appui", APPUIS, "libre"),
            Colonne("ddl", "DDL perso", "texte", aide="Appui « perso » : 6 chiffres 0/1 pour ux uy uz θx θy θz (1 = bloqué)."),
        ],
        "pieces": [
            _id("id", "id"), _id("debut", "Nœud début"), _id("fin", "Nœud fin"),
            liste_col("materiau", "Matériau", dm.listMaterials(), "S235"),
            liste_col("section", "Section", SECTIONS, "rond"),
            Colonne("dimensions", "Dimensions (mm)", "texte", defaut="d=40",
                    aide="Exemples : " + " ; ".join(f"{k} : « {v} »" for k, v in EXEMPLES_DIM.items())),
            nombre_col("beta", "β (°)"),
            liste_col("liaison_debut", "Liaison début", LIAISONS, "rigide"),
            liste_col("liaison_fin", "Liaison fin", LIAISONS, "rigide"),
        ],
        "charges_nodales": [
            _id("noeud", "Nœud"),
            *[nombre_col(c, f"{c} (N)") for c in ("Fx", "Fy", "Fz")],
            *[nombre_col(c, f"{c} (N·m)") for c in ("Mx", "My", "Mz")],
        ],
        "charges_reparties": [_id("piece", "Pièce"), *[nombre_col(c, f"{c} (N/m)") for c in ("qx", "qy", "qz")]],
    }  # fmt: skip


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


def _synthese(z: Zone, res: dict) -> None:
    sig = [c["sigma_max"] for c in res["contraintes"].values() if c["sigma_max"] is not None]
    dm = res["deplacement_max"]
    z.synthese(
        [
            {"label": "Déplacement max", "value": f"{dm['valeur'] * 1e3:.4g} mm", "delta": f"Nœud {dm['noeud']}"},
            {"label": "σmax", "value": f"{max(sig) / 1e6:.4g} MPa" if sig else "non calculée"},
        ]
    )
    eq = res["equilibre"]
    if eq["ok"]:
        z.statut("Équilibre global vérifié (réactions + charges = 0).", True)
    else:
        z.statut(
            f"Écart d'équilibre : ΣF = {np.round(eq['forces'], 6).tolist()} N, "
            f"ΣM = {np.round(eq['moments'], 6).tolist()} N·m.",
            False,
        )


def _efforts(z: Zone, res: dict) -> None:
    piece = z.liste("Pièce", list(res["efforts"]), "p3d.piece", apres=z.page.surSaisie)
    ef = res["efforts"][piece]
    s = np.array(ef["s"]) * 1e3
    cols = z.colonnes(2)
    for k, (c, unite) in enumerate(COMPOSANTES):
        fig = go.Figure(go.Scatter(x=s, y=ef[c], mode="lines", fill="tozeroy", line={"color": C_DEFORMEE}))
        fig.update_layout(
            title={"text": f"{c} ({unite})"},
            height=260,
            margin={"l": 50, "r": 10, "t": 40, "b": 40},
            xaxis_title="s (mm)",
            showlegend=False,
        )
        cols[k % 2].plot(fig)


def _equations(z: Zone, res: dict) -> None:
    z.formules(res["latex"])
    z.rapport(res["rapport"])


def _terme(v: float) -> str:
    """Valeur en kN ou kN·m d'un terme de somme LaTeX, entre parenthèses si négative."""
    x = 0.0 if abs(v) < 1e-9 else v / 1e3  # résidu d'arrondi : écrit 0
    return f"({x:.5g})" if x < 0 else f"{x:.5g}"


def _verification(z: Zone, res: dict, data: dict) -> None:
    """Vérification à la main : bilan des actions avec valeurs, puis contraintes comparées à Re."""
    v = frame3d.verificationAMain(data, res)
    b = v["bilan"]
    z.texte(
        "**Équilibre global, refait à partir de vos données** : charges nodales + charges réparties (poids propre "
        "compris) + réactions du solveur = 0. Moments pris par rapport à l'origine (0, 0, 0)."
    )
    termes = (("charges nodales", "nodales"), ("charges réparties", r"r\'eparties"), ("réactions", r"r\'eactions"))
    for grandeur, cle, unite in (("F", "F", r"\mathrm{kN}"), ("M", "M", r"\mathrm{kN\cdot m}")):
        for i, axe in enumerate("xyz"):
            somme = " + ".join(
                r"\underbrace{" + _terme(b[nom][cle][i]) + r"}_{\text{" + leg + "}}" for nom, leg in termes
            )
            z.formule(rf"\sum {grandeur}_{axe}=" + somme + "=" + _terme(b["somme"][cle][i]) + rf"\ {unite}")
    z.legende(
        "Les sommes doivent être nulles (écart admis : 1e-6 de l'échelle des actions). "
        + ("Équilibre vérifié." if res["equilibre"]["ok"] else "ÉQUILIBRE NON VÉRIFIÉ : voir l'onglet Synthèse.")
    )
    z.texte(
        "**Contraintes** : σ = |N|/A + |My|/Wy + |Mz|/Wz, maximum sur les 21 points de chaque pièce, comparée à la "
        "limite élastique Re du matériau (sans coefficient de sécurité). Les efforts viennent du solveur "
        "(onglet Efforts internes)."
    )
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
    z.tableau(pd.DataFrame(lignes))
    if any(c["sigma"] is None for c in v["contraintes"]):
        z.legende("σ non calculée pour une pièce sans module de flexion Wy ou Wz : saisissez-les (section « perso »).")


def _resultats(z: Zone, res: dict, data: dict) -> None:
    ampli = z.curseur("Amplification", "p3d.ampli", _amplification_auto(res, data), 1, 1000, 1, "%d",
                      apres=z.page.surSaisie)  # fmt: skip
    z.plot(_vue_3d(res, data, ampli))
    z.onglets(
        {
            "Synthèse": lambda c: _synthese(c, res),
            "Déplacements": lambda c: c.tableau(_table_deplacements(res)),
            "Réactions": lambda c: c.tableau(_table_reactions(res)),
            "Efforts internes": lambda c: _efforts(c, res),
            "Contraintes": lambda c: c.tableau(_table_contraintes(res)),
            "Vérification à la main": lambda c: _verification(c, res, data),
            "Équations": lambda c: _equations(c, res),
        }
    )
    z.telecharger("Exporter les résultats (CSV)", lambda: _csv(res), "ossature_3d.csv")


def _materiaux(z: Zone, pieces: list[dict], dm) -> None:
    """Caractéristiques des matériaux choisis dans le tableau des pièces (base de données de l'application)."""
    noms = sorted({str(p["materiau"]) for p in pieces if isinstance(p.get("materiau"), str) and p["materiau"]})
    lignes = []
    for nom in noms:
        m = dm.getMaterial(nom)
        lignes.append(
            {
                "Matériau": m["Name"],
                "E (GPa)": m["E"] / 1e9,
                "G (GPa)": m["G"] / 1e9,
                "ν": m["nu"],
                "ρ (kg/m³)": m["rho"],
                "Re (MPa)": m["Re"] / 1e6,
                "Rm (MPa)": m["Rm"] / 1e6,
            }
        )

    def corps(c: Zone) -> None:
        c.tableau(pd.DataFrame(lignes))
        c.legende(
            "Valeurs de la base de données de l'application (page Base de données). "
            "Changez le matériau dans « Pièces »."
        )

    z.repliable(f"Matériaux utilisés ({len(lignes)})", rendu=corps, cle="p3d.materiaux")


# ------------------------------------------------------------------ page


def _charge_exemple(nom: str, dm) -> None:
    """Remplace les tableaux et la case poids propre par l'exemple `nom`, et efface le résultat."""
    P3D = state.extra["P3D"]
    P3D.update(_tables_exemple(nom, dm))
    P3D["pp"] = bool(exemples(dm)[nom].get("poids_propre", False))
    state.v.pop("p3d.res", None)


def construire(page) -> object:
    """Panneaux du mode « Ossature 3D » : saisie à gauche (tableaux, Calculer), vue 3D et résultats à droite."""
    from mecastruct.bureau.widgets import Section, partage

    dm = state.dm()
    noms = list(exemples(dm))
    if "P3D" not in state.extra:
        state.extra["P3D"] = {"exemple": noms[0]}
        _charge_exemple(noms[0], dm)
    cols = _colonnes(dm)

    def calculer() -> None:
        s = copy.deepcopy(state.extra["P3D"])

        def travail():
            try:
                tables = {k: pd.DataFrame(s[k], columns=[c.cle for c in cols[k]]) for k in TABLES}
                data = _donnees(tables, s["pp"], dm)
                res = frame3d.solveFrame3D(data)
            except (ValueError, frame3d.FrameMechanismError) as err:
                return ("erreur", str(err))
            res.pop("K", None)  # 11 Mo pour 200 nœuds, inutile à la page : pas gardé
            return ("ok", res, data)

        def fin(r: tuple) -> None:
            if r[0] == "erreur":
                state.v["p3d.erreur"] = r[1]
                state.v.pop("p3d.res", None)
                return
            state.v.pop("p3d.erreur", None)
            state.v["p3d.res"] = {"res": r[1], "data": r[2], "empreinte": repr(s)}
            state.v["p3d.ampli"] = _amplification_auto(r[1], r[2])

        page.lancer(travail, fin, "erreur.p3d")

    def saisie(z: Zone) -> None:
        z.bouton("Calculer", calculer, primaire=True)
        z.erreurGardee("erreur.p3d")
        if state.v.get("p3d.erreur"):
            z.erreur(state.v["p3d.erreur"])

        def change() -> None:
            _charge_exemple(state.extra["P3D"]["exemple"], dm)
            page.rafraichirTout()

        z.liste("Exemple", noms, ("P3D", "exemple"), apres=change,
                aide="\n\n".join(f"{n} : {t}" for n, t in EXPLICATIONS.items()))  # fmt: skip
        z.legende(EXPLICATIONS.get(state.extra["P3D"]["exemple"], ""))
        for k, titre in zip(
            TABLES, ("Nœuds", "Pièces", "Charges nodales (repère global)", "Charges réparties (repère global)"),
            strict=True,
        ):  # fmt: skip
            z.texte(f"**{titre}**")
            z.table("P3D", k, cols[k])
            if k == "pieces":
                _materiaux(z, state.extra["P3D"]["pieces"], dm)
        z.case("Poids propre", ("P3D", "pp"), aide="ρ·g·A selon -Z, g = 9,81 m/s².")
        z.legende(
            "Poutres d'Euler-Bernoulli (déformation d'effort tranchant négligée). Repère local : x de début vers fin, "
            "z vertical pour une pièce horizontale (Iy = axe fort). β tourne la section autour de son axe."
        )

    def ajuste() -> None:
        panneau.setSizes([200, 1100] if state.v.get("zones.p3d.large") else [480, 820])

    def visu(z: Zone) -> None:
        ligne = z.colonnes([3, 2])
        ligne[0].case("Agrandir la visualisation", "zones.p3d.large", apres=ajuste,
                      aide="Élargit cette zone vers la gauche ; la saisie reste accessible dans la colonne étroite.")  # fmt: skip
        ligne[1].bouton("Calculer", calculer, primaire=True)
        calc = state.v.get("p3d.res")
        if calc is None:
            z.info("Choisissez un exemple ou remplissez les tableaux, puis cliquez sur « Calculer ».")
            return
        if calc["empreinte"] != repr(state.extra["P3D"]):
            z.avertissement(
                "Saisie modifiée depuis le dernier calcul : la vue et les résultats ci-dessous sont ceux de "
                "l'ancienne saisie. Cliquez sur « Calculer » pour les mettre à jour."
            )
        _resultats(z, calc["res"], calc["data"])

    sg, sd = Section(page, saisie), Section(page, visu, suit=True)
    sg.mode3d = sd.mode3d = True
    page.sections += [sg, sd]
    panneau = partage(sg, sd)
    ajuste()
    return panneau

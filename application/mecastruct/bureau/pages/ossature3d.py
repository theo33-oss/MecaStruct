"""Mode « Ossature 3D » de la page Poutres : saisie en tableaux, vue 3D, résultats du moteur frame3d.

Saisie en mm, N, N·m et N/m ; conversion en SI (m) avant l'appel à frame3d.solveFrame3D. La saisie vit dans
state.extra["P3D"] (quatre listes de lignes, la case « poids propre » et l'exemple choisi).
"""

import copy

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from mecastruct.bureau import exports, state
from mecastruct.bureau.widgets import Colonne, Zone, liste_col, nombre_col
from mecastruct.core import frame3d
from mecastruct.services import criteres
from mecastruct.services.exemples_3d import EXPLICATIONS, exemples
from mecastruct.services.ossature3d import (  # noqa: F401 : réexportés pour la page et les tests
    APPUIS,
    C_DEFORMEE,
    COMPOSANTES,
    EXEMPLES_DIM,
    LIAISONS,
    SECTIONS,
    TABLES,
    _amplification_auto,
    _csv,
    _donnees,
    _table_contraintes,
    _table_deplacements,
    _table_reactions,
    _tables_exemple,
    _vue_3d,
    bilan_latex,
)


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


def _verification(z: Zone, res: dict, data: dict) -> None:
    """Vérification à la main : bilan des actions avec valeurs, puis contraintes comparées à Re."""
    formules, contraintes, manquante = bilan_latex(res, data)
    z.texte(
        "**Équilibre global, refait à partir de vos données** : charges nodales + charges réparties (poids propre "
        "compris) + réactions du solveur = 0. Moments pris par rapport à l'origine (0, 0, 0)."
    )
    for f in formules:
        z.formule(f)
    z.legende(
        "Les sommes doivent être nulles (écart admis : 1e-6 de l'échelle des actions). "
        + ("Équilibre vérifié." if res["equilibre"]["ok"] else "ÉQUILIBRE NON VÉRIFIÉ : voir l'onglet Synthèse.")
    )
    z.texte(
        "**Contraintes** : σ = |N|/A + |My|/Wy + |Mz|/Wz, maximum sur les 21 points de chaque pièce, comparée à la "
        "limite élastique Re du matériau (sans coefficient de sécurité). Les efforts viennent du solveur "
        "(onglet Efforts internes)."
    )
    z.tableau(contraintes)
    if manquante:
        z.legende("σ non calculée pour une pièce sans module de flexion Wy ou Wz : saisissez-les (section « perso »).")


def _verdict(z: Zone, res: dict, data: dict) -> None:
    """Contrainte de la pièce la plus sollicitée face à Re (indicatif, sans coefficient de sécurité) ; équilibre."""
    eq = res["equilibre"]
    crit = criteres.ossature(res["contraintes"], {e["id"]: e.get("Re") for e in data["elements"]})
    if eq["ok"]:
        status = "Équilibre global vérifié (réactions + charges = 0). σ est comparée à Re sans coefficient de sécurité : à vous de juger la marge."
    else:
        status = f"Écart d'équilibre : ΣF = {np.round(eq['forces'], 6).tolist()} N, ΣM = {np.round(eq['moments'], 6).tolist()} N·m."
    if crit:
        z.modes(crit, status, None if eq["ok"] else False)
    else:
        z.statut(status, None if eq["ok"] else False)
    exports.boutons(z, "ossature", {k: v for k, v in state.extra["P3D"].items() if k != "exemple"}, "Ossature 3D")


def _resultats(z: Zone, res: dict, data: dict) -> None:
    _verdict(z, res, data)
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
            "Valeurs de la base de données de l'application (page Matériaux et profilés). "
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

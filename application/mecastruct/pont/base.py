"""Pont de la page « Matériaux et profilés » : consultation, ajouts de l'utilisateur, import et export.

La base est celle du calcul (DataManager). Les ajouts de l'utilisateur sont renvoyés à la page après chaque
changement ({"utilisateur": …}) : elle les garde dans le navigateur et les rejoue au démarrage (base.restaurer).
"""

import json
import math

import pandas as pd

from mecastruct.pont import noyau
from mecastruct.pont.noyau import calcul, dm

LIMITE_FICHIER = 500_000  # caractères


def _utilisateur() -> dict:
    return dm().exportUserData()


def _apres_changement(message: str) -> dict:
    noyau.invalider_formulaires()  # les listes de matériaux des formulaires doivent suivre
    return {"message": message, "utilisateur": _utilisateur()}


def _nb(v, defaut=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return defaut


@calcul("base.catalogue")
def catalogue(_s):
    """Catégories de matériaux, familles de profilés et table de matage."""
    base = dm()
    t = base.BearingPressures
    return {
        "categories": sorted(base.Materials["Category"].dropna().unique()),
        "familles": base.listProfileFamilies(),
        "matage": t.drop(columns=[c for c in t.columns if c not in ("Liaison", "Conditions", "Pmin", "Pmax", "Note")]),
        "utilisateur": [n for n in base.Materials.loc[base.Materials["IsUser"], "Name"]],
    }


@calcul("base.materiaux")
def materiaux(s):
    T = dm().Materials
    categories = s.get("categories")
    vue = T if not categories else T[T["Category"].isin(categories)]
    if s.get("recherche"):
        vue = vue[vue["Name"].str.contains(str(s["recherche"]), case=False, regex=False)]
    return pd.DataFrame({
        "Nom": vue["Name"], "Catégorie": vue["Category"], "E (GPa)": vue["E"] / 1e9, "G (GPa)": vue["G"] / 1e9,
        "ν (-)": vue["nu"], "Re (MPa)": vue["Re"] / 1e6, "Rm (MPa)": vue["Rm"] / 1e6, "α (1e-6/°C)": vue["alpha"] * 1e6,
        "ρ (kg/m³)": vue["rho"], "Ajouté par": vue["Author"], "Note": vue["Note"],
    })  # fmt: skip


@calcul("base.profils")
def profils(s):
    T = dm().Profiles[s["famille"]]
    return pd.DataFrame({
        "Désignation": T["Name"], "h (mm)": T["h"] * 1e3, "b (mm)": T["b"] * 1e3, "a (mm)": T["a"] * 1e3,
        "e (mm)": T["e"] * 1e3, "r (mm)": T["r"] * 1e3, "S (cm²)": T["S"] * 1e4, "Iz (cm⁴)": T["Iz"] * 1e8,
        "Iy (cm⁴)": T["Iy"] * 1e8, "Wz (cm³)": T["Wz"] * 1e6, "Wy (cm³)": T["Wy"] * 1e6, "rz (mm)": T["rz"] * 1e3,
        "ry (mm)": T["ry"] * 1e3, "masse (kg/m)": T["mass"], "c (mm)": T["c"] * 1e3, "Ajouté par": T["Author"],
    })  # fmt: skip


@calcul("base.ajouter_materiau")
def ajouter_materiau(s):
    g = _nb(s.get("G"))
    dm().addMaterial({
        "Name": str(s["nom"]).strip(), "Category": str(s.get("categorie", "")).strip() or "Utilisateur",
        "E": _nb(s["E"]) * 1e9, "G": g * 1e9 if g > 0 else math.nan, "nu": _nb(s["nu"]),
        "Re": _nb(s["Re"]) * 1e6, "Rm": _nb(s["Rm"]) * 1e6, "alpha": _nb(s["alpha"]) * 1e-6, "rho": _nb(s["rho"]),
        "Note": "Matériau utilisateur (saisi dans l'interface).", "Author": str(s.get("auteur", "")).strip(),
    })  # fmt: skip
    return _apres_changement(f"Matériau « {str(s['nom']).strip()} » ajouté.")


@calcul("base.supprimer_materiau")
def supprimer_materiau(s):
    dm().removeMaterial(s["nom"])
    return _apres_changement(f"Matériau « {s['nom']} » supprimé.")


@calcul("base.ajouter_profil")
def ajouter_profil(s):
    dm().addProfile(s["famille"], {
        "Name": str(s["nom"]).strip(), "h": _nb(s["h"]) * 1e-3, "b": _nb(s["b"]) * 1e-3, "a": _nb(s["a"]) * 1e-3,
        "e": _nb(s["e"]) * 1e-3, "r": _nb(s["r"]) * 1e-3, "Author": str(s.get("auteur", "")).strip(),
    })  # fmt: skip
    return _apres_changement(f"Profilé « {str(s['nom']).strip()} » ajouté à la famille {s['famille']}.")


@calcul("base.exporter")
def exporter(_s):
    """Ajouts de l'utilisateur au format de l'application de bureau (importUserData)."""
    return {"nom": "MecaStruct_ajouts_utilisateur.json",
            "texte": json.dumps({"app": "MecaStruct RdM Pro", "utilisateur": _utilisateur()}, ensure_ascii=False, indent=1)}  # fmt: skip


@calcul("base.importer")
def importer(s):
    """Fusionne un fichier d'ajouts (taille limitée, chaque ajout est revérifié par le calcul)."""
    texte = s["texte"]
    if len(texte) > LIMITE_FICHIER:
        raise ValueError("Fichier trop gros pour des ajouts MecaStruct.")
    try:
        d = json.loads(texte)
    except ValueError as err:
        raise ValueError(f"Ce fichier n'est pas un fichier d'ajouts MecaStruct (JSON illisible : {err}).") from err
    donnees = d.get("utilisateur") if isinstance(d, dict) and d.get("app") == "MecaStruct RdM Pro" else d
    if not isinstance(donnees, dict) or not ({"materials", "profiles"} & set(donnees)):
        raise ValueError("Ce fichier n'est pas un fichier d'ajouts MecaStruct.")
    n = dm().importUserData(donnees)
    return _apres_changement(f"{n} ajout(s) importé(s).")


@calcul("base.restaurer")
def restaurer(s):
    """Rejoue au démarrage les ajouts gardés dans le navigateur ; un ajout illisible est ignoré (compté)."""
    donnees = s.get("utilisateur") or {}
    ignores = 0
    for m in donnees.get("materials", []):
        try:
            dm().addMaterial(m)
        except Exception:  # noqa: BLE001 : une entrée abîmée n'empêche pas les autres
            ignores += 1
    for fam, lignes in (donnees.get("profiles") or {}).items():
        for p in lignes:
            try:
                dm().addProfile(fam, p)
            except Exception:  # noqa: BLE001
                ignores += 1
    noyau.invalider_formulaires()
    return {"ignores": ignores}

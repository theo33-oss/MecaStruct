"""Export « bloc-notes » d'un calcul : un fichier .txt lisible partout (données, critères, résultats, démarche).

Les données viennent de la description du formulaire (pont/formulaire.py) : mêmes libellés et unités que la page.
"""

import re
from datetime import datetime

import pandas as pd

from mecastruct import __version__

LARGEUR = 100
_SCALAIRES = ("nombre", "liste", "case", "texte")


def nombre(x, chiffres: int = 5) -> str:
    """Nombre à la française (virgule décimale), sans chiffres inutiles."""
    if isinstance(x, bool):
        return "oui" if x else "non"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if x != x:  # NaN
            return "-"
        if x in (float("inf"), float("-inf")):
            return "infini"
        return format(x, f".{chiffres}g").replace(".", ",")
    return "" if x is None else str(x)


_NOMBRE_POINT = re.compile(r"^[-−+]?\d+\.\d+(e[-+]?\d+)?$")
_DECIMALE = re.compile(r"(\d)\.(\d)")


def fr(texte) -> str:
    """Virgule décimale dans une phrase du calcul (« 159.2 MPa » devient « 159,2 MPa »), comme sur la page."""
    return _DECIMALE.sub(r"\1,\2", str(texte))


def _visible(champ: dict, saisie: dict) -> bool:
    """Champ affiché sur la page : chacune de ses conditions (une seule, ou une liste) est remplie."""
    si = champ.get("si") or []
    return all(saisie.get(k["id"]) in k["valeurs"] for k in ([si] if isinstance(si, dict) else si))


def donnees(formulaire: dict, saisie: dict) -> list[dict]:
    """Champs simples du formulaire : [{"id", "groupe", "libelle", "valeur" (texte affiché), "brut", "unite"}]."""
    lignes = []
    for g in formulaire.get("groupes", []):
        for c in g["champs"]:
            if c.get("type") not in _SCALAIRES or c["id"] not in saisie or not (_visible(c, saisie) or c.get("exporte")):
                continue
            v = brut = saisie[c["id"]]
            if c["type"] == "liste" and c.get("etiquettes") and v in c["options"]:
                v = c["etiquettes"][c["options"].index(v)]
            lignes.append({"id": c["id"], "groupe": g["titre"], "libelle": c["libelle"], "valeur": v, "brut": brut,
                           "unite": c.get("unite", ""), "securite": bool(c.get("securite"))})  # fmt: skip
    return lignes


def tableaux_saisie(formulaire: dict, saisie: dict) -> dict[str, pd.DataFrame]:
    """Tableaux et matrices saisis (appuis, charges, nœuds, tenseur) : libellé → tableau."""
    tables = {}
    for g in formulaire.get("groupes", []):
        for c in g["champs"]:
            v = saisie.get(c.get("id"))
            if not v or not _visible(c, saisie):
                continue
            if c.get("type") == "tableau":
                cols = {k["id"]: k["libelle"] for k in c["colonnes"]}
                tables[c["libelle"]] = pd.DataFrame([{lib: r.get(k, "") for k, lib in cols.items()} for r in v])
            elif c.get("type") == "matrice":
                noms = c.get("noms") or [str(i + 1) for i in range(len(v))]
                tables[c["libelle"]] = pd.DataFrame(v, columns=noms).assign(**{"": noms}).set_index("").reset_index()
    return tables


def _colonnes(entetes: list[str], lignes: list[list[str]]) -> list[str]:
    """Tableau en texte : colonnes alignées par des espaces, trait sous les en-têtes."""
    larg = [max(len(str(x)) for x in col) for col in zip(entetes, *lignes, strict=False)]
    fmt = lambda r: "  ".join(str(x).ljust(w) for x, w in zip(r, larg, strict=False)).rstrip()  # noqa: E731
    return [fmt(entetes), "  ".join("-" * w for w in larg), *map(fmt, lignes)]


def _table(t: pd.DataFrame, maxi: int = 60) -> list[str]:
    lignes = [[fr(nombre(v)) if _NOMBRE_POINT.match(nombre(v).strip()) else nombre(v) for v in r]
              for r in t.head(maxi).itertuples(index=False)]  # fmt: skip
    out = _colonnes([str(c) for c in t.columns], lignes)
    if len(t) > maxi:
        out.append(f"… {len(t) - maxi} ligne(s) de plus : voir l'export Excel.")
    return out


def _titre(t: str) -> list[str]:
    return ["", t.upper(), "=" * len(t)]


def chiffres(c: dict, en_marge: bool = False) -> tuple[str, str, str]:
    """(« 159,2 MPa pour 156,7 MPa admissibles », « taux 102 % », « s = 1,48 · demandé 1,5 » ou « marge 17 % »).

    `en_marge` : une résistance s'écrit en marge de sécurité (s − 1, en %) : « marge 48 % · demandée 50 % »."""
    u = f" {c['unite']}" if c["unite"] else ""
    sans_unite = not c["unite"] and c["limite"] == 1  # rapport d'une norme (effort / résistance ≤ 1) : le taux suffit
    mot = "admissibles" if c["sens"] == "max" else "requis"
    valeurs = "" if sans_unite else f"{nombre(c['valeur'], 4)}{u} pour {nombre(c['limite'], 4)}{u} {mot}"
    taux = f"taux {nombre(100 * c['taux'], 3)} %"
    if c.get("genre", "resistance") == "resistance":
        if en_marge:
            return (valeurs, taux, f"marge {nombre(100 * (c['s_obtenu'] - 1), 3)} % · demandée "
                                   f"{nombre(100 * (c['s_demande'] - 1), 3)} %")  # fmt: skip
        return valeurs, taux, f"s = {nombre(c['s_obtenu'], 3)} · demandé {nombre(c['s_demande'], 3)}"
    marge_ = f"marge {nombre(100 * (1 - c['taux']), 3)} %" if c["taux"] <= 1 else f"dépassement {nombre(100 * (c['taux'] - 1), 3)} %"
    return valeurs, taux, marge_


def phrase_bilan(crit: list[dict]) -> str:
    """« Les 2 modes de ruine sont admissibles », « 1 mode de ruine non admissible sur 3 »."""
    ko = sum(1 for c in crit if not c["ok"])
    if ko:
        return f"{ko} mode{'s' if ko > 1 else ''} de ruine non admissible{'s' if ko > 1 else ''} sur {len(crit)}"
    return f"Les {len(crit)} modes de ruine sont admissibles" if len(crit) > 1 else "Le mode de ruine est admissible"


def phrase_etat(status) -> str:
    """Ligne d'état du calcul : virgule décimale et majuscule initiale."""
    t = fr(status)
    return t[:1].upper() + t[1:] if re.match(r"[a-zà-ÿ]{2}", t) else t


def lignes_criteres(crit: list[dict], en_marge: bool = False) -> list[str]:
    if not crit:
        return ["Ce calcul ne compare pas de valeur à une limite."]
    lignes, groupe = [], None
    for c in crit:
        if c.get("groupe") and c["groupe"] != groupe:
            lignes.append([f"[{c['groupe']}]", "", "", "", ""])
        groupe = c.get("groupe") or None
        valeurs, taux, marge = chiffres(c, en_marge)
        lignes.append([c["mode"], valeurs, taux.removeprefix("taux "), marge, "ADMISSIBLE" if c["ok"] else "NON ADMISSIBLE"])
    return _colonnes(["Mode de ruine", "Valeur et limite", "Taux", "Coefficient ou marge", "Verdict"], lignes)


def texte(titre: str, formulaire: dict, saisie: dict, sortie: dict, crit: list[dict], quand: datetime | None = None) -> str:
    """Note de calcul en texte brut. `sortie` : {status, ok, tables (DataFrame), rapport}."""
    quand = quand or datetime.now()
    ok = sortie.get("ok")
    verdict = "VÉRIFIÉ" if ok is True else "NON VÉRIFIÉ" if ok is False else "sans verdict (calcul d'information)"
    L = [f"MecaStruct RdM {__version__} - {titre}", f"Calcul du {quand:%d/%m/%Y à %H h %M}", "-" * LARGEUR]
    en_marge = saisie.get("_securite") == "marge"  # réglage de la page : sécurité donnée en marge (%)
    L += _titre("Données")
    groupe = None
    for d in donnees(formulaire, saisie):
        if d["groupe"] != groupe:
            groupe = d["groupe"]
            L += ["", f"[{groupe}]"]
        ligne = f"  {d['libelle']:<58.58} {nombre(d['valeur'], 8)} {d['unite']}".rstrip()
        if en_marge and d["securite"] and isinstance(d["brut"], (int, float)):
            ligne += f"  (marge de sécurité {nombre(100 * (d['brut'] - 1), 8)} %)"
        L.append(ligne)
    for nom, t in tableaux_saisie(formulaire, saisie).items():
        L += ["", f"[{nom}]", *("  " + x for x in _table(t))]
    L += _titre("Verdict et modes de ruine")
    L += [f"Verdict : {verdict}", fr(sortie.get("status", "")), ""]
    L += lignes_criteres(crit, en_marge)
    tables = {n: t for n, t in (sortie.get("tables") or {}).items() if isinstance(t, pd.DataFrame) and len(t)}
    if tables:
        L += _titre("Résultats")
        for nom, t in tables.items():
            L += ["", f"[{nom}]", *("  " + x for x in _table(t))]
    rapport = [fr(x) for x in sortie.get("rapport") or [] if str(x).strip()]
    if rapport:
        L += _titre("Démarche du calcul")
        L += [x if x.startswith("===") else "- " + x for x in rapport]
    L += ["", "-" * LARGEUR, "Outil pédagogique et d'aide au pré-dimensionnement, fourni sans garantie :",
          "vérifiez les résultats avant tout usage réel. Limites : fichier LIMITES.md du projet."]  # fmt: skip
    return "﻿" + "\r\n".join(L) + "\r\n"

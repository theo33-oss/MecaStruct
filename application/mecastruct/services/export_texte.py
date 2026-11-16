"""Export « bloc-notes » d'un calcul : un fichier .txt lisible partout (données, critères, résultats, démarche).

Les données viennent de la description du formulaire (pont/formulaire.py) : mêmes libellés et unités que la page.
"""

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


def _visible(champ: dict, saisie: dict) -> bool:
    si = champ.get("si")
    return not si or saisie.get(si["id"]) in si["valeurs"]


def donnees(formulaire: dict, saisie: dict) -> list[dict]:
    """Champs simples du formulaire : [{"id", "groupe", "libelle", "valeur" (texte affiché), "brut", "unite"}]."""
    lignes = []
    for g in formulaire.get("groupes", []):
        for c in g["champs"]:
            if c.get("type") not in _SCALAIRES or c["id"] not in saisie or not _visible(c, saisie):
                continue
            v = brut = saisie[c["id"]]
            if c["type"] == "liste" and c.get("etiquettes") and v in c["options"]:
                v = c["etiquettes"][c["options"].index(v)]
            lignes.append({"id": c["id"], "groupe": g["titre"], "libelle": c["libelle"], "valeur": v, "brut": brut,
                           "unite": c.get("unite", "")})  # fmt: skip
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
    lignes = [[nombre(v) for v in r] for r in t.head(maxi).itertuples(index=False)]
    out = _colonnes([str(c) for c in t.columns], lignes)
    if len(t) > maxi:
        out.append(f"… {len(t) - maxi} ligne(s) de plus : voir l'export Excel.")
    return out


def _titre(t: str) -> list[str]:
    return ["", t.upper(), "=" * len(t)]


def lignes_criteres(crit: list[dict]) -> list[str]:
    if not crit:
        return ["Ce calcul ne compare pas de valeur à une limite."]
    lignes = []
    for c in crit:
        u = f" {c['unite']}" if c["unite"] else ""
        signe = "≤" if c["sens"] == "max" else "≥"
        lignes.append([c["mode"], f"{nombre(c['valeur'], 4)}{u} {signe} {nombre(c['limite'], 4)}{u}", f"{nombre(100 * c['taux'], 3)} %",
                       f"{nombre(c['s_obtenu'], 3)} (demandé {nombre(c['s_demande'], 3)})", "ADMISSIBLE" if c["ok"] else "NON ADMISSIBLE"])  # fmt: skip
    return _colonnes(["Mode de ruine", "Valeur et limite", "Taux", "Coefficient de sécurité", "Verdict"], lignes)


def texte(titre: str, formulaire: dict, saisie: dict, sortie: dict, crit: list[dict], quand: datetime | None = None) -> str:
    """Note de calcul en texte brut. `sortie` : {status, ok, tables (DataFrame), rapport}."""
    quand = quand or datetime.now()
    ok = sortie.get("ok")
    verdict = "VÉRIFIÉ" if ok is True else "NON VÉRIFIÉ" if ok is False else "sans verdict (calcul d'information)"
    L = [f"MecaStruct RdM Pro {__version__} - {titre}", f"Calcul du {quand:%d/%m/%Y à %H h %M}", "-" * LARGEUR]
    L += _titre("Données")
    groupe = None
    for d in donnees(formulaire, saisie):
        if d["groupe"] != groupe:
            groupe = d["groupe"]
            L += ["", f"[{groupe}]"]
        L.append(f"  {d['libelle']:<58.58} {nombre(d['valeur'], 8)} {d['unite']}".rstrip())
    for nom, t in tableaux_saisie(formulaire, saisie).items():
        L += ["", f"[{nom}]", *("  " + x for x in _table(t))]
    L += _titre("Verdict et modes de ruine")
    L += [f"Verdict : {verdict}", str(sortie.get("status", "")), ""]
    L += lignes_criteres(crit)
    tables = {n: t for n, t in (sortie.get("tables") or {}).items() if isinstance(t, pd.DataFrame) and len(t)}
    if tables:
        L += _titre("Résultats")
        for nom, t in tables.items():
            L += ["", f"[{nom}]", *("  " + x for x in _table(t))]
    rapport = [str(x) for x in sortie.get("rapport") or [] if str(x).strip()]
    if rapport:
        L += _titre("Démarche du calcul")
        L += [x if x.startswith("===") else "- " + x for x in rapport]
    L += ["", "-" * LARGEUR, "Outil pédagogique et d'aide au pré-dimensionnement, fourni sans garantie :",
          "vérifiez les résultats avant tout usage réel. Limites : fichier LIMITES.md du projet."]  # fmt: skip
    return "﻿" + "\r\n".join(L) + "\r\n"

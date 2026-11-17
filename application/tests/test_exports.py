"""Modes de ruine, export bloc-notes et Excel de validation (pont web)."""

import base64
import io
import json
import math
import re

import pytest
from openpyxl import load_workbook

from mecastruct.pont import noyau
from mecastruct.services import criteres, export_validation

noyau.charger("structures")
FORMULAIRES = noyau.tous_formulaires()
CALCULS = ["beam", "truss", "ossature", "sec", "tra", "cis", "tor", "fle", "fla", "ten", "hoo", "jau",
           "aju", "fre", "pal", "rlt", "rlt_ens", "eng", "trn", "epi", "frn", "emb", "mot"]  # fmt: skip
AVEC_CRITERES = ["beam", "truss", "tra", "cis", "tor", "fle", "fla", "ten", "fre", "pal", "rlt", "eng", "emb", "mot"]


def appel(ident, saisie=None):
    r = json.loads(noyau.appeler(ident, json.dumps(FORMULAIRES[ident.split(".")[0]]["defaut"] if saisie is None else saisie)))
    assert r["ok"], r.get("erreur")
    return r["sortie"]


# ---------------------------------------------------------------------------------------------- modes de ruine


def test_ligne_sens_max_et_min():
    c = criteres.ligne("σ", 120.0, 150.0, "MPa", 1.5)
    assert c["taux"] == pytest.approx(0.8) and c["s_obtenu"] == pytest.approx(1.875) and c["ok"]
    d = criteres.ligne("durée", 1000.0, 1500.0, "h", sens="min")
    assert d["taux"] == pytest.approx(1.5) and d["s_obtenu"] == pytest.approx(2 / 3) and not d["ok"]
    assert criteres.ligne("x", float("nan"), 1.0) is None and criteres.ligne("x", 1.0, 0.0) is None


def test_poutre_de_l_exemple():
    c = appel("beam", {**FORMULAIRES["beam"]["defaut"], "selfw": False})["criteres"]  # sans le poids propre, coché de base
    flexion = next(x for x in c if x["mode"].startswith("Flexion"))
    assert flexion["s_obtenu"] == pytest.approx(235 / 120.672, rel=1e-3) and flexion["s_demande"] == 1.5
    assert flexion["taux"] == pytest.approx(120.672 / 156.667, rel=1e-3)
    assert any(x["mode"].startswith("Effort tranchant") and x["taux"] == pytest.approx(0.1244, rel=1e-2) for x in c)


@pytest.mark.parametrize("ident", AVEC_CRITERES)
def test_criteres_coherents_avec_le_verdict(ident):
    s = appel(ident)
    c = s["criteres"]
    assert c, ident
    assert c == criteres.trier(c)  # études dans l'ordre de la page, mode le plus sollicité en premier
    assert all(x["genre"] in ("resistance", "limite") for x in c)
    for x in c:
        assert x["ok"] == (x["s_obtenu"] >= x["s_demande"] * (1 - 1e-9)), x
    if s["ok"] is True and ident not in ("cis", "tor", "tra"):  # leur verdict ne porte que sur la résistance
        assert all(x["ok"] for x in c), c
    if s["ok"] is False:
        assert not all(x["ok"] for x in c), c


@pytest.mark.parametrize("ident", ["hoo", "jau", "aju", "rlt_ens", "trn", "frn"])
def test_calculs_sans_critere(ident):
    assert appel(ident).get("criteres", []) == []


def test_resultat_brut_absent_de_la_page():
    assert all("_brut" not in appel(i) for i in ("tra", "mot"))


def test_eurocode_et_fatigue():
    ec3 = appel("beam.ec3")
    assert ec3["criteres"] and all(x["limite"] == 1.0 for x in ec3["criteres"])
    fat = appel("beam.fatigue")["criteres"]
    assert len(fat) == 1 and fat[0]["sens"] == "min" and fat[0]["s_obtenu"] == fat[0]["valeur"]


# -------------------------------------------------------------------------------------------------- bloc-notes


@pytest.mark.parametrize("ident", CALCULS)
def test_bloc_notes(ident):
    r = appel(ident + ".texte")
    t = r["texte"]
    assert r["nom"].endswith("_note.txt") and t.startswith("﻿") and "\r\n" in t
    for mot in ("DONNÉES", "VERDICT ET MODES DE RUINE", "sans garantie"):
        assert mot in t
    if ident in AVEC_CRITERES:
        assert "ADMISSIBLE" in t and "Coefficient ou marge" in t


def test_bloc_notes_de_la_traction():
    t = appel("tra.texte")["texte"]
    assert "N (> 0 traction)" in t and "50 kN" in t and "NON VÉRIFIÉ" in t and "159,2 MPa pour 156,7 MPa admissibles" in t


# ------------------------------------------------------------------------------------- Excel de validation

_FONCTIONS = {"PI": lambda: math.pi, "SQRT": math.sqrt, "ABS": abs, "MAX": max, "MIN": min, "TAN": math.tan, "COS": math.cos,
              "RADIANS": math.radians, "IF": lambda c, a, b: a if c else b}  # fmt: skip


def evaluer(wb, feuille, cellule, pile=()):
    """Valeur d'une cellule : les formules du classeur sont recalculées ici (sous-ensemble d'Excel utilisé)."""
    v = wb[feuille][cellule].value
    if not (isinstance(v, str) and v.startswith("=")):
        return v
    assert (feuille, cellule) not in pile
    expr = v[1:]

    def ref(m):
        f = (m.group(1) or m.group(2) or feuille)
        return repr(evaluer(wb, f, m.group(3).replace("$", ""), (*pile, (feuille, cellule))))

    expr = re.sub(r"(?:'([^']+)'!|(\w+)!)?(\$?[A-Z]{1,2}\$?\d+)(?![\w(])", ref, expr)
    expr = expr.replace("^", "**").replace("<=", "≤").replace(">=", "≥").replace("=", "==").replace("≤", "<=").replace("≥", ">=")
    return eval(expr, {"__builtins__": {}}, _FONCTIONS)  # noqa: S307 : formules écrites par export_validation


def classeur(ident, saisie=None):
    r = appel(ident + ".validation", saisie)
    assert r["nom"].endswith("_validation.xlsx")
    return load_workbook(io.BytesIO(base64.b64decode(r["base64"])))


@pytest.mark.parametrize("ident", sorted(export_validation.FORMULES))
def test_formules_excel_redonnent_mecastruct(ident):
    wb = classeur(ident)
    ws = wb["Calcul"]
    assert ws.max_row >= 3
    for n in range(2, ws.max_row + 1):
        excel, meca = evaluer(wb, "Calcul", f"C{n}"), ws[f"D{n}"].value
        assert ws[f"C{n}"].value.startswith("=")
        assert excel == pytest.approx(meca, rel=1e-3, abs=1e-12), (ident, ws[f"A{n}"].value)
        assert evaluer(wb, "Calcul", f"G{n}") == "OK"


def test_formules_suivent_une_donnee_modifiee():
    wb = classeur("tra")
    wd = wb["Données"]
    ligne = next(n for n in range(2, wd.max_row + 1) if wd[f"A{n}"].value == "N (> 0 traction)")
    avant = evaluer(wb, "Calcul", "C2")
    wd[f"B{ligne}"].value = 100.0
    assert evaluer(wb, "Calcul", "C2") == pytest.approx(2 * avant)
    assert evaluer(wb, "Calcul", "G2") == "ÉCART"  # la colonne MecaStruct garde l'ancien résultat


@pytest.mark.parametrize("ident", CALCULS)
def test_classeur_de_chaque_calcul(ident):
    wb = classeur(ident)
    assert wb.sheetnames[:2] == ["Lisez-moi", "Données"] and "Critères" in wb.sheetnames
    assert ("Calcul" in wb.sheetnames) == (ident in export_validation.FORMULES)
    wk = wb["Critères"]
    crit = appel(ident).get("criteres", [])
    for n, c in enumerate(crit, start=2):
        assert evaluer(wb, "Critères", f"G{n}") == pytest.approx(c["s_obtenu"])
        assert evaluer(wb, "Critères", f"H{n}") == pytest.approx(c["taux"])
        assert evaluer(wb, "Critères", f"I{n}") == ("Admissible" if c["taux"] <= 1 else "Non admissible")
    assert wk["A1"].value == "Mode de ruine"


def test_cas_non_refaits_dans_excel():
    s = {**FORMULAIRES["tra"]["defaut"], "varS": True}
    assert "Calcul" not in classeur("tra", s).sheetnames  # section variable : intégrale, pas de formule simple


def test_aucun_texte_de_la_saisie_ne_devient_une_formule():
    s = {**FORMULAIRES["tra"]["defaut"], "Sexpr": "=CMD|' /C calc'!A0"}
    wb = classeur("tra", s)
    for ws in wb:
        for ligne in ws.iter_rows():
            for c in ligne:
                if isinstance(c.value, str) and c.value.startswith("="):
                    assert ws.title in ("Calcul", "Critères") and "CMD" not in c.value


def test_audit_utilisateur():
    """Constats de l'audit : études du cisaillement séparées, libellés complets, pas de « vérifié » sans limite."""
    cis = appel("cis")
    assert list(dict.fromkeys(x["groupe"] for x in cis["criteres"])) == ["Cisaillement simple et Jourawski", "Matage", "Clavette", "Goupille"]
    assert cis["ok"] is True and appel("tor")["ok"] is True  # exemples du site admissibles
    assert appel("tra")["ok"] is False  # un exemple qui ne passe pas est gardé exprès
    assert {x["mode"] for x in appel("pal")["criteres"]} >= {"Pression P", "Vitesse de glissement V"}
    assert appel("aju")["ok"] is None
    epi = appel("epi")
    assert [c["ok"] for c in epi["controles"]] == [True, True] and epi["titre_controles"] == "Conditions de montage"
    assert appel("rlt")["criteres"][0]["genre"] == "limite" and appel("fle")["criteres"][0]["genre"] == "resistance"
    assert FORMULAIRES["tra"]["groupes"][0]["champs"][3]["familles"]  # matériaux rangés par famille


def test_audit_des_pages_restantes():
    oss = appel("ossature")
    c = oss["criteres"]
    assert oss["ok"] is None and len(c) == 1 and c[0]["unite"] == "MPa" and c[0]["mode"].startswith("Contrainte σ max, pièce")
    assert c[0]["valeur"] == pytest.approx(102.9, rel=1e-2) and c[0]["limite"] == pytest.approx(235.0)
    assert appel("truss")["status"].startswith("Treillis isostatique (degré d'hyperstaticité h = 0)")
    assert "lent" not in FORMULAIRES["sec"]


def test_fichiers_ouverts_pour_de_vrai():
    """Constats du contrôle dans Excel et le Bloc-notes : nombres en vrais nombres, virgule dans le texte."""
    wb = classeur("tra")
    ws = wb["Synthèse"]
    valeurs = [c.value for ligne in ws.iter_rows(min_row=2, min_col=2, max_col=2) for c in ligne]
    assert any(isinstance(v, float) and v == pytest.approx(159.155) for v in valeurs)  # pas le texte « 159.155 »
    t = appel("tra.texte")["texte"]
    assert "σmax = 159,2 MPa" in t and "159.2" not in t and "159,155" in t
    assert "\n" not in t.replace("\r\n", "")  # fins de ligne Windows partout
    assert "marge" in appel("rlt.texte")["texte"] and "[Matage]" in appel("cis.texte")["texte"]


def test_bloc_notes_en_marge_de_securite():
    """Réglage « marge (%) » de la page : le bloc-notes écrit la marge (s − 1) à côté de s, le calcul ne change pas."""
    from mecastruct.pont import noyau

    noyau.charger("structures")
    s = json.loads(json.dumps(noyau.tous_formulaires()["beam"]["defaut"]))
    s["s"] = 1.3
    coef = json.loads(noyau.appeler("beam.texte", json.dumps(s)))["sortie"]["texte"]
    marge = json.loads(noyau.appeler("beam.texte", json.dumps({**s, "_securite": "marge"})))["sortie"]["texte"]
    assert "marge de sécurité 30 %" in marge and "marge de sécurité" not in coef
    assert "demandée 30 %" in marge and "demandé 1,3" in coef


def test_champs_de_securite_reperes():
    """Chaque champ « Coefficient de sécurité » des pages porte le marqueur qui propose la marge en %."""
    from mecastruct.pont import noyau

    noyau.charger("machines"); noyau.charger("outils"); noyau.charger("structures")
    trouves = [(i, c["id"]) for i, f in noyau.tous_formulaires().items() for g in f.get("groupes", []) for c in g["champs"] if c.get("securite")]
    assert len(trouves) >= 10
    assert ("beam", "s") in trouves and ("fla", "s") in trouves

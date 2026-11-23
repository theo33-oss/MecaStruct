"""Glossaire des symboles : lu dans les formulaires et les fiches (rien d'écrit à la main), le même sur le site et le bureau."""

import json
import re
from pathlib import Path

import pytest

from mecastruct.pont import noyau
from mecastruct.services import glossaire
from mecastruct.services.glossaire import _champs, _cle, _formulaires

RACINE = Path(__file__).resolve().parents[2]
APP_JS = (RACINE / "docs" / "app.js").read_text(encoding="utf-8")
RECHERCHE_JS = (RACINE / "docs" / "js" / "recherche.js").read_text(encoding="utf-8")
PAGES_SITE = set(re.findall(r'\{ id: "([a-z-]+)", titre: "[^"]+", famille', APP_JS))


@pytest.fixture(scope="module")
def entrees():
    return glossaire.entrees()


def test_chaque_entree_a_un_symbole_un_nom_et_au_moins_une_page(entrees):
    assert len(entrees) > 100
    for e in entrees:
        assert e["symbole"].strip() and e["nom"].strip() and e["latex"].strip(), e
        assert e["pages"], e


def test_pas_de_doublon_exact(entrees):
    cles = [(e["symbole"], _cle(e["nom"])) for e in entrees]
    assert len(cles) == len(set(cles))


def test_chaque_page_citee_existe_sur_le_site(entrees):
    assert {"poutres", "sollicitations", "roulements"} <= PAGES_SITE
    for e in entrees:
        assert set(e["pages"]) <= PAGES_SITE, e


def test_les_symboles_des_pages_principales_sont_presents(entrees):
    symboles = {e["symbole"] for e in entrees}
    # E, L, F, M, σ, τ : tous sont dans les formulaires ou les fiches ; I n'existe qu'avec ses indices (Ix, Iy, Iz)
    for s in ("E", "L", "F", "M", "σ", "τ", "Re", "S", "N", "Kt"):
        assert s in symboles, s
    assert {"Ix", "Iy", "Iz"} & symboles


def test_un_meme_symbole_peut_avoir_deux_sens_avec_leurs_pages(entrees):
    n = [e for e in entrees if e["symbole"] == "N"]
    assert len({e["nom"] for e in n}) >= 2 and all(e["pages"] for e in n)


def test_aucun_nom_n_est_invente(entrees):
    """Chaque nom est un texte déjà présent dans l'application : libellé ou aide d'un champ, ou variable d'une fiche."""
    textes = []
    for c in _champs(_formulaires()):
        textes += [c["libelle"], c["aide"]]
    fiches = json.loads((RACINE / "application" / "data" / "formula_sheets.json").read_text(encoding="utf-8"))["sheets"]
    textes += [f.get("vars") or "" for feuille in fiches.values() for f in feuille]
    corpus = " ".join(" ".join(t.split()) for t in textes).casefold()
    for e in entrees:
        assert _cle(e["nom"]) in corpus, e


def test_latex_des_symboles():
    assert glossaire.latex("Mfz") == "M_{fz}"
    assert glossaire.latex("σxx") == r"\sigma_{xx}"
    assert glossaire.latex("ΔT") == r"\Delta T"
    assert glossaire.latex("Padm") == r"P_{\mathrm{adm}}"
    assert glossaire.latex("Z21") == "Z_{21}"
    assert glossaire.latex("tw = a") == "t_{w} = a"
    assert glossaire.latex("q(x)") == "q(x)"
    assert glossaire.latex("α") == r"\alpha"
    assert glossaire.latex("L'") == "L'"


def test_les_symboles_sans_nom_sont_listes_et_absents_du_glossaire(entrees):
    manque = glossaire.sans_nom()
    assert manque and all(pages for _, pages in manque)
    presents = {(e["symbole"], p) for e in entrees for p in e["pages"]}
    assert not [(s, p) for s, pages in manque for p in pages if (s, p) in presents]


def test_le_pont_rend_les_memes_entrees(entrees):
    r = json.loads(noyau.appeler("glossaire"))
    assert r["ok"]
    sortie = r["sortie"]["entrees"]
    assert [(e["symbole"], e["nom"]) for e in sortie] == [(e["symbole"], e["nom"]) for e in entrees]
    assert all("source" not in e for e in sortie)


def test_les_symboles_de_la_recherche_suivent_le_glossaire(entrees):
    from mecastruct.bureau.recherche import SYMBOLES_GLOSSAIRE

    attendu = list(dict.fromkeys(e["symbole"] for e in entrees))
    assert SYMBOLES_GLOSSAIRE.split("|") == attendu
    assert re.search(r'const SYMBOLES_GLOSSAIRE = "([^"]*)"', RECHERCHE_JS).group(1).split("|") == attendu


def test_la_page_du_site_est_dans_donnees_et_aide_apres_les_references():
    ordre = re.findall(r'\{ id: "([a-z-]+)", titre: "[^"]+", famille: "donnees"', APP_JS)
    assert ordre.index("references") + 1 == ordre.index("glossaire") < ordre.index("limites")
    index = (RACINE / "docs" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<script defer src="js/glossaire\.js\?v=[0-9a-f]{8}"', index)
    assert '["glossaire", "", ""' in RECHERCHE_JS

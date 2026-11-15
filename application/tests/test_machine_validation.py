"""Tests du dossier de validation des pages de cours (machine_validation) et de son bouton (machine_dossier)."""

import copy
import itertools
import re
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QAbstractButton

from mecastruct.bureau import state

from mecastruct.core.data_manager import DataManager
from mecastruct.services import machine_courses as mc
from mecastruct.services import machine_validation as mv
from mecastruct.services import validation_report as vr


@pytest.fixture(scope="module")
def dm():
    return DataManager()


def _pages(dm) -> dict:
    """Pour chaque page : [(titre du calcul, type, saisie par défaut, résultat du solveur)]."""
    d = {
        "Roulements": [
            ("Durée de vie", "bearing", mc.defaultBearingInput(), mc.computeBearingLife),
            ("Ensemble de roulements", "bearingSet", mc.defaultBearingSetInput(), mc.computeBearingSet),
        ],
        "Engrenages": [
            ("Engrènement", "gearMesh", mc.defaultGearInput(), lambda s: mc.computeGearMesh(s, dm)),
            ("Train d'engrenages", "gearTrain", mc.defaultGearTrainInput(), mc.computeGearTrain),
        ],
        "Trains épicycloïdaux": [("Train épicycloïdal", "planetary", mc.defaultPlanetaryInput(), mc.computePlanetary)],
        "Freins et embrayages": [
            ("Frein à disque", "brake", mc.defaultBrakeInput(), mc.computeBrake),
            ("Embrayage", "clutch", mc.defaultClutchInput(), mc.computeClutch),
        ],
        "Dimensionnement moteur": [("Moteur", "motor", mc.defaultMotorInput(), mc.computeMotor)],
    }
    return {p: [(n, t, s, f(s)) for n, t, s, f in cs] for p, cs in d.items()}


def _bilan(html: str) -> tuple[int, int]:
    m = re.search(r"(\d+) / (\d+) contrôles de calcul concordent", html)
    return int(m.group(1)), int(m.group(2))


@pytest.mark.parametrize(
    "page", ["Roulements", "Engrenages", "Trains épicycloïdaux", "Freins et embrayages", "Dimensionnement moteur"]
)
def test_dossier_de_chaque_page(dm, page):
    """Exemples par défaut : 8 parties, chaque calcul présent, tous les contrôles à la main concordent."""
    calculs = _pages(dm)[page]
    html = mv.generate(page, calculs, dm)
    for ident, titre in vr._SECTIONS:
        assert f'<h2 id="{ident}">{titre}<a' in html
    for nom, *_ in calculs:
        assert html.count(f"<h3>{nom}</h3>") >= 5
    nOK, nTot = _bilan(html)
    assert nTot >= 3 and nOK == nTot
    assert "ÉCART" not in html and "NON satisfait" not in html and "Non inclus" not in html


@pytest.mark.parametrize(
    "bloque,entree", list(itertools.permutations(("planétaire", "couronne", "porte-satellites"), 2))
)
def test_willis_forme_fermee_toutes_configurations(dm, bloque, entree):
    s = {**mc.defaultPlanetaryInput(), "bloque": bloque, "entree": entree}
    nOK, nTot = _bilan(mv.generate("Épi", [("Train", "planetary", s, mc.computePlanetary(s))], dm))
    assert nOK == nTot == 3


def test_valeur_du_solveur_faussee_donne_un_ecart(dm):
    calculs = _pages(dm)["Roulements"]
    faux = copy.deepcopy(calculs[0][3])
    faux["result"]["L10"] *= 1.01
    html = mv.generate("Roulements", [calculs[0][:3] + (faux,), calculs[1]], dm)
    nOK, nTot = _bilan(html)
    assert nOK == nTot - 1 and "ÉCART" in html and "écart(s) à examiner" in html


def test_calcul_non_a_jour_non_inclus(dm):
    frein, emb = _pages(dm)["Freins et embrayages"]
    html = mv.generate("Freins et embrayages", [frein, emb[:3] + (None,)], dm)
    assert "Non inclus" in html
    assert _bilan(html)[1] == 6  # seuls les contrôles du frein


def test_hypothese_non_satisfaite_comptee(dm):
    s = {**mc.defaultClutchInput(), "CM": 10.0}
    html = mv.generate("Embrayage", [("Embrayage", "clutch", s, mc.computeClutch(s))], dm)
    assert "NON satisfait" in html and "1 hypothèse(s) NON satisfaite(s)" in html


def test_nom_de_fichier():
    assert mv.fileName("Trains épicycloïdaux", datetime(2026, 11, 2, 9, 30)) == (
        "Validation_Trains_epicycloidaux_20261102_093000.html"
    )


def test_bouton_du_dossier(bureau, tmp_path):
    """Inactif avant « Calculer » ; après, le dossier se génère et s'enregistre ; masqué si la saisie change."""
    bureau.ouvre("freins_embrayages")
    assert not bureau.bouton("Dossier de validation de cette page").isEnabled()
    bureau.clique("Calculer")
    assert bureau.bouton("Dossier de validation de cette page").isEnabled()
    assert bureau.a_texte("Embrayage")  # non inclus : pas calculé
    bureau.clique("Dossier de validation de cette page")
    fichier, html, _, _ = state.v["validation.freins"]
    assert fichier.startswith("Validation_Freins_et_embrayages_") and "Frein à disque" in html
    for fmt, ext in (("PDF", ".pdf"), ("Word", ".docx"), ("HTML", ".html")):
        bureau.radio(fmt)
        cible = tmp_path / f"dossier{ext}"
        bureau.clavier_enregistrer(cible)
        bureau.clique(next(b.text() for b in bureau._visibles(QAbstractButton) if b.text().startswith("Enregistrer le dossier")))
        assert cible.stat().st_size > 0
    state.v["frn.F"] = 1000.0  # saisie modifiée : le dossier ne correspond plus
    bureau.page.rafraichirPied()
    assert not any(b.text().startswith("Enregistrer le dossier") for b in bureau._visibles(QAbstractButton))


@pytest.mark.parametrize(
    "page, nom",
    [
        ("roulements", "roulements"),
        ("engrenages", "engrenages"),
        ("epicycloidaux", "epicycloidaux"),
        ("freins_embrayages", "freins"),
        ("dimensionnement_moteur", "moteur"),
    ],
)
def test_dossier_branche_dans_chaque_page(bureau, page, nom):
    """Dans la vraie page : tous les « Calculer », puis le dossier réunit chaque calcul, sans écart."""
    bureau.ouvre(page)
    onglets = getattr(bureau.page, "pages", [None])
    for i in range(len(onglets)):
        if hasattr(bureau.page, "onglets"):
            bureau.page.onglets.setCurrentIndex(i)
            bureau.attend()
        if bureau.boutons("Calculer"):
            bureau.clique("Calculer")
    bureau.clique("Dossier de validation de cette page")
    _, html, _, _ = state.v[f"validation.{nom}"]
    assert "Non inclus" not in html and "ÉCART" not in html


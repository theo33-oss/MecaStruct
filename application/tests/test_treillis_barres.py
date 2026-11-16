"""Treillis : contrainte et flambage d'Euler des barres (lot 1.4.0), refaits à la main."""

import math

import numpy as np
import pytest

from mecastruct.core import design_checks
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import compute, validation_report
from mecastruct.services.examples import loadExample

DM = DataManager()


def calcule(**modif):
    s = {**compute.defaultTrussInput(), **modif}
    return s, compute.computeTruss(s, DM)


def test_barres_refaites_a_la_main():
    """Exemple du site : tube de 200 000 mm⁴ ; barre 7 (E–C) de 2,5 m comprimée à 27,083 kN."""
    _, r = calcule()
    c = r["result"]["check"]
    assert c["ok"] and r["ok"] is True and "barres vérifiées" in r["status"]
    N = np.array(r["result"]["tsol"]["N"])
    assert c["sigma"] == pytest.approx(np.abs(N) / 500e-6)
    pcr = math.pi**2 * 210e9 * 200000e-12 / 2.5**2  # barre de 2,5 m
    assert c["Pcr"][6] == pytest.approx(pcr, rel=1e-9) and pcr == pytest.approx(66323.7, rel=1e-4)
    assert c["tauxFlambage"][6] == pytest.approx(27083.33 * 1.5 / pcr, rel=1e-6)
    assert c["iFlambage"] == 4 and c["iSigma"] == 6  # barre 5 (D–E, 3 m) : la plus proche du flambage
    assert np.isnan(c["Pcr"][0])  # barre tendue : pas de flambage


def test_barre_comprimee_elancee_flambe_avant_re():
    """Rond plein de 25 mm : σ reste à 54 MPa mais la barre de 2,5 m flambe sous 6,6 kN."""
    _, r = calcule(Imin=19894.0)
    assert r["ok"] is False and "NON vérifiées" in r["status"]
    c = r["result"]["check"]
    assert c["okSigma"].all() and not c["okFlambage"].all()
    assert r["tables"]["Vérification des barres"]["Résultat"].tolist().count("NON") == 3


def test_contrainte_trop_forte():
    _, r = calcule(S=50.0, Imin=0.0)
    assert r["ok"] is False and not r["result"]["check"]["okSigma"].all()


def test_sans_imin_pas_de_verdict_complet():
    _, r = calcule(Imin=0.0)
    assert r["ok"] is None and "flambage non vérifié" in r["status"]
    assert np.isnan(r["result"]["check"]["Pcr"]).all()


def test_ancien_fichier_sans_les_nouveaux_champs():
    """Une étude enregistrée avant 1.4.0 n'a ni Re, ni s, ni Imin : le calcul reste possible (flambage non vérifié)."""
    s = loadExample("Tr")
    for cle in ("Re", "s", "Imin"):
        s.pop(cle)
    r = compute.computeTruss(s, DM)
    assert r["ok"] is None and r["result"]["check"]["sigmaAdm"] == pytest.approx(235e6 / 1.5)


def test_efforts_inchanges():
    """Les efforts du solveur (références MATLAB) ne dépendent pas de la vérification."""
    _, a = calcule()
    _, b = calcule(Re=100.0, s=3.0, Imin=0.0)
    assert np.array(a["result"]["tsol"]["N"]) == pytest.approx(np.array(b["result"]["tsol"]["N"]), rel=1e-12)


def test_saisies_invalides():
    with pytest.raises(MecaStructError):
        design_checks.trussBars([1.0], [1.0], 1e-4, 210e9, 235e6, 0.0)
    with pytest.raises(MecaStructError):
        design_checks.trussBars([1.0], [1.0], 1e-4, 210e9, 235e6, 1.5, -1.0)


def test_dossier_de_validation_refait_euler():
    s, r = calcule()
    r = validation_report.recompute("Tr", s, DM, None)
    lignes = [x for x in validation_report._handRows("Tr", s, r, DM) if x.get("hand") is not None]
    euler = [x for x in lignes if "charge critique d'Euler" in x["label"]]
    assert len(euler) == 3  # trois barres comprimées
    for x in euler:
        assert validation_report._verdict(x)[1], x["label"]
    assert any(x["label"] == "σ admissible Re/s" and validation_report._verdict(x)[1] for x in lignes)
    html = validation_report.generate("Tr", s, r, DM)
    assert "flambage d'Euler" in html

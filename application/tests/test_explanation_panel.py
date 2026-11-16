"""Panneau « Explications du calcul » : lignes avec équations (validation_report) et affichage sur la page Poutres."""

import pytest

from mecastruct.bureau import state
from mecastruct.core.data_manager import DataManager
from mecastruct.services import validation_report as vr
from mecastruct.services.examples import loadExample

MESSAGE_AVANT_CALCUL = "Cliquez sur « Calculer » pour voir les équations appliquées à vos données."


@pytest.fixture(scope="module")
def dm():
    return DataManager()


@pytest.mark.parametrize("key", vr.KEYS)
def test_lignes_avec_equation_latex(dm, key):
    """Chaque contrôle à la main de l'exemple par défaut a une équation LaTeX non vide."""
    saisie = loadExample(key)
    res = vr.recompute(key, saisie, dm)
    rows = vr.explanationRows(key, saisie, res, dm)
    assert rows
    for r in rows:
        if r["hand"] is not None:
            assert isinstance(r["latex"], str) and r["latex"].strip(), (key, r["label"])


def test_message_avant_calcul(bureau):
    bureau.ouvre("poutres")
    assert bureau.case("Explications du calcul", True)
    assert bureau.a_texte(MESSAGE_AVANT_CALCUL)


def test_equations_affichees_apres_calcul(bureau):
    bureau.ouvre("poutres")
    bureau.clique("Calculer")
    assert bureau.nb_formules() > 0  # panneau sous son titre : graphiques empilés


def test_saisie_modifiee_apres_calcul(bureau):
    """Après un calcul, une saisie modifiée n'affiche pas d'équations calculées avec elle face à l'ancien résultat."""
    bureau.ouvre("poutres")
    bureau.clique("Calculer")
    bureau.saisit("Longueur L (m)", "7")
    assert state.result("Beam") is not None and not state.is_current("Beam")
    assert bureau.a_texte("Saisie modifiée depuis le dernier calcul")

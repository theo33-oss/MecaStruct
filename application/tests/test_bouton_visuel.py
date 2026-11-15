"""Bouton « Calculer » du visuel : il lance le même calcul que celui de la saisie, sans défiler jusqu'en bas."""

import pytest
from PySide6.QtWidgets import QFrame

from mecastruct.bureau import state


def _metriques(bureau):
    return [w for w in bureau._visibles(QFrame) if w.objectName() == "metrique"]


@pytest.mark.parametrize(
    ("page", "nom"),
    [
        ("frettage", "fre"),
        ("ajustements", "aju"),
        ("paliers_lisses", "pal"),
        ("dimensionnement_moteur", "mot"),
        ("epicycloidaux", "epi"),
    ],
)
def test_bouton_du_visuel_calcule_comme_la_saisie(bureau, page, nom):
    bureau.ouvre(page)
    assert f"{nom}.res" not in state.v
    assert len(bureau.boutons("Calculer")) == 2  # celui de la saisie et celui du visuel
    bureau.clique("Calculer", n=1)  # le second est celui du visuel
    assert f"{nom}.res" in state.v


@pytest.mark.parametrize(
    ("page", "tab"),
    [("flambage", "Fla"), ("sections", "Sec"), ("tenseurs", "Ten"), ("treillis", "Tr")],
)
def test_bouton_du_visuel_sur_les_autres_pages(bureau, page, tab):
    bureau.ouvre(page)
    bureau.clique("Calculer", n=1)
    assert state.result(tab) is not None


def test_machine_saisie_modifiee_sans_verdict_colore(bureau):
    bureau.ouvre("frettage")
    bureau.clique("Calculer", n=1)
    assert not bureau.a_texte("Saisie modifiée depuis le dernier calcul")
    bureau.saisit("Couple C (N·m)", str(state.v["fre.C"] + 1))
    assert bureau.a_texte("Saisie modifiée depuis le dernier calcul")
    assert bureau.a_texte("(saisie modifiée : cliquez sur Calculer)")


def test_synthese_sous_calculer_suit_la_saisie(bureau):
    bureau.ouvre("flambage")
    bureau.clique("Calculer", n=1)
    assert _metriques(bureau) and not bureau.a_texte("(saisie modifiée : cliquez sur Calculer)")
    bureau.saisit("Longueur L (m)", str(state.saisie("Fla")["L"] + 1))
    assert not _metriques(bureau) and bureau.a_texte("(saisie modifiée : cliquez sur Calculer)")


def test_bouton_du_visuel_en_mode_ossature_3d(bureau):
    """Le mode Ossature 3D vit dans la page « Poutres » : son bouton du visuel lance le même calcul."""
    bureau.ouvre("poutres")
    bureau.radio("Ossature 3D")
    bureau.clique("Calculer", n=1)
    assert "p3d.res" in state.v

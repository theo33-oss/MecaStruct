"""Tests de fumée de l'interface de bureau : la fenêtre et chaque page de son menu s'ouvrent sans exception."""

import pytest

import main

PAGES = [ident for ident, libelle, _ in main.MENU if libelle is not None]


def test_la_fenetre_s_ouvre_sur_l_accueil(bureau):
    assert bureau.fenetre.isVisible()
    from mecastruct import __version__

    assert bureau.fenetre.windowTitle() == f"MecaStruct RdM Pro {__version__}"
    assert bureau.fenetre.menu.currentRow() == bureau.fenetre.pages["accueil"][0]
    assert bureau.a_texte("Calculs de résistance des matériaux et d'éléments de machines")


@pytest.mark.parametrize("page", PAGES)
def test_chaque_page_s_ouvre(bureau, page):
    bureau.ouvre(page)
    assert bureau.fenetre.pile.currentWidget() is bureau.page
    assert bureau.page.bati


def test_chaque_page_du_menu_a_sa_classe():
    assert len(PAGES) == 21
    assert len(set(PAGES)) == len(PAGES)

"""Listes déroulantes à libellés français : on affiche l'étiquette, on stocke la valeur interne."""

import pytest

from mecastruct.bureau import state
from mecastruct.bureau.widgets import TableauEditable

pytestmark = pytest.mark.qt


def _tableau(bureau, ident, tab, champ):
    bureau.ouvre(ident)
    return next(t for t in bureau.page.findChildren(TableauEditable) if t.champ == champ), state.saisie(tab)


def test_ancien_projet_affiche_le_libelle_francais(bureau):
    t, s = _tableau(bureau, "poutres", "Beam", "sup")
    s["sup"] = [{"pos": 0.0, "type": "pivot_glissant", "name": "A"}]
    t.charger()
    j = [c.cle for c in t.colonnes].index("type")
    assert t.item(0, j).text() == "Pivot glissant"


def test_choisir_un_appui_stocke_la_valeur_interne(bureau):
    t, s = _tableau(bureau, "poutres", "Beam", "sup")
    s["sup"] = [{"pos": 0.0, "type": "appui_simple", "name": "A"}]
    t.charger()
    j = [c.cle for c in t.colonnes].index("type")
    t.item(0, j).setText("Encastrement")
    assert s["sup"][0]["type"] == "encastrement"


def test_ossature3d_libelles_et_valeurs(bureau):
    bureau.ouvre("poutres")
    bureau.radio("Ossature 3D")
    bureau.choisit("Exemple", "Potence en L")
    t = next(t for t in bureau.page.findChildren(TableauEditable) if t.champ == "noeuds")
    s = state.extra["P3D"]
    s["noeuds"][0]["appui"] = "appui_z"
    t.charger()
    j = [c.cle for c in t.colonnes].index("appui")
    assert t.item(0, j).text() == "Appui vertical (z)"
    t.item(0, j).setText("Personnalisé (DDL)")
    assert s["noeuds"][0]["appui"] == "perso"

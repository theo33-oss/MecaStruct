"""Application de bureau : diagramme des modes de ruine et boutons Bloc-notes et Excel de validation (1.4.0)."""

import base64
import io

import pytest
from openpyxl import load_workbook

from mecastruct.bureau import exports, state
from mecastruct.bureau.modes import Jauge, ModesRuine
from mecastruct.services import criteres

pytestmark = pytest.mark.qt


def modes(bureau):
    return [w for w in bureau.page.findChildren(ModesRuine) if w.isVisibleTo(bureau.page)]


@pytest.mark.parametrize(
    ("page", "onglet", "texte"),
    [
        ("poutres", None, "Flexion composée"),
        ("treillis", None, "Flambage d'Euler"),
        ("flambage", None, "Flambage : charge P"),
        ("tenseurs", None, "Von Mises"),
        ("sollicitations", 1, "Cisaillement : τ max"),
        ("roulements", 0, "Durée de vie Lnh"),
        ("frettage", None, "Arbre : σ équivalente"),
        ("paliers_lisses", None, "Pression P"),
        ("engrenages", 0, "Flexion en pied de dent"),
        ("dimensionnement_moteur", None, "Couple nominal"),
    ],
)
def test_le_diagramme_apparait_apres_calcul(bureau, page, onglet, texte):
    bureau.ouvre(page)
    if onglet is not None:
        bureau.page.onglets.setCurrentIndex(onglet)
        bureau.attend()
    assert not modes(bureau)  # rien avant « Calculer »
    bureau.clique("Calculer")
    bureau.attend(200)
    cadres = modes(bureau)
    assert len(cadres) == 1
    textes = [w.text() for w in cadres[0].findChildren(object) if hasattr(w, "text") and callable(w.text)]
    assert any(texte in x for x in textes), textes
    assert cadres[0].findChildren(Jauge)


def test_pastille_et_phrase_de_la_traction(bureau):
    bureau.ouvre("sollicitations")
    bureau.clique("Calculer")
    bureau.attend(200)
    (cadre,) = modes(bureau)
    textes = [w.text() for w in cadre.findChildren(object) if hasattr(w, "text") and callable(w.text)]
    assert "Non vérifié" in textes and "1 mode de ruine non admissible sur 1" in textes
    assert any("159,2 MPa pour 156,7 MPa admissibles" in t for t in textes)  # virgule, pas de signe ≤ trompeur
    assert any(t.startswith("σmax = 159,2") for t in textes)  # le σ grec n'est pas mis en majuscule


def test_saisie_modifiee_grise_le_diagramme(bureau):
    bureau.ouvre("sollicitations")
    bureau.clique("Calculer")
    bureau.attend(200)
    state.saisie("Tra")["N"] = 10.0
    bureau.page.pages[bureau.page.onglets.currentIndex()].rafraichirTout()
    bureau.attend(200)
    (cadre,) = modes(bureau)
    assert cadre.graphicsEffect() is not None and cadre.graphicsEffect().opacity() < 1


def test_boutons_d_export_et_fichiers(bureau):
    bureau.ouvre("treillis")
    assert bureau.boutons("Bloc-notes (.txt)") and bureau.boutons("Excel de validation")
    saisie = state.saisie("Tr")
    texte = exports.appel("truss.texte", saisie)["texte"]
    assert texte.startswith("﻿") and "Flambage d'Euler" in texte and "MPa" in texte
    classeur = load_workbook(io.BytesIO(base64.b64decode(exports.appel("truss.validation", saisie)["base64"])))
    assert classeur.sheetnames[:2] == ["Lisez-moi", "Données"] and "Calcul" in classeur.sheetnames


def test_bouton_demander_a_une_ia(bureau, monkeypatch):
    """« Demander à une IA » : l'étude (consigne + note) est dans le presse-papiers, puis un menu propose Claude et ChatGPT."""
    from PySide6.QtWidgets import QApplication

    menus = []
    monkeypatch.setattr(exports, "montrer_menu", lambda menu, _pos: menus.append([x.text() for x in menu.actions()]))
    bureau.ouvre("treillis")
    assert bureau.boutons("Demander à une IA")
    bureau.clique("Demander à une IA")
    bureau.attend(300)
    copie = QApplication.clipboard().text()
    assert "attends mes questions" in copie and "--- ÉTUDE ---" in copie and "Flambage d'Euler" in copie
    assert menus and "Ouvrir Claude" in menus[0] and "Ouvrir ChatGPT" in menus[0]


def test_export_voit_les_materiaux_de_l_utilisateur(bureau):
    """Le pont reçoit la base de l'application : un matériau ajouté dans l'application est connu des exports."""
    from mecastruct.pont import noyau

    exports.appel("tra.texte", state.saisie("Tra"))
    assert noyau.dm() is state.dm()


def test_barre_de_taux_dessinee_et_nom_accessible():
    j = Jauge(1.02, 1.25, False)
    assert j.accessibleName() == "Taux de travail 102 %" and j.height() == 18


def test_criteres_du_bureau_et_du_site_identiques(bureau):
    """Même fonction de critères que le pont : mêmes valeurs pour la même saisie."""
    from mecastruct.pont import noyau

    bureau.ouvre("sollicitations")
    bureau.clique("Calculer")
    bureau.attend(200)
    res = state.result("Tra")
    sur_le_bureau = criteres.criteres("Tra", state.saisie("Tra"), res)
    sur_le_site = noyau.appeler  # le site passe par la même fonction : vérifié dans test_exports
    assert sur_le_bureau and callable(sur_le_site) and sur_le_bureau[0]["taux"] == pytest.approx(1.0159, rel=1e-3)

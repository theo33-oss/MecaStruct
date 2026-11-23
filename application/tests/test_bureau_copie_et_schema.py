"""Bureau comme le site : « Copier l'image », retour visible des boutons, schéma replié après « Calculer »."""

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton

from mecastruct.bureau import widgets
from mecastruct.bureau.widgets import TeteRepli

pytestmark = pytest.mark.qt


def boutons_copie(bureau):
    return [b for b in bureau.page.findChildren(QPushButton) if b.text() == "Copier l'image" and b.isVisibleTo(bureau.page)]


def tetes_schema(bureau):
    return [t for t in bureau.page.findChildren(TeteRepli) if t.property("schema")]


def test_copier_l_image_met_un_png_dans_le_presse_papiers(bureau):
    bureau.ouvre("engrenages")
    bureau.clique("Calculer")
    bureau.attend(300)
    assert boutons_copie(bureau)  # schéma, décision, graphique ou tableaux
    QApplication.clipboard().clear()
    bouton = boutons_copie(bureau)[0]
    bouton.click()
    bureau.attend(100)
    assert not QApplication.clipboard().image().isNull()
    assert bouton.text().startswith("✓")  # retour visible
    assert "copiée" in bureau.fenetre.statusBar().currentMessage()


def test_retour_visible_revient_a_l_etat_initial(bureau, monkeypatch):
    monkeypatch.setattr(widgets, "DUREE_RETOUR_MS", 20)
    b = QPushButton("Excel")
    b.setStyleSheet("color:red;")
    widgets.retour_bouton(b, True, "Enregistré", bureau.page, "Fait.")
    assert b.text() == "✓ Enregistré" and "background" in b.styleSheet()
    assert bureau.fenetre.statusBar().currentMessage() == "Fait."
    widgets.retour_bouton(b, False, "Échec")  # un second retour ne perd pas le texte d'origine
    assert b.text().startswith("✗")
    bureau.attend(150)
    assert b.text() == "Excel" and b.styleSheet() == "color:red;"


def test_schema_se_replie_apres_calculer(bureau):
    bureau.ouvre("engrenages")
    (tete,) = tetes_schema(bureau)
    assert tete.actif and tete.libelle.text() == "Masquer le schéma"
    bureau.clique("Calculer")
    bureau.attend(300)
    (tete,) = tetes_schema(bureau)
    assert not tete.actif and tete.libelle.text() == "Afficher le schéma"
    # un clic sur l'en-tête le rouvre : le schéma et la case « Mémoriser » apparaissent
    tete.mousePressEvent(None)
    assert tete.actif and tete.libelle.text() == "Masquer le schéma"
    assert any(c.text().startswith("Mémoriser ce choix") for c in bureau.page.findChildren(QCheckBox))


def test_choix_memorise_garde_le_schema_visible(bureau):
    bureau.ouvre("engrenages")
    case = next(c for c in bureau.page.findChildren(QCheckBox) if c.text().startswith("Mémoriser ce choix"))
    case.setChecked(True)  # schéma visible mémorisé
    bureau.clique("Calculer")
    bureau.attend(300)
    (tete,) = tetes_schema(bureau)
    assert tete.actif  # « Calculer » ne le replie pas

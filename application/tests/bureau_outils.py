"""Outils des tests de l'interface de bureau : fenêtre partagée, recherche de boutons et de champs par leur libellé.

Les gestes sont ceux d'un utilisateur : clic sur un bouton, texte tapé dans un champ puis validé, choix dans une liste.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

import main  # noqa: E402  (importe QtWebEngine avant QApplication)
from PySide6.QtCore import QCoreApplication, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QRadioButton,
    QTableWidget,
    QTabWidget,
    QWidget,
)

from mecastruct.bureau import state, tache, widgets  # noqa: E402


class Bureau:
    """Fenêtre de l'application et gestes sur la page ouverte."""

    def __init__(self, qapp, qtbot) -> None:
        widgets.appliquerTheme(qapp)
        state.v.clear()
        state.extra.clear()
        state.abonnes.clear()
        state.init()
        self.qtbot = qtbot
        self.fenetre = main.Fenetre()
        self.fenetre.show()
        self.ident = "accueil"

    def ouvre(self, ident: str):
        self.ident = ident
        self.fenetre.aller(ident)
        self.attend(30)
        return self.page

    @property
    def page(self):
        return self.fenetre.page(self.ident)

    def attend(self, ms: int = 30) -> None:
        """Laisse passer les rappels différés et les calculs en arrière-plan."""
        self.qtbot.waitUntil(lambda: not tache.occupe(), timeout=120000)
        self.qtbot.wait(ms)
        QCoreApplication.processEvents()
        self.qtbot.waitUntil(lambda: not tache.occupe(), timeout=120000)

    def _visibles(self, type_: type) -> list:
        QCoreApplication.processEvents()  # les widgets créés par un redessin ne sont affichés qu'après leur mise en page
        QCoreApplication.sendPostedEvents(None, 0)
        return [w for w in self.page.findChildren(type_) if w.isVisibleTo(self.page)]

    def textes(self) -> list[str]:
        """Textes de tous les libellés visibles de la page ouverte (tous onglets bâtis)."""
        return [w.text() for w in self._visibles(QLabel)]

    def a_texte(self, fragment: str) -> bool:
        return any(fragment in t for t in self.textes())

    def boutons(self, texte: str) -> list[QAbstractButton]:
        return [b for b in self._visibles(QAbstractButton) if b.text() == texte]

    def bouton(self, texte: str, n: int = 0) -> QAbstractButton:
        trouves = self.boutons(texte)
        assert trouves, f"bouton « {texte} » introuvable (boutons : {[b.text() for b in self._visibles(QAbstractButton)][:40]})"
        return trouves[n]

    def clique(self, texte: str, n: int = 0) -> None:
        b = self.bouton(texte, n)
        assert b.isEnabled(), f"bouton « {texte} » inactif"
        b.click()
        self.attend()

    def nb_formules(self) -> int:
        """Nombre de formules (textes sélectionnables) visibles dans la page."""
        return sum(1 for lab in self._visibles(QLabel) if lab.objectName() == "formule")

    def ouvre_volet(self, titre: str) -> None:
        """Déplie le bloc repliable `titre` en cliquant sur son en-tête."""
        for tete in self._visibles(widgets.TeteRepli):
            if any(lab.text() == titre for lab in tete.findChildren(QLabel)):
                if not tete.actif:
                    tete.mousePressEvent(None)
                    self.attend()
                return
        raise AssertionError(f"bloc « {titre} » introuvable")

    def ordre_vertical(self, section) -> list[str]:
        """Textes des libellés d'une section, de haut en bas (ordre d'affichage)."""
        QCoreApplication.processEvents()
        items = [(w.mapTo(section, w.rect().topLeft()).y(), w.text()) for w in section.findChildren(QLabel)
                 if w.isVisibleTo(section) and w.text()]  # fmt: skip
        return [t for _, t in sorted(items)]

    def onglet(self, nom: str) -> None:
        """Ouvre l'onglet `nom` du premier jeu d'onglets visible qui le contient."""
        for tabs in self._visibles(QTabWidget):
            for i in range(tabs.count()):
                if tabs.tabText(i) == nom:
                    tabs.setCurrentIndex(i)
                    self.attend()
                    return
        raise AssertionError(f"onglet « {nom} » introuvable")

    def onglets(self) -> list[str]:
        return [t.tabText(i) for t in self._visibles(QTabWidget) for i in range(t.count())]

    def _apres_libelle(self, libelle: str, type_: type) -> QWidget:
        for lab in self._visibles(QLabel):
            if lab.text() == libelle:
                mise = lab.parentWidget().layout()
                i = mise.indexOf(lab)
                w = mise.itemAt(i + 1).widget()
                assert isinstance(w, type_), f"{libelle} : {type(w).__name__}"
                return w
        raise AssertionError(f"champ « {libelle} » introuvable")

    def champ(self, libelle: str) -> QLineEdit:
        return self._apres_libelle(libelle, QLineEdit)

    def saisit(self, libelle: str, texte: str) -> None:
        c = self.champ(libelle)
        c.setText(texte)
        c.editingFinished.emit()
        self.attend()

    def valeur(self, libelle: str) -> str:
        return self.champ(libelle).text()

    def liste(self, libelle: str) -> QComboBox:
        return self._apres_libelle(libelle, QComboBox)

    def choisit(self, libelle: str, texte: str) -> None:
        boite = self.liste(libelle)
        i = boite.findText(texte)
        assert i >= 0, f"{texte} absent de {[boite.itemText(k) for k in range(boite.count())]}"
        boite.setCurrentIndex(i)
        boite.activated.emit(i)
        self.attend()

    def case(self, libelle: str, etat: bool | None = None) -> bool:
        c = next(c for c in self._visibles(QCheckBox) if c.text() == libelle)
        if etat is not None and c.isChecked() != etat:
            c.setChecked(etat)  # le redessin qui suit détruit la case : l'état est lu avant
            self.attend()
            return etat
        return c.isChecked()

    def radio(self, texte: str) -> None:
        r = next(r for r in self._visibles(QRadioButton) if r.text() == texte)
        r.click()
        self.attend()

    def multi(self, libelle: str) -> QListWidget:
        return self._apres_libelle(libelle, QListWidget)

    def tableaux(self) -> list[QTableWidget]:
        return [t for t in self._visibles(QTableWidget) if isinstance(t, widgets.TableauEditable)]

    def cellule(self, tableau: QTableWidget, ligne: int, colonne: str, texte: str) -> None:
        j = next(k for k, c in enumerate(tableau.colonnes) if c.titre == colonne)
        tableau.item(ligne, j).setText(texte)
        self.attend()

    def clavier_enregistrer(self, chemin: str) -> None:
        """Les boîtes « Enregistrer » répondent `chemin` (aucune fenêtre n'est ouverte)."""
        from PySide6.QtWidgets import QFileDialog

        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(chemin), ""))

    def clavier_ouvrir(self, chemin: str) -> None:
        from PySide6.QtWidgets import QFileDialog

        QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(chemin), ""))
        QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([str(chemin)], ""))


def ouvre_fenetre(qapp, qtbot) -> Bureau:
    return Bureau(qapp, qtbot)


_ = Qt  # (import gardé pour les tests qui ont besoin des constantes Qt)

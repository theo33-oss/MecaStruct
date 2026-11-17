"""Briques d'interface : page, section reconstruite à la demande, zone d'affichage et champs liés à la saisie.

Une Section redessine son contenu avec une fonction `rendu(zone)`. Les champs gardent leur valeur dans state.v sous
leur clé : une section reconstruite les retrouve, comme une page rouverte.
"""

import math
import re
import tempfile
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from shiboken6 import isValid
from PySide6.QtCore import QEvent, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mecastruct.bureau import state, theme
from mecastruct.bureau.latex_texte import versTexte
from mecastruct.services.export_texte import fr

_DOSSIER_FIGURES = Path(tempfile.mkdtemp(prefix="mecastruct_"))
HAUTEUR_TABLEAU_MAX = 420
NIVEAUX_MESSAGE = ("info", "succes", "avertissement", "erreur")


def differer(fonction: Callable[[], None]) -> None:
    """Exécute fonction après le signal en cours : elle peut alors détruire le champ qui l'a appelée."""
    QTimer.singleShot(0, fonction)


def vider(disposition: Any) -> None:
    """Retire et détruit tout le contenu d'une disposition."""
    while disposition.count():
        element = disposition.takeAt(0)
        if (w := element.widget()) is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif element.layout() is not None:
            vider(element.layout())


def contrasteEleve() -> bool:
    """Vrai si « Contraste élevé » est choisi pour les graphiques."""
    return bool(state.v.get("contraste"))


def _renforce(fig: Any) -> None:
    """Contraste élevé : traits épaissis, aires colorées plus opaques, quadrillage et textes plus marqués."""
    for t in fig.data:
        ligne = getattr(t, "line", None)
        if ligne is not None and getattr(ligne, "width", None):  # largeur 0 (bord d'une aire) : inchangée
            ligne.width = max(2.5, ligne.width * 1.8)
        fond = getattr(t, "fillcolor", None)
        if isinstance(fond, str) and fond.startswith("rgba("):
            *rvb, alpha = fond[5:-1].split(",")
            t.fillcolor = f"rgba({','.join(rvb)},{min(1.0, 2 * float(alpha)):g})"
    fig.update_layout(font_size=15)
    for a in fig.layout.annotations:
        if a.font.size is not None and a.font.size < 12:
            a.font.size = 12
    encre = theme.actuel()["encre"]
    fig.update_xaxes(gridcolor="#8E86AA", linecolor=encre, zerolinecolor=encre, tickfont_size=14)
    fig.update_yaxes(gridcolor="#8E86AA", linecolor=encre, zerolinecolor=encre, tickfont_size=14)


class VueFigure(QWebEngineView):
    """Figure Plotly interactive, sans Internet : plotly.min.js est écrit une fois dans le dossier temporaire."""

    def __init__(self, fig: Any) -> None:
        super().__init__()
        if theme.sombre():
            fig = theme.figure_sombre(fig)
        fond = theme.actuel()["carte"]
        fig.update_layout(paper_bgcolor=fond, plot_bgcolor=fond)
        if contrasteEleve():
            _renforce(fig)
        hauteur = int(fig.layout.height or 450)
        chemin = _DOSSIER_FIGURES / f"{uuid.uuid4().hex}.html"
        fig.write_html(
            chemin,
            include_plotlyjs="directory",
            full_html=True,
            default_width="100%",
            default_height=f"{hauteur}px",
            config={"displaylogo": False, "scrollZoom": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
        )
        html = chemin.read_text(encoding="utf-8").replace("<body>", '<body style="margin:0;overflow:hidden">', 1)
        chemin.write_text(html, encoding="utf-8")
        self.setFixedHeight(hauteur + 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.load(QUrl.fromLocalFile(str(chemin)))


_NOMBRE_POINT = re.compile(r"^[-−+]?\d+\.\d+(e[-+]?\d+)?$")


def _ecrit(v: Any, fmt: str | None) -> str:
    """Case de tableau en texte : nombres à la française, vide pour une valeur absente."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if fmt and isinstance(v, int | float):
        return (fmt % v).replace(".", ",")
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    if isinstance(v, str) and _NOMBRE_POINT.match(v.strip()):  # « 5.6993 » écrit en texte par le calcul
        return v.replace(".", ",")
    return str(v)


def ajusterHauteur(table: QTableWidget) -> None:
    """Hauteur du tableau selon ses lignes (bornée : un long tableau défile sur place)."""
    h = table.horizontalHeader().height() + 2 * table.frameWidth() + 18
    h += sum(table.rowHeight(i) for i in range(table.rowCount()))
    table.setFixedHeight(min(h, HAUTEUR_TABLEAU_MAX))
    # le tableau défile sur place : sa largeur ne doit pas élargir le panneau
    table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    table.setMinimumWidth(120)


class TableauDonnees(QTableWidget):
    """DataFrame en lecture seule. formats : {colonne: « %.4f »} ; couleurs : {colonne: valeur → (fond, texte)}."""

    def __init__(self, df: pd.DataFrame, formats: dict | None = None, couleurs: dict | None = None,
                 index: bool = False) -> None:  # fmt: skip
        super().__init__(len(df), len(df.columns))
        formats, couleurs = formats or {}, couleurs or {}
        self.setHorizontalHeaderLabels([str(c) for c in df.columns])
        if index:
            self.setVerticalHeaderLabels([str(i) for i in df.index])
        else:
            self.verticalHeader().hide()
        for j, col in enumerate(df.columns):
            for i, v in enumerate(df[col].tolist()):
                item = QTableWidgetItem(_ecrit(v, formats.get(col)))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if isinstance(v, int | float) and not isinstance(v, bool):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col in couleurs and (c := couleurs[col](v)):
                    item.setBackground(QColor(c[0]))
                    item.setForeground(QColor(c[1]))
                self.setItem(i, j, item)
        self.setWordWrap(False)
        self.resizeColumnsToContents()
        for j in range(self.columnCount()):
            self.setColumnWidth(j, min(self.columnWidth(j), 340))
        self.horizontalHeader().setStretchLastSection(True)
        ajusterHauteur(self)


class Colonne:
    """Colonne d'un TableauEditable : genre « texte », « nombre », « liste » ou « case » ; defaut = valeur d'une ligne neuve."""

    def __init__(self, cle: str, titre: str, genre: str = "texte", options: Sequence[str] = (), defaut: Any = None,
                 aide: str = "", entier: bool = False, mini: float | None = None, libre: bool = False) -> None:  # fmt: skip
        self.cle, self.titre, self.genre, self.options = cle, titre, genre, list(options)
        self.aide, self.entier, self.mini, self.libre = aide, entier, mini, libre
        if defaut is None:
            defaut = {"nombre": 0.0, "case": False, "liste": self.options[0] if self.options else "", "texte": ""}[genre]
        self.defaut = defaut


def nombre_col(cle: str, titre: str, defaut: float = 0.0, **kw: Any) -> Colonne:
    return Colonne(cle, titre, "nombre", defaut=defaut, **kw)


def noeud_col(cle: str, titre: str, defaut: int = 1) -> Colonne:
    return Colonne(cle, titre, "nombre", defaut=defaut, entier=True, mini=1)


def texte_col(cle: str, titre: str, defaut: str = "") -> Colonne:
    return Colonne(cle, titre, "texte", defaut=defaut)


def liste_col(cle: str, titre: str, options: Sequence[str], defaut: str | None = None) -> Colonne:
    return Colonne(cle, titre, "liste", options=options, defaut=defaut)


def case_col(cle: str, titre: str, defaut: bool = True) -> Colonne:
    return Colonne(cle, titre, "case", defaut=defaut)


class _DelegueListe(QStyledItemDelegate):
    """Éditeur des colonnes à liste : QComboBox."""

    def __init__(self, table: "TableauEditable") -> None:
        super().__init__(table)
        self.table = table

    def createEditor(self, parent: QWidget, option: Any, index: Any) -> QWidget:  # noqa: N802 : nom imposé par Qt
        col = self.table.colonnes[index.column()]
        if col.genre != "liste":
            return super().createEditor(parent, option, index)
        boite = QComboBox(parent)
        boite.setEditable(col.libre)
        boite.addItems(col.options)
        boite.activated.connect(lambda: self.commitData.emit(boite))
        return boite

    def setEditorData(self, editeur: QWidget, index: Any) -> None:  # noqa: N802 : nom imposé par Qt
        if isinstance(editeur, QComboBox):
            editeur.setCurrentText(index.data() or "")
        else:
            super().setEditorData(editeur, index)

    def setModelData(self, editeur: QWidget, modele: Any, index: Any) -> None:  # noqa: N802 : nom imposé par Qt
        if isinstance(editeur, QComboBox):
            modele.setData(index, editeur.currentText())
        else:
            super().setModelData(editeur, modele, index)


def lireNombre(texte: str) -> float | None:
    """Nombre tapé avec un point ou une virgule ; None si le texte est vide ; ValueError s'il est illisible."""
    t = texte.strip().replace(",", ".").replace(" ", "").replace("−", "-")
    return None if not t else float(t)


def formatNombre(v: float | None, entier: bool = False) -> str:
    """Nombre écrit à la française (virgule), 6 chiffres significatifs ; vide pour None."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{round(v):d}" if entier else f"{v:.6g}".replace(".", ",")


class TableauEditable(QTableWidget):
    """Tableau de saisie lié à la liste de dicts saisie[tab][champ] ; surChange() suit chaque case validée."""

    def __init__(self, tab: str, champ: str, colonnes: list[Colonne], surChange: Callable[[], None] | None = None,
                 maxLignes: int = 200, polaire: dict | None = None) -> None:  # fmt: skip
        super().__init__(0, len(colonnes))
        self.tab, self.champ, self.colonnes, self.surChange, self.maxLignes = tab, champ, colonnes, surChange, maxLignes
        # force inclinée : {"norme", "angle", "plan", "composantes"} (noms de colonnes) ; Fx, Fy, Fz suivent F, α et le plan
        self.polaire = polaire
        self.setHorizontalHeaderLabels([c.titre for c in colonnes])
        for j, c in enumerate(colonnes):
            self.horizontalHeaderItem(j).setToolTip(c.aide)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setItemDelegate(_DelegueListe(self))
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.itemChanged.connect(self._change)
        self.charger()

    @property
    def lignes(self) -> list[dict]:
        return state.saisie(self.tab)[self.champ]

    def _valeur(self, ligne: dict, c: Colonne) -> Any:
        v = ligne.get(c.cle)
        return c.defaut if v is None or (isinstance(v, float) and math.isnan(v)) else v

    def charger(self) -> None:
        """Affiche les lignes de la saisie sans déclencher surChange."""
        self.blockSignals(True)
        lignes = self.lignes
        self.setRowCount(len(lignes))
        for i, ligne in enumerate(lignes):
            for j, c in enumerate(self.colonnes):
                v = self._valeur(ligne, c)
                item = QTableWidgetItem()
                if c.genre == "case":
                    item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable
                    )
                    item.setCheckState(Qt.CheckState.Checked if v else Qt.CheckState.Unchecked)
                elif c.genre == "nombre":
                    item.setText(formatNombre(float(v), c.entier))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setText(str(v))
                self.setItem(i, j, item)
        self.blockSignals(False)
        self.resizeColumnsToContents()
        ajusterHauteur(self)

    def ajouter(self) -> None:
        if len(self.lignes) >= self.maxLignes:
            QMessageBox.information(self, "Tableau plein", f"{self.maxLignes} lignes au plus par tableau.")
            return
        self.lignes.append({c.cle: c.defaut for c in self.colonnes})
        self.charger()
        self._suite()

    def supprimer(self) -> None:
        rangs = sorted({i.row() for i in self.selectedIndexes()}, reverse=True)
        if not rangs and self.currentRow() >= 0:
            rangs = [self.currentRow()]
        for i in rangs:
            del self.lignes[i]
        if rangs:
            self.charger()
            self._suite()

    def _suite(self) -> None:
        if self.surChange:
            differer(self.surChange)

    def _change(self, item: QTableWidgetItem) -> None:
        i, c = item.row(), self.colonnes[item.column()]
        ligne = self.lignes[i]
        if c.genre == "case":
            valeur: Any = item.checkState() == Qt.CheckState.Checked
        elif c.genre == "nombre":
            try:
                valeur = lireNombre(item.text())
                if valeur is None or not math.isfinite(valeur) or (c.mini is not None and valeur < c.mini):
                    raise ValueError
                valeur = int(round(valeur)) if c.entier else valeur
            except ValueError:  # saisie illisible : la case reprend sa valeur
                self.blockSignals(True)
                item.setText(formatNombre(float(self._valeur(ligne, c)), c.entier))
                self.blockSignals(False)
                return
        else:
            valeur = item.text().strip()
        if ligne.get(c.cle) != valeur:
            ligne[c.cle] = valeur
            if self.polaire:
                self._suit_polaire(ligne, c.cle)
            self._suite()

    def _suit_polaire(self, ligne: dict, cle: str) -> None:
        """Même règle que le site (services/forces.py) : F, α ou plan → composantes ; une composante saisie → F = 0."""
        from mecastruct.services import forces

        p = self.polaire
        if cle in p["composantes"]:
            ligne[p["norme"]] = 0.0
            ligne[p["angle"]] = 0.0
        elif cle in (p["norme"], p["angle"], p["plan"]) and float(ligne.get(p["norme"]) or 0.0) != 0.0:
            c = forces.composantes(float(ligne[p["norme"]]), float(ligne.get(p["angle"]) or 0.0),
                                   str(ligne.get(p["plan"]) or "xy"))
            for nom in p["composantes"]:
                ligne[nom] = c[nom]
        else:
            return
        self.charger()


class ChampNombre(QLineEdit):
    """Nombre tapé (point ou virgule), borné par mini et maxi ; l'ancienne valeur revient si la saisie est illisible."""

    def __init__(self, valeur: float | None, entier: bool, mini: float | None, maxi: float | None,
                 surValide: Callable[[Any], None]) -> None:  # fmt: skip
        super().__init__()
        self.entier, self.mini, self.maxi, self.surValide = entier, mini, maxi, surValide
        self.valeur = valeur
        self._ecrire()
        self.editingFinished.connect(self._valider)

    def _ecrire(self) -> None:
        self.setText(formatNombre(self.valeur, self.entier))
        self._affiche = self.text()

    def _valider(self) -> None:
        if self.text() == self._affiche:  # rien de tapé : la valeur exacte (plus de 6 chiffres) est conservée
            return
        try:
            v = lireNombre(self.text())
            if v is None or not math.isfinite(v):
                raise ValueError
        except ValueError:
            self._ecrire()
            return
        v = v if self.mini is None else max(v, self.mini)
        v = v if self.maxi is None else min(v, self.maxi)
        v = int(round(v)) if self.entier else v
        change = v != self.valeur
        self.valeur = v
        self._ecrire()
        if change:
            self.surValide(v)


CONSEILS = {
    "mechanism": "la structure peut bouger. Ajoutez un appui ou un encastrement, ou changez le type d'un appui "
    "(voir la légende sous le tableau des appuis).",
    "invalidSupport": "vérifiez le tableau des appuis : type connu et position comprise entre 0 et L.",
    "invalidModel": "une donnée est incohérente (position hors de la poutre, case vide, valeur nulle). "
    "Relisez les tableaux et la longueur L.",
    "invalidExpression": "dans les cases de valeurs, utilisez seulement des nombres, x et + - * / ^ ( ).",
    "invalidDimensions": "vérifiez les dimensions de la section (toutes positives, épaisseurs plus petites que la "
    "largeur).",
}

def _sans_balises(texte: Any) -> str:
    """Texte brut d'un titre Plotly : balises HTML (<br>, <sup>…) retirées, espaces réduits."""
    return " ".join(re.sub(r"<[^>]+>", " ", str(texte or "")).split())


def _extrema(courbe: Any) -> str:
    """« nom : maximum y en x = …, minimum y en x = … » d'une courbe, ou « » si ses valeurs ne sont pas numériques."""
    try:
        pts = [
            (float(x), float(y)) for x, y in zip(courbe.x, courbe.y, strict=False) if x is not None and y is not None
        ]
    except (TypeError, ValueError):
        return ""
    pts = [p for p in pts if math.isfinite(p[0]) and math.isfinite(p[1])]
    if len(pts) < 3:
        return ""
    (xh, yh), (xb, yb) = max(pts, key=lambda p: p[1]), min(pts, key=lambda p: p[1])
    return f"{courbe.name} : maximum {yh:.4g} en x = {xh:.4g}, minimum {yb:.4g} en x = {xb:.4g}."


def resume_graphique(fig: Any) -> str:
    """Description en texte d'un graphique : titre, axes, extrema de chaque courbe (dessin à l'échelle : titre seul)."""
    lay = fig.layout
    morceaux = [_sans_balises(lay.title.text)]
    if lay.yaxis.scaleanchor != "x":
        x, y = _sans_balises(lay.xaxis.title.text), _sans_balises(lay.yaxis.title.text)
        if x or y:
            morceaux.append(f"Axes : x = {x or '—'}, y = {y or '—'}.")
        courbes = [
            t for t in fig.data if t.type == "scatter" and t.name and not t.fill and "lines" in (t.mode or "lines")
        ]
        morceaux += [e for e in map(_extrema, courbes[:4]) if e]
    return " ".join(m for m in morceaux if m)


class TeteRepli(QFrame):
    """En-tête cliquable d'un bloc repliable : flèche et titre sur plusieurs lignes si la place manque."""

    toggled = Signal(bool)

    def __init__(self, titre: str, ouvert: bool) -> None:
        super().__init__()
        self.setObjectName("repli")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 4, 6, 4)
        self._fleche = QLabel()
        self._fleche.setFixedWidth(14)
        lab = QLabel(titre)
        lab.setWordWrap(True)
        lab.setStyleSheet("font-weight:bold;")
        lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        h.addWidget(self._fleche, 0, Qt.AlignmentFlag.AlignTop)
        h.addWidget(lab, 1)
        self.actif = ouvert
        self.fleche(ouvert)

    def fleche(self, actif: bool) -> None:
        self._fleche.setText("▾" if actif else "▸")

    def isChecked(self) -> bool:
        return self.actif

    def mousePressEvent(self, e) -> None:  # noqa: N802 : nom imposé par Qt
        self.actif = not self.actif
        self.toggled.emit(self.actif)


class GrilleChamps(QGridLayout):
    """Mise en page d'un volet de saisie : les champs (objectName « champ ») se rangent en colonnes égales, autant que la
    largeur le permet, comme la grille du site ; tout le reste (tableaux, textes, boutons) prend la ligne entière.

    Le nombre de colonnes suit la largeur du volet : à chaque changement, les éléments sont replacés dans la grille."""

    LARGEUR_MIN = 190  # largeur minimale d'une colonne de champs
    ESPACE = 10

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setContentsMargins(12, 2, 0, 6)
        self.setHorizontalSpacing(self.ESPACE)
        self.setVerticalSpacing(self.ESPACE)
        self._elements: list[QWidget] = []
        self._alignements: dict[QWidget, Any] = {}
        self._colonnes = 1
        parent.installEventFilter(self)

    def addWidget(self, w: QWidget, *args: Any) -> None:  # noqa: N802 : nom imposé par Qt
        if args:  # position donnée par l'appelant : comportement de QGridLayout
            super().addWidget(w, *args)
            return
        self._elements.append(w)
        self._placer()

    def setAlignment(self, w: QWidget, alignement: Any) -> bool:  # noqa: N802
        self._alignements[w] = alignement
        return super().setAlignment(w, alignement)

    def eventFilter(self, objet, evenement) -> bool:  # noqa: N802
        if objet is self.parentWidget() and evenement.type() == QEvent.Type.Resize:
            m = self.contentsMargins()
            largeur = objet.width() - m.left() - m.right()
            colonnes = max(1, (largeur + self.ESPACE) // (self.LARGEUR_MIN + self.ESPACE))
            if colonnes != self._colonnes:
                self._colonnes = colonnes
                self._placer()
        return False

    def _placer(self) -> None:
        """Replace tous les éléments : champs côte à côte, le reste sur toute la largeur."""
        for w in self._elements:
            self.removeWidget(w)
        for i in range(max(self.columnCount(), self._colonnes)):
            self.setColumnStretch(i, 1 if i < self._colonnes else 0)
        ligne = colonne = 0
        for w in self._elements:
            if w.objectName() == "champ":
                super().addWidget(w, ligne, colonne)
                colonne += 1
                if colonne == self._colonnes:
                    ligne, colonne = ligne + 1, 0
            else:
                if colonne:
                    ligne, colonne = ligne + 1, 0
                align = self._alignements.get(w)
                if align is None:
                    super().addWidget(w, ligne, 0, 1, self._colonnes)
                else:
                    super().addWidget(w, ligne, 0, 1, self._colonnes, align)
                ligne += 1


class Zone:
    """Emplacement où écrire : mêmes gestes partout (titre, texte, tableau, figure, champs, boutons)."""

    def __init__(self, page: "Page", disposition: Any, section: "Section | None" = None) -> None:
        self.page, self.d, self.section_ = page, disposition, section

    def _ajouter(self, w: QWidget, alignement: Any = None) -> QWidget:
        self.d.addWidget(w)
        if alignement is not None:
            self.d.setAlignment(w, alignement)
        return w

    def _libelle(self, texte: str, nom: str, md: bool = False) -> QLabel:
        lab = QLabel(texte)
        lab.setObjectName(nom)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setTextFormat(Qt.TextFormat.MarkdownText if md else Qt.TextFormat.PlainText)
        lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        return self._ajouter(lab)

    def titre(self, texte: str) -> None:
        self._libelle(texte, "titre")

    def sousTitre(self, texte: str) -> None:
        self._libelle(texte, "sousTitre")

    def intro(self, texte: str) -> None:
        """Phrase sous le titre de la page (la même que sur le site)."""
        self._libelle(texte, "intro")

    def texte(self, md: str) -> None:
        """Texte en Markdown (gras, listes)."""
        self._libelle(md, "texte", md=True)

    def legende(self, texte: str) -> None:
        self._libelle(texte, "legende")

    def brut(self, texte: str) -> None:
        """Ligne de rapport en chasse fixe."""
        self._libelle(texte, "brut")

    def message(self, niveau: str, texte: str) -> None:
        """Bandeau coloré : niveau « info », « succes », « avertissement » ou « erreur »."""
        lab = self._libelle(texte, "message", md=True)
        fond, encre = theme.couleur_message(niveau)
        lab.setStyleSheet(f"background:{fond};color:{encre};padding:8px 12px;border-radius:6px;")

    def info(self, texte: str) -> None:
        self.message("info", texte)

    def succes(self, texte: str) -> None:
        self.message("succes", texte)

    def avertissement(self, texte: str) -> None:
        self.message("avertissement", texte)

    def erreur(self, texte: str) -> None:
        self.message("erreur", texte)

    def modes(self, criteres: Sequence[dict], statut: str, ok: bool | None, perime: bool = False) -> None:
        """Diagramme des modes de ruine (voir bureau/modes.py) ; `perime` : saisie modifiée depuis le calcul, grisé."""
        from mecastruct.bureau.modes import ModesRuine

        self._ajouter(ModesRuine(criteres, statut, ok, perime))

    def statut(self, texte: str, ok: bool | None = None) -> None:
        """Ligne d'état : verte si ok, rouge si non ok, orange si inconnu (None)."""
        self.message("succes" if ok is True else "erreur" if ok is False else "avertissement", texte)

    def messageGarde(self, cle: str) -> None:
        """Affiche puis oublie le message (genre, texte) gardé sous cle ; genre « error » = erreur, sinon information."""
        m = state.v.pop(cle, None)
        if m:
            niveau = {"error": "erreur"}.get(m[0], m[0])
            self.message(niveau if niveau in NIVEAUX_MESSAGE else "info", m[1])

    def erreurCalcul(self, err: Exception) -> None:
        """Erreur de calcul : message et conseil pour MecaStructError, trace complète sinon."""
        from mecastruct.core.errors import MecaStructError

        if isinstance(err, MecaStructError):
            self.erreur(err.message)
            conseil = CONSEILS.get(str(err.identifier).split(":")[-1], "")
            if conseil:
                self.info(f"Conseil : {conseil}")
        else:
            import traceback

            self.erreur("Erreur inattendue pendant le calcul :")
            self.brut("".join(traceback.format_exception(type(err), err, err.__traceback__))[-1500:])

    def erreurGardee(self, cle: str) -> None:
        """Affiche puis oublie l'erreur de calcul gardée sous cle."""
        err = state.v.pop(cle, None)
        if err is not None:
            self.erreurCalcul(err)

    def metrique(self, libelle: str, valeur: str, aide: str | None = None, delta: str | None = None,
                 couleur: str = "off") -> None:  # fmt: skip
        cadre = QFrame()
        cadre.setObjectName("metrique")
        cadre.setToolTip(aide or "")
        col = QVBoxLayout(cadre)
        col.setContentsMargins(8, 4, 8, 4)
        col.setSpacing(0)
        valeur, delta = fr(valeur), fr(delta) if delta else delta  # virgule décimale, comme les champs et les tableaux
        haut, bas = QLabel(libelle), QLabel(valeur)
        haut.setObjectName("metriqueLibelle")
        haut.setWordWrap(True)
        bas.setObjectName("metriqueValeur")
        bas.setWordWrap(True)
        bas.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(haut)
        col.addWidget(bas)
        if delta:
            d = QLabel(delta)
            d.setWordWrap(True)
            d.setObjectName("metriqueDelta")
            p = theme.actuel()
            d.setStyleSheet(f"color:{ {'green': p['succes'][1], 'red': p['erreur'][1]}.get(couleur, p['discret']) };")
            col.addWidget(d)
        self._ajouter(cadre)

    def metriques(self, valeurs: Sequence[dict], parLigne: int = 3) -> None:
        """Valeurs clés : dicts label, value, delta et delta_color facultatifs, par rangées de parLigne."""
        for debut in range(0, len(valeurs), parLigne):
            cols = self.colonnes(parLigne)
            for col, m in zip(cols, valeurs[debut : debut + parLigne], strict=False):
                col.metrique(m["label"], m["value"], None, m.get("delta"), m.get("delta_color", "off"))

    def synthese(self, valeurs: Sequence[dict]) -> None:
        self.metriques(valeurs)

    def tableau(self, df: pd.DataFrame, formats: dict | None = None, couleurs: dict | None = None,
                index: bool = False) -> None:  # fmt: skip
        self._ajouter(TableauDonnees(df, formats, couleurs, index))

    def plot(self, fig: Any) -> None:
        """Graphique Plotly interactif, suivi d'une description en texte (lecture d'écran)."""
        self._ajouter(VueFigure(fig))
        if resume := resume_graphique(fig):
            self.legende(resume)

    def formule(self, tex: str) -> None:
        """Formule en texte Unicode sélectionnable (copier-coller) ; la source LaTeX reste dans l'info-bulle."""
        lab = self._libelle(versTexte(tex), "formule")
        lab.setToolTip(tex.strip().strip("$"))

    def formules(self, latex: Sequence[str]) -> None:
        for f in latex:
            self.formule(f)

    def rapport(self, lignes: Sequence[str]) -> None:
        """Rapport de calcul : les lignes « Résultats » et « Réaction » en encadré, les autres en chasse fixe."""
        for ligne in lignes:
            if ligne.startswith(("Résultats", "Réaction")):
                self.info(ligne)
            else:
                self.brut(ligne)

    def colonnes(self, poids: int | Sequence[int]) -> list["Zone"]:
        """Colonnes côte à côte (nombre, ou poids relatifs)."""
        poids = [1] * poids if isinstance(poids, int) else list(poids)
        ligne = QWidget()
        h = QHBoxLayout(ligne)
        h.setContentsMargins(0, 0, 0, 0)
        zones = []
        for p in poids:
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setAlignment(Qt.AlignmentFlag.AlignTop)
            h.addWidget(w, p)
            zones.append(Zone(self.page, v, self.section_))
        self._ajouter(ligne)
        return zones

    def cadre(self) -> "Zone":
        """Encadré : contenu groupé d'une carte."""
        w = QFrame()
        w.setObjectName("cadre")
        v = QVBoxLayout(w)
        self._ajouter(w)
        return Zone(self.page, v, self.section_)

    def repliable(self, titre: str, ouvert: bool = False, rendu: Callable[["Zone"], None] | None = None,
                  cle: str | None = None) -> "Zone":  # fmt: skip
        """Bloc repliable ; son état survit aux reconstructions. Avec `rendu`, le contenu n'est bâti qu'à l'ouverture."""
        cle = f"repli.{type(self.page).__name__}.{cle or titre}"
        ouvert = bool(state.v.get(cle, ouvert))
        tete = TeteRepli(titre, ouvert)
        corps = QWidget()
        v = GrilleChamps(corps)
        zone = Zone(self.page, v, self.section_)
        corps.setVisible(ouvert)
        bati = {"fait": rendu is None}

        def basculer(actif: bool) -> None:
            state.v[cle] = actif
            tete.fleche(actif)
            if actif and not bati["fait"]:
                bati["fait"] = True
                rendu(zone)
            corps.setVisible(actif)

        tete.toggled.connect(basculer)
        self._ajouter(tete)
        self._ajouter(corps)
        if ouvert and not bati["fait"]:
            bati["fait"] = True
            rendu(zone)
        return zone

    def onglets(self, rendus: dict[str, Callable[["Zone"], None]], cle: str | None = None) -> None:
        """Onglets : le contenu d'un onglet n'est bâti qu'à sa première ouverture (figures coûteuses)."""
        noms, faits = list(rendus), set()
        cle = cle or "onglet." + type(self.page).__name__ + "|".join(n.split(" (")[0] for n in noms)
        tabs = QTabWidget()
        zones: list[Zone] = []
        for nom in noms:
            w = QWidget()
            v = QVBoxLayout(w)
            v.setAlignment(Qt.AlignmentFlag.AlignTop)
            tabs.addTab(w, nom.replace("&", "&&"))  # « & » seul serait pris pour un raccourci clavier
            zones.append(Zone(self.page, v, self.section_))

        def ouvrir(i: int) -> None:
            state.v[cle] = noms[i]
            if i not in faits:
                faits.add(i)
                rendus[noms[i]](zones[i])

        depart = noms.index(state.v[cle]) if state.v.get(cle) in noms else 0
        tabs.setCurrentIndex(depart)
        ouvrir(depart)
        tabs.currentChanged.connect(ouvrir)
        self._ajouter(tabs)

    def section(self, rendu: Callable[["Zone"], None], suit: bool = False) -> "Section":
        """Partie redessinée à part ; avec suit, elle se redessine à chaque changement de la saisie."""
        s = Section(self.page, rendu, suit)
        if suit:
            self.page.suivis.append(s)
        self._ajouter(s)
        s.rafraichir()
        return s

    def bouton(self, texte: str, action: Callable[[], None], primaire: bool = False, actif: bool = True,
               aide: str | None = None) -> QPushButton:  # fmt: skip
        b = QPushButton(texte)
        b.setObjectName("primaire" if primaire else "bouton")
        b.setEnabled(actif)
        b.setToolTip(aide or "")
        b.clicked.connect(lambda: differer(action))
        self._ajouter(b, Qt.AlignmentFlag.AlignLeft)
        return b

    def lien(self, page: str, texte: str) -> None:
        """Lien vers une autre page de l'application."""
        b = QPushButton(texte)
        b.setObjectName("lien")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda: differer(lambda: self.page.aller(page)))
        self._ajouter(b)

    def telecharger(self, libelle: str, donnees: bytes | str | Callable[[], bytes | str], nomFichier: str,
                    actif: bool = True, aide: str | None = None) -> QPushButton:  # fmt: skip
        """Bouton d'enregistrement : demande où écrire le fichier ; donnees peut être une fonction (appelée au clic)."""

        def ecrire() -> None:
            chemin, _ = QFileDialog.getSaveFileName(self.page, "Enregistrer", nomFichier)
            if not chemin:
                return
            try:
                contenu = donnees() if callable(donnees) else donnees
                Path(chemin).write_bytes(contenu.encode("utf-8") if isinstance(contenu, str) else contenu)
            except OSError as e:
                QMessageBox.warning(self.page, "Enregistrement impossible", str(e))
            except Exception as e:  # noqa: BLE001 : conversion de dossier ratée
                QMessageBox.warning(self.page, "Export impossible", str(getattr(e, "message", e)))

        return self.bouton(libelle, ecrire, actif=actif, aide=aide)

    def ouvrirFichier(self, libelle: str, filtre: str, action: Callable[[list[tuple[str, bytes]]], None],
                      multiple: bool = False, aide: str | None = None) -> None:  # fmt: skip
        """Bouton d'ouverture : action reçoit la liste des (nom, octets) des fichiers choisis."""

        def ouvrir() -> None:
            if multiple:
                chemins, _ = QFileDialog.getOpenFileNames(self.page, libelle, "", filtre)
            else:
                chemin, _ = QFileDialog.getOpenFileName(self.page, libelle, "", filtre)
                chemins = [chemin] if chemin else []
            if chemins:
                action([(Path(c).name, Path(c).read_bytes()) for c in chemins])

        self.bouton(libelle, ouvrir, aide=aide)

    def _etiquette(self, libelle: str, w: QWidget, aide: str | None) -> QWidget:
        w.setToolTip(aide or "")
        if libelle:
            lab = QLabel(libelle)
            lab.setObjectName("etiquette")
            lab.setWordWrap(True)
            lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
            lab.setToolTip(aide or "")
            champ = QWidget()
            champ.setObjectName("champ")
            v = QVBoxLayout(champ)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(2)
            v.addWidget(lab)
            v.addWidget(w)
            self._ajouter(champ)
            return w
        return self._ajouter(w)

    def _rappel(self, cle: Any, valeur: Any, apres: Callable[[], None] | None) -> None:
        state.ecrire(cle, valeur)
        if apres:
            differer(apres)
        differer(self.page.surSaisie)

    def liste(self, libelle: str, options: Sequence, cle: Any, format: Callable[[Any], str] = str, defaut: Any = None,
              apres: Callable[[], None] | None = None, aide: str | None = None, actif: bool = True) -> Any:  # fmt: skip
        """Liste déroulante ; renvoie la valeur choisie (celle gardée, sinon `defaut`, sinon la première)."""
        options = list(options)
        v = state.lire(cle, defaut)
        v = v if v in options else (defaut if defaut in options else options[0] if options else None)
        state.ecrire(cle, v)
        boite = QComboBox()
        boite.addItems([format(o) for o in options])
        boite.setEnabled(actif)
        boite.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        boite.setMinimumContentsLength(8)
        if v in options:
            boite.setCurrentIndex(options.index(v))
        boite.activated.connect(lambda i: self._rappel(cle, options[i], apres))
        boite.wheelEvent = lambda e: e.ignore()  # la molette fait défiler la page, pas la liste
        self._etiquette(libelle, boite, aide)
        return v

    def radio(self, libelle: str, options: Sequence, cle: Any, format: Callable[[Any], str] = str, defaut: Any = None,
              apres: Callable[[], None] | None = None, aide: str | None = None, vertical: bool = False) -> Any:  # fmt: skip
        """Boutons radio ; renvoie la valeur choisie."""
        options = list(options)
        v = state.lire(cle, defaut)
        v = v if v in options else options[0]
        state.ecrire(cle, v)
        groupe = QWidget()
        d = QVBoxLayout(groupe) if vertical else QHBoxLayout(groupe)
        d.setContentsMargins(0, 0, 0, 0)
        boutons = QButtonGroup(groupe)
        for i, o in enumerate(options):
            b = QRadioButton(format(o))
            b.setChecked(o == v)
            boutons.addButton(b, i)
            d.addWidget(b)
        if not vertical:
            d.addStretch(1)
        boutons.idClicked.connect(lambda i: self._rappel(cle, options[i], apres))
        self._etiquette(libelle, groupe, aide)
        return v

    def multi(self, libelle: str, options: Sequence, cle: Any, format: Callable[[Any], str] = str,
              apres: Callable[[], None] | None = None, aide: str | None = None) -> list:  # fmt: skip
        """Choix multiple par cases à cocher ; renvoie la liste choisie, dans l'ordre des options."""
        options = list(options)
        choisis = [o for o in options if o in (state.lire(cle) or [])]
        state.ecrire(cle, choisis)
        boite = QListWidget()
        for o in options:
            it = QListWidgetItem(format(o))
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if o in choisis else Qt.CheckState.Unchecked)
            boite.addItem(it)
        boite.setFixedHeight(min(150, 8 + 22 * len(options)))

        def change() -> None:
            coches = [o for i, o in enumerate(options) if boite.item(i).checkState() == Qt.CheckState.Checked]
            if coches != state.lire(cle):
                self._rappel(cle, coches, apres)

        boite.itemChanged.connect(lambda _it: change())
        self._etiquette(libelle, boite, aide)
        return choisis

    def nombre(self, libelle: str, cle: Any, defaut: float | None = 0.0, mini: float | None = None,
               maxi: float | None = None, entier: bool = False, apres: Callable[[], None] | None = None,
               aide: str | None = None, actif: bool = True) -> Any:  # fmt: skip
        """Champ numérique (point ou virgule) ; entier = True : nombre entier."""
        v = state.lire(cle, defaut)
        state.ecrire(cle, v)
        champ = ChampNombre(v, entier, mini, maxi, lambda x: self._rappel(cle, x, apres))
        champ.setEnabled(actif)
        self._etiquette(libelle, champ, aide)
        return v

    def saisie(self, libelle: str, cle: Any, defaut: str = "", apres: Callable[[], None] | None = None,
               aide: str | None = None, indice: str = "", longueur: int | None = None) -> str:  # fmt: skip
        """Champ de texte ; le texte est pris en compte à la sortie du champ (ou Entrée)."""
        v = state.lire(cle, defaut)
        state.ecrire(cle, v)
        champ = QLineEdit(v)
        champ.setPlaceholderText(indice)
        if longueur:
            champ.setMaxLength(longueur)

        def valider() -> None:
            if champ.text() != state.lire(cle):
                self._rappel(cle, champ.text(), apres)

        champ.editingFinished.connect(valider)
        self._etiquette(libelle, champ, aide)
        return v

    def case(self, libelle: str, cle: Any, defaut: bool = False, apres: Callable[[], None] | None = None,
             aide: str | None = None) -> bool:  # fmt: skip
        v = bool(state.lire(cle, defaut))
        state.ecrire(cle, v)
        c = QCheckBox(libelle)
        c.setChecked(v)
        c.setToolTip(aide or "")
        c.toggled.connect(lambda x: self._rappel(cle, x, apres))
        self._ajouter(c)
        return v

    # --- gestes sur la saisie d'un onglet ---

    def securite(self, libelle: str, cle: Any, aide: str | None = None, apres: Callable[[], None] | None = None,
                 actif: bool = True) -> float:
        """Coefficient de sécurité s, ou marge en % (marge = s − 1) : réglage commun à toutes les pages (comme le site).

        La saisie garde toujours s ; la marge n'est qu'une autre façon de l'écrire."""
        marge = state.lire("securite", "coef") == "marge"
        s = state.lire(cle, 1.0)
        s = float(s) if isinstance(s, (int, float)) else 1.0
        boite = QComboBox()
        boite.addItems(["Coefficient s", "Marge (%)"])
        boite.setCurrentIndex(1 if marge else 0)
        boite.setToolTip("Coefficient de sécurité s, ou marge en % : marge = s − 1 (30 % donne s = 1,30). Valable pour toutes les pages.")

        def bascule(i: int) -> None:
            state.ecrire("securite", "marge" if i == 1 else "coef")
            differer(self.page.rafraichirTout)

        boite.currentIndexChanged.connect(bascule)
        champ = ChampNombre((s - 1.0) * 100.0 if marge else s, False, 0.0 if marge else 1e-12, None,
                            lambda x: self._rappel(cle, 1.0 + x / 100.0 if marge else x, apres))  # fmt: skip
        champ.setEnabled(actif)
        self._etiquette("Sécurité exprimée en", boite, "Coefficient s, ou marge en % (marge = s − 1) : même réglage sur toutes les pages.")
        self._etiquette("Marge de sécurité (%)" if marge else libelle, champ, aide)
        return s

    def num(self, tab: str, champ: str, label: str, unit: str = "", help: str | None = None,
            min_value: float | None = None, max_value: float | None = None, entier: bool = False,
            on_change: Callable[[], None] | None = None, actif: bool = True) -> Any:  # fmt: skip
        """Champ numérique lié à saisie[tab][champ] ; libellé « label (unit) »."""
        if champ == "s" and label.startswith("Coefficient de sécurité"):
            return self.securite(label, (tab, champ), help, on_change, actif)
        return self.nombre(f"{label} ({unit})" if unit else label, (tab, champ), mini=min_value, maxi=max_value,
                           entier=entier, apres=on_change, aide=help, actif=actif)  # fmt: skip

    def choice(self, tab: str, champ: str, label: str, options: Sequence, help: str | None = None,
               format_func: Callable[[Any], str] | None = None, on_change: Callable[[], None] | None = None,
               actif: bool = True) -> Any:  # fmt: skip
        """Liste déroulante liée à saisie[tab][champ] ; format_func donne le libellé affiché de chaque option."""
        return self.liste(label, options, (tab, champ), format=format_func or str, apres=on_change, aide=help,
                          actif=actif)  # fmt: skip

    def check(self, tab: str, champ: str, label: str, help: str | None = None,
              on_change: Callable[[], None] | None = None) -> bool:  # fmt: skip
        return self.case(label, (tab, champ), apres=on_change, aide=help)

    def text(self, tab: str, champ: str, label: str, help: str | None = None) -> str:
        return self.saisie(label, (tab, champ), aide=help)

    def table(self, tab: str, champ: str, colonnes: list[Colonne], help: str | None = None,
              polaire: dict | None = None) -> TableauEditable:
        """Tableau éditable (lignes ajoutables et supprimables) sur saisie[tab][champ], liste de dicts."""
        if help:
            self.legende(help)
        t = TableauEditable(tab, champ, colonnes, self.page.surSaisie, polaire=polaire)
        self._ajouter(t)
        boutons = self.colonnes(3)
        boutons[0].bouton("Ajouter une ligne", t.ajouter)
        boutons[1].bouton("Supprimer la sélection", t.supprimer)
        return t

    def choice_materiau(self, tab: str, champs: list[str], dm: Any, label: str = "Matériau",
                        actif: bool = True) -> str:
        """Liste des matériaux liée à saisie[tab]["mat"] ; un changement remplit les champs `champs` (E, G, Re…)."""
        from mecastruct.services import compute

        def applique() -> None:
            for champ, valeur in compute._materiau(dm, state.saisie(tab)["mat"], champs).items():
                if math.isfinite(valeur):  # comme applyMaterial : un champ inconnu de la base reste inchangé
                    state.saisie(tab)[champ] = valeur
            self.page.rafraichirSaisie()

        return self.choice(tab, "mat", label, dm.listMaterials(), on_change=applique, actif=actif)

    def graphs(self, cle: str, contenus: list[tuple[str, Callable[["Zone"], Any]]],
               dessous: tuple[str, ...] = ()) -> list:  # fmt: skip
        """Graphiques les uns sous les autres, chacun avec son titre ; la case « Graphiques en onglets » les groupe.

        Les titres de `dessous` ne sont pas tracés en mode empilé : ils sont renvoyés, pour que l'appelant les range
        avec ses propres onglets (en mode onglets, ils restent dans les onglets des graphiques : liste vide).
        """
        if len(contenus) > 1 and self.case("Graphiques en onglets", cle, apres=self.page.surSaisie):
            self.onglets(dict(contenus), cle=cle + ".onglet")
            return []
        for titre, affiche in contenus:
            if titre not in dessous:
                self.sousTitre(titre)
                affiche(self)
        return [c for c in contenus if c[0] in dessous]

    def curseur(self, libelle: str, cle: Any, defaut: float, mini: float, maxi: float, pas: float, fmt: str = "%g",
                continu: Callable[[], None] | None = None, apres: Callable[[], None] | None = None,
                aide: str | None = None) -> float:  # fmt: skip
        """Curseur ; `continu` est appelé pendant le glissement, `apres` au relâchement."""
        v = float(state.lire(cle, defaut))
        state.ecrire(cle, v)
        c = QSlider(Qt.Orientation.Horizontal)
        c.setRange(0, round((maxi - mini) / pas))
        c.setValue(round((v - mini) / pas))
        tete = QLabel(f"{libelle} : {(fmt % v).replace('.', ',')}")
        tete.setObjectName("etiquette")
        tete.setToolTip(aide or "")
        c.setToolTip(aide or "")
        c.wheelEvent = lambda e: e.ignore()

        def bouge(i: int) -> None:
            x = mini + i * pas
            state.ecrire(cle, x)
            tete.setText(f"{libelle} : {(fmt % x).replace('.', ',')}")
            if continu:
                differer(continu)

        c.valueChanged.connect(bouge)
        if apres:
            c.sliderReleased.connect(lambda: differer(apres))
        self._ajouter(tete)
        self._ajouter(c)
        return v


class Section(QWidget):
    """Partie de page redessinée d'un bloc par sa fonction de rendu."""

    def __init__(self, page: "Page", rendu: Callable[[Zone], None], suit: bool = False) -> None:
        super().__init__()
        self.page, self.rendu, self.suit = page, rendu, suit
        self.mode3d = False  # section du mode « Ossature 3D » de la page Poutres
        self.disposition = QVBoxLayout(self)
        self.disposition.setContentsMargins(0, 0, 0, 0)
        self.disposition.setAlignment(Qt.AlignmentFlag.AlignTop)

    def _defilement(self) -> QScrollArea | None:
        w = self.parentWidget()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parentWidget()
        return w

    def rafraichir(self) -> None:
        zone = self._defilement()
        position = zone.verticalScrollBar().value() if zone else 0
        self.setUpdatesEnabled(False)
        vider(self.disposition)
        self.rendu(Zone(self.page, self.disposition, self))
        self.setUpdatesEnabled(True)
        if zone and position:
            QTimer.singleShot(0, lambda: zone.verticalScrollBar().setValue(position))


def _defilable(contenu: QWidget) -> QScrollArea:
    a = QScrollArea()
    a.setWidgetResizable(True)
    a.setFrameShape(QFrame.Shape.NoFrame)
    a.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    a.setWidget(contenu)
    return a


class Page(QWidget):
    """Page de la fenêtre. Une page simple redéfinit rendre(zone) ; une page à deux panneaux, deuxPanneaux."""

    def __init__(self, fenetre: Any) -> None:
        super().__init__()
        self.fenetre = fenetre
        self.d = QVBoxLayout(self)
        self.d.setContentsMargins(16, 10, 8, 8)
        self.sections: list[Section] = []
        self.suivis: list[Section] = []  # parties de la saisie qui suivent la saisie (valeurs clés)
        self.bati = False

    def aller(self, page: str) -> None:
        self.fenetre.aller(page)

    def afficher(self) -> None:
        """Appelée à chaque ouverture de la page : tout repart de l'état courant."""
        if not self.bati:
            self.bati = True
            self.construire()
        for s in self.actives():
            s.rafraichir()

    def actives(self) -> list[Section]:
        """Sections à redessiner (toutes, sauf pour une page qui en cache certaines)."""
        return self.sections

    def surSaisie(self) -> None:
        """Une valeur de la saisie a changé : les sections qui suivent la saisie (aperçus, résultats) se redessinent."""
        self.suivis = [s for s in self.suivis if isValid(s)]
        for s in list(self.suivis):
            s.rafraichir()
        for s in self.actives():
            if s.suit:
                s.rafraichir()

    def rafraichirSaisie(self) -> None:
        """Redessine les champs de saisie (après un changement de la saisie par programme)."""
        for s in self.actives():
            if not s.suit:
                s.rafraichir()

    def rafraichirTout(self) -> None:
        for s in self.actives():
            s.rafraichir()

    def construire(self) -> None:
        s = Section(self, self.rendre)
        self.sections.append(s)
        self.d.addWidget(_defilable(s))

    def rendre(self, z: Zone) -> None:
        raise NotImplementedError

    def deuxPanneaux(self, tete: Callable[[Zone], None], gauche: Callable[[Zone], None],
                     droite: Callable[[Zone], None]) -> tuple[Section, Section]:  # fmt: skip
        """En-tête puis saisie à gauche et visualisation à droite, chacune défilant seule."""
        haut = Section(self, tete)
        sg, sd = Section(self, gauche), Section(self, droite, suit=True)
        self.sections += [haut, sg, sd]
        self.d.addWidget(haut)
        self.panneau = partage(sg, sd)
        self.d.addWidget(self.panneau, 1)
        return sg, sd


def partage(gauche: QWidget, droite: QWidget) -> QSplitter:
    """Deux panneaux défilants côte à côte, séparés par une barre déplaçable."""
    s = QSplitter(Qt.Orientation.Horizontal)
    s.addWidget(_defilable(gauche))
    s.addWidget(_defilable(droite))
    s.setStretchFactor(0, 2)
    s.setStretchFactor(1, 3)
    s.setSizes([480, 820])
    return s


def appliquerTheme(app: QApplication, nom: str | None = None) -> None:
    """Applique le thème « clair » ou « sombre » (celui en cours si `nom` est omis) : mêmes couleurs que le site."""
    if nom is not None:
        theme.definir(nom)
    app.setStyleSheet(theme.feuille_de_style())
    from PySide6.QtGui import QColor, QPalette

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Link, QColor(theme.actuel()["lien"]))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(theme.actuel()["lien"]))
    app.setPalette(palette)

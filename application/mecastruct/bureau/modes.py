"""Diagramme des modes de ruine de l'application de bureau (même contenu et mêmes mots que le site).

Une ligne par critère (services/criteres.py) : nom du mode, pastille « Admissible » ou « Non admissible », barre du taux
de travail avec un trait à 100 %, valeur pour limite admissible, taux, coefficient ou marge de sécurité (résistance) ou
réserve 1 − taux (limite).
"""

from collections.abc import Callable, Sequence
from html import escape

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from mecastruct.bureau import state, theme
from mecastruct.services import export_texte
from mecastruct.services.decision import Decision


def _couleurs(nom: str) -> tuple[str, str, str]:
    """(fond de la pastille, texte, barre) de l'état « ok », « ko » ou « neutre » dans le thème en cours."""
    p = theme.actuel()
    if nom == "ok":
        return (*p["succes"], p["jaugeOk"])
    if nom == "ko":
        return (*p["erreur"], p["jaugeKo"])
    return (*p["info"], p["accent"])


class Jauge(QWidget):
    """Barre du taux de travail : remplie jusqu'à `taux` (en part de `echelle`), trait à 100 %."""

    def __init__(self, taux: float, echelle: float, ok: bool) -> None:
        super().__init__()
        self.taux, self.echelle, self.ok = taux, echelle, ok
        self.setFixedHeight(18)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip("Part de l'admissible utilisée. Le trait marque 100 % : au-delà, le mode n'est pas admissible.")
        self.setAccessibleName(f"Taux de travail {export_texte.nombre(100 * taux, 3)} %")

    def paintEvent(self, _event) -> None:  # noqa: N802 : nom imposé par Qt
        p = QPainter(self)
        pal = theme.actuel()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x0, w, h = 1.0, self.width() - 2.0, 12.0
        y0 = (self.height() - h) / 2
        p.setPen(QPen(QColor(pal["bord"]), 1))
        p.setBrush(QColor(pal["alt"]))
        p.drawRoundedRect(QRectF(x0, y0, w, h), 6, 6)
        remplie = max(4.0, w * min(self.taux, self.echelle) / self.echelle)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_couleurs("ok" if self.ok else "ko")[2]))
        p.drawRoundedRect(QRectF(x0, y0, min(remplie, w), h), 6, 6)
        trait = x0 + w / self.echelle
        p.setPen(QPen(QColor(pal["encre"]), 2))
        p.drawLine(int(trait), int(y0 - 3), int(trait), int(y0 + h + 3))
        p.end()


def _pastille(texte: str, couleurs: tuple[str, str, str], gras_taille: str = "9pt") -> QLabel:
    lab = QLabel(texte)
    lab.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    lab.setStyleSheet(
        f"background:{couleurs[0]};color:{couleurs[1]};border-radius:9px;padding:2px 10px;font-weight:bold;"
        f"font-size:{gras_taille};"
    )
    return lab


def _texte(texte: str, style: str = "") -> QLabel:
    lab = QLabel(texte)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    lab.setStyleSheet(f"background:transparent;{style}")
    return lab


class ModesRuine(QFrame):
    """Cadre du verdict : pastille et phrase, une ligne par mode de ruine, puis la ligne d'état du calcul."""

    def __init__(self, criteres: Sequence[dict], status: str, ok: bool | None, perime: bool = False) -> None:
        super().__init__()
        etat = _couleurs("neutre" if ok is None else "ok" if ok else "ko")
        pal = theme.actuel()
        self.setObjectName("modes")
        self.setStyleSheet(
            f"#modes{{background:{pal['carte']};border:1px solid {pal['bord']};border-left:6px solid {etat[2]};"
            "border-radius:8px;}"
        )
        col = QVBoxLayout(self)
        col.setContentsMargins(12, 8, 12, 8)
        col.setSpacing(4)
        tete = QHBoxLayout()
        tete.addWidget(_pastille({None: "Indicatif", True: "Vérifié", False: "Non vérifié"}[ok], etat, "10pt"))
        tete.addWidget(_texte(export_texte.phrase_bilan(criteres), "font-weight:bold;font-size:11pt;"), 1)
        col.addLayout(tete)
        echelle = min(2.0, max(1.25, *(c["taux"] * 1.08 for c in criteres)))
        pire = max(criteres, key=lambda c: c["taux"])
        groupe = ""
        for c in criteres:
            if c.get("groupe") and c["groupe"] != groupe:
                col.addWidget(_texte(c["groupe"].upper(), f"color:{pal['discret']};font-size:8pt;font-weight:bold;margin-top:6px;"))
            groupe = c.get("groupe") or ""
            col.addWidget(self._ligne(c, echelle, c is pire and len(criteres) > 1))
        col.addWidget(_texte(export_texte.phrase_etat(status), "font-size:9pt;margin-top:4px;"))
        if perime:  # la saisie a changé depuis le calcul : verdict grisé
            effet = QGraphicsOpacityEffect(self)
            effet.setOpacity(0.45)
            self.setGraphicsEffect(effet)

    @staticmethod
    def _ligne(c: dict, echelle: float, pire: bool) -> QWidget:
        boite = QWidget()
        boite.setStyleSheet("background:transparent;")
        col = QVBoxLayout(boite)
        col.setContentsMargins(0, 4, 0, 4)
        col.setSpacing(2)
        haut = QHBoxLayout()
        nom = c["mode"] + (" · le plus sollicité" if pire else "")
        haut.addWidget(_texte(nom, "font-weight:bold;"), 1)
        haut.addWidget(_pastille(("✓ Admissible" if c["ok"] else "✗ Non admissible"), _couleurs("ok" if c["ok"] else "ko"), "8pt"))
        col.addLayout(haut)
        col.addWidget(Jauge(c["taux"], echelle, c["ok"]))
        valeurs, taux, marge = export_texte.chiffres(c, state.lire("securite", "coef") == "marge")
        col.addWidget(_texte("   ·   ".join(x for x in (valeurs, taux, marge) if x), f"color:{theme.actuel()['discret']};font-size:9pt;"))
        return boite


class BlocDecision(QFrame):
    """Tête de résultat : verdict (texte, icône, couleur), coefficient de sécurité minimal, mode dimensionnant, paramètre
    le plus influent, avertissement, action conseillée et lien « Aller à la cause » (comme le bloc « Décision » du site).

    `aller(cibles)` donne le focus au champ ou au groupe désigné (vrai si trouvé), `peut(cibles)` dit si le lien a un
    sens, `nom(champ)` donne le libellé d'un champ. Les cibles sont celles de services/decision.py."""

    def __init__(self, d: Decision, aller: Callable[[list[str]], bool], peut: Callable[[list[str]], bool],
                 nom: Callable[[str], str], perime: bool = False) -> None:  # fmt: skip
        super().__init__()
        self.decision = d
        self.lienCause: QPushButton | None = None  # lien « Aller à la cause », s'il y a une cause à désigner
        pal = theme.actuel()
        etat = _couleurs("ok" if d.niveau == "ok" else "ko" if d.niveau == "ko" else "neutre")
        self.setObjectName("decision")
        self.setAccessibleName("Décision")
        self.setStyleSheet(
            f"#decision{{background:{pal['carte']};border:1px solid {pal['bord']};border-left:6px solid {etat[2]};"
            "border-radius:8px;}"
        )
        col = QVBoxLayout(self)
        col.setContentsMargins(12, 8, 12, 8)
        col.setSpacing(4)
        self.verdict = _pastille(f"{d.icone} {d.mot}", etat, "12pt")
        self.verdict.setObjectName("decisionVerdict")
        col.addWidget(self.verdict)
        for fait in d.faits:
            ligne = QHBoxLayout()
            ligne.setSpacing(6)
            intitule = QLabel(f"{fait.titre} :")  # sur une seule ligne : un libellé qui s'enroule rendrait la rangée haute
            intitule.setStyleSheet(f"background:transparent;color:{pal['discret']};")
            intitule.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            ligne.addWidget(intitule)
            if fait.champ is not None:  # paramètre le plus influent : lien vers le champ
                lien = QPushButton(nom(fait.champ))
                lien.setObjectName("lien")
                lien.setCursor(Qt.CursorShape.PointingHandCursor)
                lien.setToolTip("Va à ce champ.")
                lien.clicked.connect(lambda _=False, c=fait.champ: self._aller(aller, [c]))
                ligne.addWidget(lien)
                ligne.addStretch(1)
            else:
                texte = f"<b>{escape(fait.valeur)}</b>" + (f" <span style='color:{pal['discret']};'>{escape(fait.sous)}</span>" if fait.sous else "")
                lab = _texte(texte)
                lab.setTextFormat(Qt.TextFormat.RichText)
                ligne.addWidget(lab, 1)
            col.addLayout(ligne)
        if d.avertissement:
            fond, encre = theme.couleur_message("avertissement")
            lab = _texte(f"⚠ {d.avertissement}", f"background:{fond};color:{encre};padding:6px 10px;border-radius:6px;")
            lab.setObjectName("decisionAvertissement")
            col.addWidget(lab)
        action = QHBoxLayout()
        action.setSpacing(8)
        lab = _texte(d.action)
        lab.setObjectName("decisionAction")
        action.addWidget(lab, 1)
        if d.cause and peut(d.cause):
            bouton = QPushButton("Aller à la cause")
            bouton.setObjectName("lien")
            bouton.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton.setAccessibleName(f"Aller à la cause : {d.nom_cause}")
            bouton.setToolTip("Va au champ ou au groupe de champs qui influence le plus ce critère.")
            bouton.clicked.connect(lambda _=False: self._aller(aller, d.cause))
            self.lienCause = bouton
            action.addWidget(bouton)
        col.addLayout(action)
        if perime:  # verdict d'une ancienne saisie : grisé
            effet = QGraphicsOpacityEffect(self)
            effet.setOpacity(0.6)
            self.setGraphicsEffect(effet)

    @staticmethod
    def _aller(aller: Callable[[list[str]], bool], cibles: list[str]) -> None:
        if not aller(cibles):
            QToolTip.showText(QCursor.pos(), "Le champ à corriger n'est pas affiché avec la saisie actuelle.")

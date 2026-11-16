"""Diagramme des modes de ruine de l'application de bureau (même contenu et mêmes mots que le site).

Une ligne par critère (services/criteres.py) : nom du mode, pastille « Admissible » ou « Non admissible », barre du taux
de travail avec un trait à 100 %, valeur pour limite admissible, taux, coefficient de sécurité (résistance) ou marge.
"""

from collections.abc import Sequence

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from mecastruct.services import export_texte

OK = ("#C8F0D2", "#0B3D1A", "#1E8E4A")  # fond de la pastille, texte, barre
KO = ("#FFC2C2", "#6B0A12", "#C62B36")
NEUTRE = ("#E4E0F3", "#3D246C", "#5C4B99")
ENCRE, BORD, SILLON = "#1E1B2E", "#8E86AA", "#E4E0F3"


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
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x0, w, h = 1.0, self.width() - 2.0, 12.0
        y0 = (self.height() - h) / 2
        p.setPen(QPen(QColor(BORD), 1))
        p.setBrush(QColor(SILLON))
        p.drawRoundedRect(QRectF(x0, y0, w, h), 6, 6)
        remplie = max(4.0, w * min(self.taux, self.echelle) / self.echelle)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor((OK if self.ok else KO)[2]))
        p.drawRoundedRect(QRectF(x0, y0, min(remplie, w), h), 6, 6)
        trait = x0 + w / self.echelle
        p.setPen(QPen(QColor(ENCRE), 2))
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
        etat = NEUTRE if ok is None else OK if ok else KO
        self.setObjectName("modes")
        self.setStyleSheet(
            f"#modes{{background:#FFFFFF;border:1px solid {BORD};border-left:6px solid {etat[2]};border-radius:6px;}}"
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
                col.addWidget(_texte(c["groupe"].upper(), "color:#4A4560;font-size:8pt;font-weight:bold;margin-top:6px;"))
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
        haut.addWidget(_pastille(("✓ Admissible" if c["ok"] else "✗ Non admissible"), OK if c["ok"] else KO, "8pt"))
        col.addLayout(haut)
        col.addWidget(Jauge(c["taux"], echelle, c["ok"]))
        valeurs, taux, marge = export_texte.chiffres(c)
        col.addWidget(_texte("   ·   ".join(x for x in (valeurs, taux, marge) if x), "color:#4A4560;font-size:9pt;"))
        return boite

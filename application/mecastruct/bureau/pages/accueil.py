"""Page d'Accueil : la même que sur le site (titre, deux façons de l'utiliser, une carte par famille), puis les repères.

Sous les cartes : « Comment faire », le projet, les unités et conventions de signe, les limites et les sources.
"""

import os
import sys
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from mecastruct.bureau import dossier, etudes, state, theme
from mecastruct.bureau.widgets import Page, Zone, differer
from mecastruct.services.pages_texte import FAMILLES, INTROS

QWIDGETSIZE_MAX = 16777215


def mouvement_reduit() -> bool:
    """Vrai si le système demande de réduire les animations (Windows : « Effets d'animation » désactivés), ou si
    MECASTRUCT_SANS_ANIMATION est défini : les cartes s'ouvrent alors sans transition, comme sur le site."""
    if os.environ.get("MECASTRUCT_SANS_ANIMATION"):
        return True
    if sys.platform == "win32":
        try:
            import ctypes

            actif = ctypes.c_int(1)
            if ctypes.windll.user32.SystemParametersInfoW(
                0x1042, 0, ctypes.byref(actif), 0
            ):  # SPI_GETCLIENTAREAANIMATION
                return not actif.value
        except (AttributeError, OSError):
            pass
    return False


class CarteFamille(QFrame):
    """Carte d'une famille de pages, repliée par défaut (même comportement que sur le site, docs/js/accueil.js).

    Un clic ouvre la carte et la garde ouverte, un second la referme ; Échap la referme. Au survol de la souris elle s'ouvre
    et se referme 250 ms après le départ du pointeur, sauf si un clic l'a gardée ouverte ou si le focus clavier est dedans.
    Hauteur animée sur 200 ms ; sans animation quand le système réduit les mouvements."""

    DELAI_FERMETURE = 250
    DUREE = 200

    def __init__(
        self, titre: str, legende: str, pages: list[tuple[str, str, str]], aller: Callable[[str], None]
    ) -> None:
        super().__init__()
        self.setObjectName("repli")
        self.titre = titre
        self._ouvert = False
        self._epingle = False  # ouverte (ou gardée) par un clic ou le clavier
        self._par_survol = False  # ouverte seulement par le survol
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(2)
        if legende:
            lab = QLabel(legende)
            lab.setObjectName("legende")
            lab.setWordWrap(True)
            lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
            v.addWidget(lab)
        self.entete = QPushButton()
        self.entete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.entete.setStyleSheet(
            "QPushButton{background:transparent;border:none;text-align:left;font-weight:bold;font-size:13pt;padding:4px 2px;}"
            f"QPushButton:hover,QPushButton:focus{{color:{theme.actuel()['lien']};}}"
        )
        self.entete.clicked.connect(self.clic)
        v.addWidget(self.entete)
        self.corps = QWidget()
        self.corps.setStyleSheet("background:transparent;")
        c = QVBoxLayout(self.corps)
        c.setContentsMargins(0, 0, 0, 4)
        c.setSpacing(0)
        for ident, libelle, intro in pages:
            b = QPushButton(libelle)
            b.setObjectName("lien")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=ident: differer(lambda: aller(i)))
            c.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
            if intro:
                lab = QLabel(intro)
                lab.setObjectName("legende")
                lab.setWordWrap(True)
                lab.setContentsMargins(8, 0, 0, 4)
                lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
                c.addWidget(lab)
        v.addWidget(self.corps)
        self.corps.setVisible(False)
        self.corps.setMaximumHeight(0)
        self._anim = QPropertyAnimation(self.corps, b"maximumHeight", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._fin)
        self._minuterie = QTimer(self)
        self._minuterie.setSingleShot(True)
        self._minuterie.timeout.connect(self._depart)
        self._maj_entete()

    # --------------------------------------------------------------------------------------------- état

    def ouverte(self) -> bool:
        """Vrai si la carte est (ou va être, pendant l'animation) ouverte."""
        return self._ouvert

    def _maj_entete(self) -> None:
        self.entete.setText(("▾  " if self._ouvert else "▸  ") + self.titre)
        self.entete.setAccessibleName(f"{self.titre} : {'ouverte' if self._ouvert else 'repliée'}")

    def _regler(self, ouvert: bool) -> None:
        if ouvert == self._ouvert:
            return
        self._ouvert = ouvert
        self._maj_entete()
        self._anim.stop()
        corps = self.corps
        if mouvement_reduit():
            corps.setVisible(ouvert)
            corps.setMaximumHeight(QWIDGETSIZE_MAX)
            return
        depart = corps.height() if corps.isVisible() else 0
        if ouvert:
            corps.setMaximumHeight(depart)
            corps.setVisible(True)
            cible = self._hauteur_corps()
        else:
            cible = 0
        self._anim.setDuration(self.DUREE)
        self._anim.setStartValue(depart)
        self._anim.setEndValue(cible)
        self._anim.start()

    def _hauteur_corps(self) -> int:
        lay = self.corps.layout()
        largeur = max(1, self.width() - 24)
        h = lay.totalHeightForWidth(largeur) if lay.hasHeightForWidth() else lay.sizeHint().height()
        return max(h, lay.sizeHint().height())

    def _fin(self) -> None:
        if self._ouvert:
            self.corps.setMaximumHeight(QWIDGETSIZE_MAX)
        else:
            self.corps.setVisible(False)

    def _fermer(self) -> None:
        self._minuterie.stop()
        self._epingle = self._par_survol = False
        self._regler(False)

    # ------------------------------------------------------------------------------------------ gestes

    def clic(self) -> None:
        self._minuterie.stop()
        if self._ouvert and self._par_survol:  # ouverte par le survol : le clic la garde ouverte
            self._par_survol, self._epingle = False, True
        elif self._ouvert:  # le clic referme
            self._fermer()
        else:  # le clic ouvre et garde ouvert
            self._epingle, self._par_survol = True, False
            self._regler(True)

    def survol_entre(self) -> None:
        self._minuterie.stop()
        if not self._ouvert:
            self._par_survol, self._epingle = True, False
            self._regler(True)

    def survol_sort(self) -> None:
        if self._par_survol:
            self._minuterie.start(self.DELAI_FERMETURE)

    def _depart(self) -> None:
        """Le pointeur est parti depuis 250 ms : la carte ouverte par le survol se referme, sauf si le focus y est."""
        focus = self.focusWidget()
        if self._par_survol and not (focus is not None and focus.hasFocus()):
            self._fermer()

    def enterEvent(self, e) -> None:  # noqa: N802 : nom imposé par Qt
        self.survol_entre()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802 : nom imposé par Qt
        self.survol_sort()
        super().leaveEvent(e)

    def keyPressEvent(self, e) -> None:  # noqa: N802 : nom imposé par Qt
        if e.key() == Qt.Key.Key_Escape and self._ouvert:
            self._fermer()
            self.entete.setFocus()
        else:
            super().keyPressEvent(e)


class PageAccueil(Page):
    def rendre(self, z: Zone) -> None:
        state.init()
        z.titre("Calculs de résistance des matériaux et d'éléments de machines")
        z.intro(
            "Chaque calcul donne un verdict, un diagramme des modes de ruine avec les coefficients de sécurité, les "
            "formules remplies avec vos valeurs et la démarche pas à pas. Il s'exporte en dossier de validation, en "
            "bloc-notes ou en Excel à formules. Plus de 1 300 tests vérifient les calculs."
        )
        z.lien("ajustements", "Commencer par un ajustement ISO 286")
        z.lien("limites", "Ce qui est vérifié")

        z.sousTitre("Deux façons de l'utiliser")
        z.texte(
            "**Sur le bureau Windows** (vous y êtes) : démarrage immédiat, hors ligne, dossiers de validation PDF et "
            "Word. Vos saisies restent sur cet ordinateur.\n\n"
            "**Dans le navigateur** : aucune installation, toutes les pages, mêmes calculs. Le bouton « Version en "
            "ligne », en haut de la fenêtre, l'ouvre."
        )
        etudes.section(z, self.fenetre)  # récents, favoris, copies nommées (comme « Mes études » du site)

        z.sousTitre("Les cinq familles")
        z.legende(
            "Passez la souris sur une famille (ou cliquez) pour voir ses pages ; chaque famille rouvre sa dernière page."
        )
        self.cartes = []
        for famille, pages in self.fenetre.familles.items():
            lignes = [
                (i, lib, INTROS.get(lib, "")) for i, lib in pages if i != "apropos"
            ]  # « À propos » : pied de page du site
            carte = CarteFamille(famille, FAMILLES.get(famille, ""), lignes, self.aller)
            self.cartes.append(carte)
            z._ajouter(carte)

        z.texte(
            "Chaque page est déjà remplie avec un exemple d'école : cliquez sur « Calculer » pour voir un résultat, "
            "puis changez les valeurs."
        )

        def comment(c: Zone) -> None:
            c.texte(
                "1. **Appuis** : le tableau Appuis donne leur position et leur type "
                "(la légende dessous dit ce que chacun bloque).\n"
                "2. **Chargement** : les tableaux Forces et Charges réparties donnent le chargement. "
                "Une force vers le bas est négative. « Charge rapide » aide à saisir une charge répartie.\n"
                "3. **Calcul** : lancez le calcul, regardez le schéma, puis les diagrammes de T et de Mf : "
                "le moment est maximal où T change de signe.\n"
                "4. **Rapport** : lisez le rapport. Sa première ligne est le verdict : "
                "la poutre résiste-t-elle, avec quelle marge ?\n"
                "5. **Flambage** : une poutre comprimée doit aussi être vérifiée au flambage (page Flambage)."
            )

        z.repliable("Comment faire : une poutre de A à Z (5 étapes)", ouvert=True, rendu=comment)

        z.sousTitre("Projet")
        dossier.project_bar(z)

        z.sousTitre("À retenir avant de saisir")
        z.texte(
            "**Unités de saisie** : sections en mm, longueurs de poutre en m, forces en kN, moments en kN·m, "
            "charges réparties en kN/m, E et G en GPa, contraintes en MPa."
        )
        z.texte(
            "**Signes** : une force vers le bas est négative (Fy < 0). N > 0 : traction. "
            "Mfz > 0 : fibres du haut comprimées, fibres du bas tendues. "
            "Torseur de cohésion : actions à droite de la coupe."
        )
        z.texte(
            "Un tableau (appuis, forces…) se remplit avec « Ajouter une ligne » ; "
            "« Supprimer la sélection » retire la ligne choisie. "
            "Le bloc « Formulaire rapide », en haut de chaque page de calcul, affiche la fiche de formules de la page."
        )

        z.repliable(
            "Limites connues de l'application",
            rendu=lambda c: c.texte(
                "- **Poutre hyperstatique avec Iyz ≠ 0** (section sans axes principaux, par exemple une cornière) : "
                "les réactions sont calculées plan par plan, le couplage y–z est ignoré. "
                "Saisir la section dans ses axes principaux (Iyz = 0). "
                "En isostatique, Iyz ≠ 0 est traité exactement.\n"
                "- **Dossier de validation, contrainte au point le plus sollicité** : non recalculée à la main "
                "pour une section dissymétrique ni pour Iyz ≠ 0 ; le dossier le dit.\n"
                "- **Normes** : seules les vérifications Eurocode 3 de la documentation sont normatives ; "
                "l'interaction N + M (annexe B) est à vérifier dans le texte de l'EN 1993-1-1.\n"
                "- **Formules** : dessinées par l'application, sans connexion Internet ; une syntaxe non reconnue "
                "reste écrite en LaTeX brut."
            ),
        )
        z.repliable(
            "Auteur et sources",
            rendu=lambda c: c.texte(
                "Application de **Théo Brun**, basée sur son cours de Résistance des Matériaux.\n\n"
                "- Cours de RDM de l'auteur : formules, conventions de signe, arbre de décision du flambage, "
                "matériaux, pressions de matage.\n"
                "- Cours de l'Université de Bordeaux (IUT GMP, Master Génie mécanique) : roulements, engrenages, "
                "trains épicycloïdaux, freins et embrayages, frettage, fatigue, milieux continus. La liste complète, "
                "avec établissements et années, est dans la page **Références**.\n"
                "- Théorie classique de la RDM : Fanchon (*Guide du calcul en mécanique*), *Mémotech*, "
                "cours de RDM des IUT GMP "
                "(Navier, Huygens, Jourawski, Euler, Castigliano, Ménabréa, cercles de Mohr, Tresca, Von Mises, "
                "Hooke).\n"
                "- Pilkey, *Peterson's Stress Concentration Factors* : ajustements des abaques Kt.\n"
                "- Tables de profilés Eurocode 3 et fabricants : dimensions et caractéristiques des profilés."
            ),
        )
        z.legende(
            "Outil pédagogique et d'aide au pré-dimensionnement. Les résultats ne remplacent ni une note de calcul "
            "certifiée ni les normes en vigueur et doivent être vérifiés avant tout usage réel."
        )
        z.lien("apropos", "À propos")

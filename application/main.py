"""Application de bureau « MecaStruct RdM Pro » : même forme que le site (bandeau, menu en haut, une page par outil).

Lancement : python main.py (ou 1_Ouvrir_application.bat sous Windows).
"""

import importlib
import os
import sys
import traceback

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401 : à importer avant QApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mecastruct.bureau import state, theme, widgets

URL_EN_LIGNE = "https://theo33-oss.github.io/MecaStruct/"  # la version en ligne, toujours à jour

# (identifiant = module de pages, libellé, classe) ; libellé seul = titre de groupe
MENU = (  # les 5 familles du site (docs/app.js, FAMILLES), mêmes noms de pages
    ("accueil", "Accueil", "PageAccueil"),
    ("Structures", None, None),
    ("poutres", "Poutres", "PagePoutres"),
    ("treillis", "Treillis", "PageTreillis"),
    ("flambage", "Flambage", "PageFlambage"),
    ("Sections et contraintes", None, None),
    ("sections", "Sections", "PageSections"),
    ("sollicitations", "Sollicitations", "PageSollicitations"),
    ("tenseurs", "Tenseurs et critères", "PageTenseurs"),
    ("hooke_jauges", "Hooke et jauges", "PageHookeJauges"),
    ("Liaisons et guidages", None, None),
    ("ajustements", "Ajustements ISO 286", "PageAjustements"),
    ("frettage", "Frettage", "PageFrettage"),
    ("paliers_lisses", "Paliers lisses", "PagePaliersLisses"),
    ("roulements", "Roulements", "PageRoulements"),
    ("Transmission", None, None),
    ("engrenages", "Engrenages", "PageEngrenages"),
    ("epicycloidaux", "Trains épicycloïdaux", "PageEpicycloidaux"),
    ("freins_embrayages", "Freins et embrayages", "PageFreinsEmbrayages"),
    ("dimensionnement_moteur", "Dimensionnement moteur", "PageDimensionnementMoteur"),
    ("Données et aide", None, None),
    ("base_de_donnees", "Matériaux et profilés", "PageBaseDeDonnees"),
    ("convertisseur", "Convertisseur", "PageConvertisseur"),
    ("references", "Références", "PageReferences"),
    ("apropos", "À propos", "PageAPropos"),
)


class Fenetre(QMainWindow):
    """Fenêtre principale : bandeau, menu en haut (familles, puis pages), pages empilées bâties à leur première ouverture."""

    def __init__(self) -> None:
        super().__init__()
        from mecastruct import __version__

        self.setWindowTitle(f"MecaStruct RdM Pro {__version__}")
        self.resize(1500, 900)
        self.familles: dict[str, list[tuple[str, str]]] = {}  # famille → [(page, libellé)]
        self.famille_de: dict[str, str] = {}
        self.pages: dict[str, tuple[int, widgets.Page | None]] = {}
        self.rangs: dict[int, str] = {}
        self.menu = QListWidget()  # modèle des pages, non affiché : l'ordre et la page ouverte (les boutons le pilotent)
        groupe = None
        for ident, libelle, _classe in MENU:
            if libelle is None:  # titre de famille
                groupe = ident
                self.familles[groupe] = []
                it = QListWidgetItem(ident.upper())
                it.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                it = QListWidgetItem("   " + libelle)
                self.pages[ident] = (self.menu.count(), None)
                self.rangs[self.menu.count()] = ident
                if groupe is not None:
                    self.familles[groupe].append((ident, libelle))
                    self.famille_de[ident] = groupe
            self.menu.addItem(it)
        centre = QWidget()
        colonne = QVBoxLayout(centre)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addWidget(self._bandeau())
        colonne.addWidget(self._barre())
        self.pile = QStackedWidget()
        colonne.addWidget(self.pile, 1)
        self.setCentralWidget(centre)
        self.menu.currentRowChanged.connect(self._ouvrir)
        self.aller("accueil")

    # ---------------------------------------------------------------------------------------------- bandeau et menu

    def _bandeau(self) -> QWidget:
        """Marque, phrase de confiance, contraste, thème et bouton vers la version en ligne (comme le haut du site)."""
        from pathlib import Path

        from PySide6.QtGui import QIcon

        bandeau = QWidget()
        bandeau.setObjectName("bandeau")
        h = QHBoxLayout(bandeau)
        h.setContentsMargins(18, 10, 18, 8)
        h.setSpacing(16)
        icone = QLabel()
        icone.setPixmap(QIcon(str(Path(__file__).resolve().parent / "data" / "icone.svg")).pixmap(36, 36))
        marque = QLabel("MecaStruct <span style='font-weight:normal'>RdM Pro</span>")
        marque.setObjectName("marque")
        confiance = QLabel("Tout est calculé sur votre ordinateur : rien n'est envoyé sur Internet. "
                           "Outil d'aide au pré-dimensionnement, résultats à vérifier.")  # fmt: skip
        confiance.setObjectName("confiance")
        confiance.setWordWrap(True)
        confiance.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.contraste = QCheckBox("Contraste élevé")
        self.contraste.setToolTip(
            "Graphiques plus lisibles : traits plus épais, aires plus colorées, quadrillage et textes plus marqués."
        )
        self.contraste.setChecked(bool(state.v.get("contraste")))
        self.contraste.toggled.connect(self._contraste)
        self.bouton_theme = QPushButton()
        self.bouton_theme.setObjectName("bouton")
        self.bouton_theme.clicked.connect(self.changer_theme)
        en_ligne = QPushButton("Version en ligne")
        en_ligne.setObjectName("primaire")
        en_ligne.setToolTip("Ouvre la version dans le navigateur : sans installation, toujours à jour.")
        en_ligne.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_EN_LIGNE)))
        for w in (icone, marque):
            h.addWidget(w)
        h.addWidget(confiance, 1)
        for w in (self.contraste, self.bouton_theme, en_ligne):
            h.addWidget(w)
        self._texte_theme()
        return bandeau

    def _barre(self) -> QWidget:
        """Barre du haut : Accueil et les familles, puis les pages de la famille choisie."""
        barre = QFrame()
        barre.setObjectName("barreMenu")
        v = QVBoxLayout(barre)
        v.setContentsMargins(18, 4, 18, 6)
        v.setSpacing(2)
        haut = QHBoxLayout()
        haut.setSpacing(6)
        self.boutons_familles: dict[str | None, QPushButton] = {}
        accueil = self._bouton_menu("Accueil", "famille", lambda: self.aller("accueil"))
        self.boutons_familles[None] = accueil
        haut.addWidget(accueil)
        self.sous = QStackedWidget()
        self.rang_famille: dict[str, int] = {}
        self.boutons_pages: dict[str, QPushButton] = {}
        for nom, pages in self.familles.items():
            b = self._bouton_menu(nom, "famille", lambda _=False, p=pages[0][0]: self.aller(p))
            self.boutons_familles[nom] = b
            haut.addWidget(b)
            rangee = QWidget()
            r = QHBoxLayout(rangee)
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(6)
            for ident, libelle in pages:
                p = self._bouton_menu(libelle, "sousmenu", lambda _=False, i=ident: self.aller(i))
                self.boutons_pages[ident] = p
                r.addWidget(p)
            r.addStretch(1)
            self.rang_famille[nom] = self.sous.addWidget(rangee)
        haut.addStretch(1)
        v.addLayout(haut)
        v.addWidget(self.sous)
        return barre

    @staticmethod
    def _bouton_menu(texte: str, nom: str, action) -> QPushButton:
        b = QPushButton(texte)
        b.setObjectName(nom)
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(action)
        return b

    def _maj_barre(self, ident: str) -> None:
        """Marque la famille et la page ouvertes ; la rangée des pages n'existe que pour une famille."""
        famille = self.famille_de.get(ident)
        for nom, b in self.boutons_familles.items():
            b.setChecked(nom == famille)
        for i, b in self.boutons_pages.items():
            b.setChecked(i == ident)
        self.sous.setVisible(famille is not None)
        if famille is not None:
            self.sous.setCurrentIndex(self.rang_famille[famille])

    # --------------------------------------------------------------------------------------------------- thème

    def _texte_theme(self) -> None:
        self.bouton_theme.setText("Thème clair" if theme.sombre() else "Thème sombre")

    def changer_theme(self) -> None:
        """Bascule clair / sombre, garde le choix, puis reconstruit les pages (elles lisent la palette à leur création)."""
        nom = "clair" if theme.sombre() else "sombre"
        widgets.appliquerTheme(QApplication.instance(), nom)
        QSettings("MecaStruct", "RdM Pro").setValue("theme", nom)
        self._texte_theme()
        courante = self.rangs.get(self.menu.currentRow())
        for ident, (rang, page) in list(self.pages.items()):
            if page is not None:
                self.pile.removeWidget(page)
                page.deleteLater()
                self.pages[ident] = (rang, None)
        if courante:
            self.aller(courante)

    def _contraste(self, actif: bool) -> None:
        state.v["contraste"] = actif
        ident = self.rangs.get(self.menu.currentRow())
        if ident and self.pages[ident][1] is not None:
            self.pages[ident][1].afficher()

    def page(self, ident: str) -> widgets.Page:
        """Page `ident`, créée à sa première demande."""
        rang, page = self.pages[ident]
        if page is None:
            classe = next(c for i, _, c in MENU if i == ident)
            page = getattr(importlib.import_module(f"mecastruct.bureau.pages.{ident}"), classe)(self)
            self.pile.addWidget(page)
            self.pages[ident] = (rang, page)
        return page

    def _ouvrir(self, ligne: int) -> None:
        ident = self.rangs.get(ligne)
        if ident:
            page = self.page(ident)
            self.pile.setCurrentWidget(page)
            self._maj_barre(ident)
            page.afficher()

    def aller(self, ident: str) -> None:
        """Ouvre une page par son identifiant ; la rouvre si elle est déjà affichée (son état a pu changer)."""
        rang, _ = self.pages[ident]
        if self.menu.currentRow() == rang:
            self.pile.setCurrentWidget(self.page(ident))
            self._maj_barre(ident)
            self.page(ident).afficher()
        else:
            self.menu.setCurrentRow(rang)


def _signalerErreur(genre: type, erreur: BaseException, trace: object) -> None:
    """Sans console (pythonw), une erreur inattendue serait muette : elle s'affiche à l'écran."""
    detail = "".join(traceback.format_exception(genre, erreur, trace))
    QMessageBox.critical(None, "Erreur de l'application", f"{erreur}\n\n{detail[-1500:]}")


def verifier(app: QApplication, fenetre: "Fenetre", sortie: str) -> int:
    """Auto-vérification (main.py --verifier fichier.txt) : ouvre et calcule chaque page, écrit les erreurs, quitte.

    Sert à contrôler l'application empaquetée (modules ou données oubliés), en local et sur GitHub.
    """
    from PySide6.QtCore import QTimer

    from mecastruct.bureau import tache

    erreurs: list[str] = []
    sys.excepthook = lambda g, e, t: erreurs.append("".join(traceback.format_exception(g, e, t))[-1500:])

    def pause(ms: int) -> None:
        fin: list[int] = []
        QTimer.singleShot(ms, lambda: fin.append(1))
        while not fin:
            app.processEvents()

    lignes = []
    for ident, libelle, _ in MENU:
        if libelle is None:
            continue
        avant = len(erreurs)
        try:
            fenetre.aller(ident)
            pause(300)
            p = fenetre.page(ident)
            for k, c in enumerate(getattr(p, "pages", [p])):
                if hasattr(p, "onglets"):
                    p.onglets.setCurrentIndex(k)
                    pause(200)
                if hasattr(c, "calculer"):
                    c.calculer()
                    while tache.occupe():
                        app.processEvents()
                    pause(600)
        except Exception:  # noqa: BLE001 : toute erreur est notée, la vérification continue
            erreurs.append(traceback.format_exc()[-1500:])
        lignes.append(f"{ident} : {'OK' if len(erreurs) == avant else 'ERREUR'}")
    try:  # bloc-notes et Excel de validation de chaque page : pont, openpyxl, jinja2 dans l'application empaquetée
        from mecastruct.bureau import exports
        from mecastruct.pont import noyau

        noyau.utiliser(state.dm())
        noyau.charger("structures")
        formulaires = noyau.tous_formulaires()
        n = 0
        for ident in sorted(formulaires):
            if formulaires[ident].get("exports"):
                s = formulaires[ident]["defaut"]
                assert exports.appel(f"{ident}.texte", s)["texte"].startswith("\ufeff")
                assert exports.appel(f"{ident}.validation", s)["base64"][:4] == "UEsD"  # « PK » : un .xlsx est un zip
                n += 1
        lignes.append(f"bloc-notes et Excel de validation ({n} calculs) : OK")
    except Exception:  # noqa: BLE001
        erreurs.append(traceback.format_exc()[-1500:])
        lignes.append("bloc-notes et Excel de validation : ERREUR")
    try:  # dossiers PDF et Word : polices, matplotlib (formules), reportlab, python-docx
        from mecastruct.services import dossier_export

        html = "<h1>Essai</h1><h2>Formules</h2><p>Contrainte $\\sigma = \\frac{N}{S} = 12.5$ MPa</p>"
        pdf, docx = dossier_export.export(html, "PDF"), dossier_export.export(html, "Word")
        lignes.append(f"dossier PDF et Word : {'OK' if pdf[:4] == b'%PDF' and docx[:2] == b'PK' else 'ERREUR'}")
    except Exception:  # noqa: BLE001
        erreurs.append(traceback.format_exc()[-1500:])
        lignes.append("dossier PDF et Word : ERREUR")
    with open(sortie, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n\n" + "\n\n".join(erreurs))
    return 1 if erreurs else 0


def captures(app: QApplication, fenetre: "Fenetre", dossier: str) -> int:
    """Audit : ouvre et calcule chaque page et chaque onglet, enregistre une image de la fenêtre (main.py --captures dossier)."""
    from pathlib import Path

    from PySide6.QtCore import QTimer

    from mecastruct.bureau import tache

    sortie = Path(dossier)
    sortie.mkdir(parents=True, exist_ok=True)
    fenetre.resize(1500, 950)

    def pause(ms: int) -> None:
        fin: list[int] = []
        QTimer.singleShot(ms, lambda: fin.append(1))
        while not fin:
            app.processEvents()

    n = 0
    for ident, libelle, _ in MENU:
        if libelle is None:
            continue
        fenetre.aller(ident)
        pause(500)
        p = fenetre.page(ident)
        for k, c in enumerate(getattr(p, "pages", [p])):
            if hasattr(p, "onglets"):
                p.onglets.setCurrentIndex(k)
                pause(300)
            if hasattr(c, "calculer"):
                c.calculer()
                while tache.occupe():
                    app.processEvents()
                pause(3500)
            fenetre.grab().save(str(sortie / f"{ident}_{k}.png"))
            n += 1
    print(f"{n} captures dans {sortie}")
    return 0


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    sys.excepthook = _signalerErreur
    state.init()
    # thème : celui de la dernière fois ; MECASTRUCT_THEME=sombre|clair le force (audits par captures)
    widgets.appliquerTheme(app, os.environ.get("MECASTRUCT_THEME") or str(QSettings("MecaStruct", "RdM Pro").value("theme", "clair")))
    from pathlib import Path

    from PySide6.QtGui import QIcon

    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / "data" / "icone.svg")))
    fenetre = Fenetre()
    fenetre.show()
    if "--verifier" in sys.argv:
        return verifier(app, fenetre, sys.argv[sys.argv.index("--verifier") + 1])
    if "--captures" in sys.argv:
        return captures(app, fenetre, sys.argv[sys.argv.index("--captures") + 1])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

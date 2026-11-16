"""Application de bureau « MecaStruct RdM Pro » : menu à gauche, une page par outil.

Lancement : python main.py (ou 1_Ouvrir_application.bat sous Windows).
"""

import importlib
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401 : à importer avant QApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mecastruct.bureau import state, widgets

# (identifiant = module de pages, libellé, classe) ; libellé seul = titre de groupe
MENU = (
    ("accueil", "Accueil", "PageAccueil"),
    ("Calcul", None, None),
    ("poutres", "Poutres", "PagePoutres"),
    ("treillis", "Treillis", "PageTreillis"),
    ("sections", "Sections", "PageSections"),
    ("sollicitations", "Sollicitations", "PageSollicitations"),
    ("flambage", "Flambage", "PageFlambage"),
    ("tenseurs", "Tenseurs & critères", "PageTenseurs"),
    ("hooke_jauges", "Hooke & jauges", "PageHookeJauges"),
    ("Éléments de machines", None, None),
    ("ajustements", "Ajustements ISO 286", "PageAjustements"),
    ("frettage", "Frettage", "PageFrettage"),
    ("paliers_lisses", "Paliers lisses", "PagePaliersLisses"),
    ("roulements", "Roulements", "PageRoulements"),
    ("engrenages", "Engrenages", "PageEngrenages"),
    ("epicycloidaux", "Trains épicycloïdaux", "PageEpicycloidaux"),
    ("freins_embrayages", "Freins et embrayages", "PageFreinsEmbrayages"),
    ("dimensionnement_moteur", "Dimensionnement moteur", "PageDimensionnementMoteur"),
    ("Outils", None, None),
    ("base_de_donnees", "Base de données", "PageBaseDeDonnees"),
    ("convertisseur", "Convertisseur", "PageConvertisseur"),
    ("references", "Références", "PageReferences"),
    ("Informations", None, None),
    ("apropos", "À propos", "PageAPropos"),
)


class Fenetre(QMainWindow):
    """Fenêtre principale : menu et pages empilées, chaque page étant bâtie à sa première ouverture."""

    def __init__(self) -> None:
        super().__init__()
        from mecastruct import __version__

        self.setWindowTitle(f"MecaStruct RdM Pro {__version__}")
        self.resize(1500, 900)
        centre = QWidget()
        h = QHBoxLayout(centre)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        gauche = QWidget()
        gauche.setObjectName("menu")
        colonne = QVBoxLayout(gauche)
        colonne.setContentsMargins(0, 0, 0, 6)
        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        gauche.setFixedWidth(235)
        colonne.addWidget(self.menu, 1)
        contraste = QCheckBox("Contraste élevé (graphiques)")
        contraste.setToolTip(
            "Graphiques plus lisibles : traits plus épais, aires plus colorées, quadrillage et textes plus marqués."
        )
        contraste.setStyleSheet("color:#F4F2FA; background:transparent; margin-left:8px;")
        contraste.setChecked(bool(state.v.get("contraste")))
        contraste.toggled.connect(self._contraste)
        colonne.addWidget(contraste)
        self.pile = QStackedWidget()
        self.pages: dict[str, tuple[int, widgets.Page | None]] = {}
        self.rangs: dict[int, str] = {}
        for ident, libelle, _classe in MENU:
            if libelle is None:  # titre de groupe
                it = QListWidgetItem(ident.upper())
                it.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                it = QListWidgetItem("   " + libelle)
                self.pages[ident] = (self.menu.count(), None)
                self.rangs[self.menu.count()] = ident
            self.menu.addItem(it)
        h.addWidget(gauche)
        h.addWidget(self.pile, 1)
        self.setCentralWidget(centre)
        self.menu.currentRowChanged.connect(self._ouvrir)
        self.aller("accueil")

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
            page.afficher()

    def aller(self, ident: str) -> None:
        """Ouvre une page par son identifiant ; la rouvre si elle est déjà affichée (son état a pu changer)."""
        rang, _ = self.pages[ident]
        if self.menu.currentRow() == rang:
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
    widgets.appliquerTheme(app)
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

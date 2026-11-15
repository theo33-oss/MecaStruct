"""Capture d'écran d'une page de la fenêtre : python tools/capture.py page[:sous-onglet] [--calcul] -> captures/page.png."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mecastruct.bureau import state, tache, widgets  # noqa: E402


def attendre(app: QApplication, ms: int) -> None:
    fin = []
    QTimer.singleShot(ms, lambda: fin.append(1))
    while not fin:
        app.processEvents()


def main_capture() -> None:
    idents = [a for a in sys.argv[1:] if not a.startswith("--")]
    calcul = "--calcul" in sys.argv
    app = QApplication([])
    widgets.appliquerTheme(app)
    state.init()
    f = main.Fenetre()
    f.resize(1500, 900)
    f.show()
    dossier = Path(__file__).resolve().parent.parent / "captures"
    dossier.mkdir(exist_ok=True)
    for arg in idents:
        ident, _, rang = arg.partition(":")  # « sollicitations:1 » : deuxième sous-onglet
        f.aller(ident)
        attendre(app, 800)
        cible = f.page(ident)
        if rang:
            cible.onglets.setCurrentIndex(int(rang))
            attendre(app, 500)
            cible = cible.pages[int(rang)]
        if calcul and hasattr(cible, "calculer"):
            cible.calculer()
            while tache.occupe():
                app.processEvents()
            attendre(app, 2500)
        f.grab().save(str(dossier / f"{ident}{('_' + rang) if rang else ''}{'_calcul' if calcul else ''}.png"))


if __name__ == "__main__":
    main_capture()

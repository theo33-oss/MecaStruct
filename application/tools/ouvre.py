"""Ouvre les pages données, les calcule, et signale toute exception (diagnostic de développement)."""
import sys, traceback
sys.path.insert(0, ".")
import main
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from mecastruct.bureau import state, tache, widgets
app = QApplication([]); widgets.appliquerTheme(app); state.init()
erreurs = []
sys.excepthook = lambda g, e, t: erreurs.append("".join(traceback.format_exception(g, e, t)))
f = main.Fenetre(); f.resize(1500, 900); f.show()
def pause(ms):
    fin = []; QTimer.singleShot(ms, lambda: fin.append(1))
    while not fin: app.processEvents()
for ident in sys.argv[1:]:
    f.aller(ident); pause(400)
    p = f.page(ident)
    cibles = getattr(p, "pages", [p])
    for k, c in enumerate(cibles):
        if hasattr(p, "onglets"):
            p.onglets.setCurrentIndex(k); pause(300)
        if hasattr(c, "calculer"):
            c.calculer()
            while tache.occupe(): app.processEvents()
            pause(1500)
    print(ident, "OK" if not erreurs else "ERREURS")
    for e in erreurs: print(e[-1800:])
    erreurs.clear()

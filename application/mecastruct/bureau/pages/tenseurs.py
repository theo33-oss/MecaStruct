"""Page « Tenseurs et critères » : contraintes principales, facette, cercles de Mohr, critères, lieux de plasticité.

Port de l'onglet « Tenseurs & Critères » de MecaStruct_App.m (buildTensorTab, computeTensor, symmetrize). La page reçoit
aussi l'état de contrainte envoyé par la page Poutres (« Envoyer au tenseur »).
"""

import copy

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QTableWidget, QTableWidgetItem

from mecastruct.bureau import dossier, state
from mecastruct.bureau.page_calcul import PageCalcul, modes_resultat
from mecastruct.bureau.widgets import Zone, ajusterHauteur, differer, formatNombre, lireNombre
from mecastruct.plots import other_plots
from mecastruct.services import compute, sources

AXES = ["x", "y", "z"]
FACETTES = {"theta": "Angle θ dans le plan (x, y)", "n": "Normale n (nx, ny, nz)"}


class GrilleTenseur(QTableWidget):
    """Tenseur 3×3 éditable ; une cellule modifiée est recopiée en position symétrique (σij = σji)."""

    def __init__(self, surChange) -> None:
        super().__init__(3, 3)
        self.surChange = surChange
        self.setHorizontalHeaderLabels(AXES)
        self.setVerticalHeaderLabels(AXES)
        self.charger()
        self.itemChanged.connect(self._change)

    def charger(self) -> None:
        self.blockSignals(True)
        sig = state.saisie("Ten")["sig"]
        for i in range(3):
            for j in range(3):
                it = QTableWidgetItem(formatNombre(float(sig[i][j])))
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(i, j, it)
        self.blockSignals(False)
        self.resizeColumnsToContents()
        ajusterHauteur(self)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def _change(self, item: QTableWidgetItem) -> None:
        try:
            v = lireNombre(item.text())
        except ValueError:
            v = None
        i, j = item.row(), item.column()
        if v is not None:
            state.saisie("Ten")["sig"] = compute.symmetrize(state.saisie("Ten")["sig"], {i: {AXES[j]: v}})
        self.charger()  # la cellule symétrique est mise à jour, une saisie illisible reprend sa valeur
        differer(self.surChange)


class PageTenseurs(PageCalcul):
    titre = "Tenseurs et critères"
    fiche = "tenseurs"
    tab = "Ten"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Ten")), state.dm()
        self.calcule_onglet("Ten", lambda: compute.computeTensor(s, dm))

    def saisie(self, z: Zone) -> None:
        dm = state.dm()
        z.legende(sources.source("ten"))

        def tenseur(c: Zone) -> None:
            c._ajouter(GrilleTenseur(self.surSaisie))
            c.legende("La saisie est symétrisée automatiquement (σij = σji).")

        def facette(c: Zone) -> None:
            mode = c.choice("Ten", "fmode", "Définition", list(FACETTES), format_func=FACETTES.get,
                            on_change=self.rafraichirSaisie)  # fmt: skip
            c.num("Ten", "theta", "θ", "°", actif=mode == "theta")
            for n in ("nx", "ny", "nz"):
                c.num("Ten", n, n, "-", actif=mode == "n")

        def criteres(c: Zone) -> None:
            c.choice_materiau("Ten", ["Re", "Rm"], dm)
            c.num("Ten", "Re", "Re = σe", "MPa")
            c.num("Ten", "Rm", "σR (fragiles : Rm)", "MPa")
            c.num("Ten", "s", "Coefficient de sécurité s", "-")

        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Ten")
        dossier.file_bar(z, "Ten")
        dossier.example_picker(z, "Ten")
        z.repliable("Tenseur des contraintes σ (MPa)", ouvert=True, rendu=tenseur, cle="Ten.sigma")
        z.repliable("Facette", ouvert=True, rendu=facette, cle="Ten.facette")
        z.repliable("Critères", ouvert=True, rendu=criteres, cle="Ten.criteres")

    def _point_critere(self, r: dict) -> list[float]:
        """Point tracé sur le lieu de plasticité : (σ1, σ2) en état plan, sinon (σI − σII, σIII − σII), en Pa."""
        pr = r["principal"]
        sig = np.array(state.saisie("Ten")["sig"], dtype=float)
        if np.all(np.abs(sig[2, :]) <= 1e-12 * max(1.0, np.max(np.abs(sig)))):
            return [r["plane2D"]["sigma1"], r["plane2D"]["sigma2"]]
        return [pr["sigmaI"] - pr["sigmaII"], pr["sigmaIII"] - pr["sigmaII"]]

    def _resultats(self, z: Zone, res: dict) -> None:
        r, t = res["result"], res["tables"]
        fa = r["facet"]
        z.graphs(
            "Ten_graphes_onglets",
            [
                ("Tricercle de Mohr", lambda c: c.plot(other_plots.mohr3D(r["mohr3D"], [fa["sigmaN"], fa["tauNorm"]]))),
                ("Mohr 2D (plan x, y)", lambda c: c.plot(other_plots.mohr2D(r["plane2D"], r["plane2D"]["theta"]))),
                ("Lieu de plasticité", lambda c: c.plot(other_plots.yieldLocus(r["loci"], self._point_critere(r)))),
            ],
        )

        def formules(c: Zone) -> None:
            for cle in ("principal", "facet", "plane2D", "mohr3D", "criteria", "loci"):
                c.formules(r[cle]["latex"])

        z.onglets(
            {
                "Principales": lambda c: c.tableau(t["Principales"]),
                "Critères": lambda c: c.tableau(t["Critères"]),
                "Facette": lambda c: c.tableau(t["Facette"]),
                "Rapport": lambda c: c.rapport(r["rapport"]),
                "Formules": formules,
            }
        )

    def visualisation(self, z: Zone) -> None:
        res = state.result("Ten")
        if res is not None:
            c = res["result"]["criteria"]
            modes_resultat(z, "Ten", res, ok=bool(c["okTresca"] and c["okVM"]))
        dossier.validation_button(z, "Ten")
        dossier.explanation_panel(z, "Ten")
        if state.result("Ten") is not None:
            self._resultats(z, state.result("Ten"))

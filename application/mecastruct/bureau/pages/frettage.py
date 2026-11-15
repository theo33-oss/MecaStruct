"""Page « Frettage » : liaison arbre / moyeu serrée, choix de l'ajustement normalisé et température de chauffe.

Port du classeur « Calculs de frettage normalises.xlsm » de l'auteur (NF E22-620).
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau import state
from mecastruct.bureau.machine_page import PageMachine
from mecastruct.bureau.widgets import Zone
from mecastruct.core import fits, shrink_fit
from mecastruct.services import machine


class PageFrettage(PageMachine):
    titre = "Frettage"
    P = "fre"
    DEFAUT = machine.defaultShrinkInput()

    def travail(self, s: dict) -> dict:
        return machine.computeShrinkFit(s, state.dm())

    def _norme(self) -> None:
        """Qualités, lissage et jeu de montage conseillés par la norme pour le diamètre saisi (bouton)."""
        P = self.P
        n = shrink_fit.normValues(state.v[f"{P}.d"])
        state.v[f"{P}.horsTable"] = n is None
        if n is not None:
            state.v[f"{P}.qa"], state.v[f"{P}.qm"] = int(n["qualiteArbre"]), int(n["qualiteMoyeu"])
            state.v[f"{P}.lissage"], state.v[f"{P}.jeu"] = n["lissage"], n["jeu"]
        self.rafraichirSaisie()

    def champs(self, z: Zone) -> None:
        P = self.P

        def efforts(c: Zone) -> None:
            mp.num(c, P, "C", "Couple C", "N·m", min_value=0.0)
            mp.num(c, P, "Fa", "Effort axial Fa", "N", min_value=0.0)
            mp.num(c, P, "f", "Coefficient d'adhérence f", min_value=0.01)
            mp.num(c, P, "s", "Coefficient de sécurité sur l'effort", min_value=1.0)

        def geometrie(c: Zone) -> None:
            mp.num(c, P, "d", "Diamètre frettée d", "mm", min_value=0.0)
            mp.num(c, P, "di", "Diamètre intérieur de l'arbre (0 = plein)", "mm", min_value=0.0)
            mp.num(c, P, "D", "Diamètre extérieur du moyeu D", "mm", min_value=0.0)
            mp.num(c, P, "L", "Longueur frettée L", "mm", min_value=0.0)

        def materiaux(c: Zone) -> None:
            noms = state.dm().listMaterials()
            c.liste("Matériau de l'arbre", noms, f"{P}.matArbre")
            c.liste("Matériau du moyeu", noms, f"{P}.matMoyeu")

        def tolerances(c: Zone) -> None:
            c1, c2 = c.colonnes(2)
            c1.liste("Qualité arbre", fits.QUALITES, f"{P}.qa")
            c2.liste("Qualité moyeu (H)", fits.QUALITES, f"{P}.qm")
            mp.num(c, P, "lissage", "Lissage (perte de serrage)", "µm", min_value=0.0)
            mp.num(c, P, "jeu", "Jeu de montage à chaud", "mm", min_value=0.0)
            c.bouton("Valeurs conseillées par la norme pour ce diamètre", self._norme)
            if state.v.get(f"{P}.horsTable"):
                c.avertissement("Diamètre hors table : saisir les valeurs.")

        z.repliable("Efforts à transmettre", ouvert=True, rendu=efforts, cle="efforts")
        z.repliable("Géométrie", ouvert=True, rendu=geometrie, cle="geometrie")
        z.repliable("Matériaux", ouvert=True, rendu=materiaux, cle="materiaux")
        z.repliable("Tolérances et montage", ouvert=True, rendu=tolerances, cle="tolerances")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Alésage normal H. L'arbre retenu est le moins serré dont l'écart inférieur couvre le serrage utile + le "
            "lissage. Contraintes : Lamé, arbre 2p/(1 − (di/d)²), moyeu Von Mises à l'alésage."
        )

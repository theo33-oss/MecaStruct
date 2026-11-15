"""Page « Paliers lisses » : vérification P, V, PV d'un coussinet (et de sa collerette) sur le diagramme P-V.

Port du classeur « CALCULS PALIERS LISSES.xlsm » de l'auteur, sans catalogue de fabricant : on vérifie les
dimensions saisies.
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau.machine_page import PageMachine
from mecastruct.bureau.widgets import Zone
from mecastruct.core import plain_bearing
from mecastruct.plots import machine_plots
from mecastruct.services import machine


class PagePaliersLisses(PageMachine):
    titre = "Paliers lisses"
    P = "pal"
    DEFAUT = machine.defaultBearingInput()

    def travail(self, s: dict) -> dict:
        return machine.computeBearing(s)

    def champs(self, z: Zone) -> None:
        P = self.P

        def charges(c: Zone) -> None:
            mp.num(c, P, "Fr", "Force radiale Fr", "N", min_value=0.0)
            mp.num(c, P, "Fa", "Force axiale Fa (collerette)", "N", min_value=0.0)
            mp.num(c, P, "n", "Fréquence de rotation", "tr/min", min_value=0.0)
            c.legende("Oscillation (remplace la rotation si les deux champs sont renseignés) :")
            mp.num(c, P, "osc", "Fréquence d'oscillation", "oscillations/min", min_value=0.0)
            mp.num(c, P, "beta", "Demi-amplitude β", "°", min_value=0.0)

        def coussinet(c: Zone) -> None:
            c.liste("Matériau", [m["Name"] for m in plain_bearing.materials()], f"{P}.materiau")
            mp.num(c, P, "d", "Alésage d (diamètre de l'arbre)", "mm", min_value=0.0)
            mp.num(c, P, "L", "Longueur L", "mm", min_value=0.0)
            mp.num(c, P, "Dfl", "Diamètre de collerette (0 = sans)", "mm", min_value=0.0)

        z.repliable("Charges et mouvement", ouvert=True, rendu=charges, cle="charges")
        z.repliable("Coussinet", ouvert=True, rendu=coussinet, cle="coussinet")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Limites P, V et courbe P-V : ordres de grandeur par famille de matériau, à confirmer sur la documentation "
            "du fabricant du coussinet."
        )

    def graphique(self, s: dict):
        return machine_plots.pvDiagram

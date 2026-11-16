"""Page « Ajustements » : écarts normalisés ISO 286 d'un alésage et d'un arbre, jeu ou serrage.

Port du classeur « ecarts-normalises.xlsm » de l'auteur (tables dans data/iso286.json).
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau.machine_page import PageMachine
from mecastruct.bureau.widgets import Zone
from mecastruct.core import fits
from mecastruct.plots import machine_plots
from mecastruct.services import machine


class PageAjustements(PageMachine):
    titre = "Ajustements ISO 286"
    P = "aju"
    DEFAUT = machine.defaultFitInput()

    def travail(self, s: dict) -> dict:
        return machine.computeFit(s)

    def champs(self, z: Zone) -> None:
        P = self.P
        mp.num(z, P, "d", "Diamètre nominal", "mm", min_value=0.0, max_value=3150.0)
        c1, c2 = z.colonnes(2)
        c1.liste("Alésage", fits.LETTRES_ALESAGE, f"{P}.alesage")
        c2.liste("Qualité alésage", fits.QUALITES, f"{P}.qa")
        c1.liste("Arbre", fits.LETTRES_ARBRE, f"{P}.arbre")
        c2.liste("Qualité arbre", fits.QUALITES, f"{P}.qb")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Tables de l'ISO 286-1/-2 (jusqu'à 3150 mm). Correction Δ appliquée à K, M, N (qualités ≤ 8) et P à ZC "
            "(≤ 7). Jeu négatif = serrage. Usuels : H7/g6 glissant, H7/h6 glissant juste, H7/k6 incertain, H7/p6 serré."
        )

    def graphique(self, s: dict):
        return lambda r: machine_plots.fitZones(r, f"{s['alesage']}{s['qa']}", f"{s['arbre']}{s['qb']}")

"""Page « Trains épicycloïdaux » : raison basique, vitesses des trois éléments par la formule de Willis, montage.

Méthode du cours « Trains épicycloïdaux » (IUT de Bordeaux) : bloquer le porte-satellites pour la raison basique,
puis composer les vitesses par rapport au bâti.
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau.machine_page import PageMachine
from mecastruct.bureau.widgets import Zone
from mecastruct.core import planetary
from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc


class PageEpicycloidaux(PageMachine):
    titre = "Trains épicycloïdaux"
    P = "epi"
    DEFAUT = mc.defaultPlanetaryInput()
    pied = ("epicycloidaux", "Trains épicycloïdaux", [("epi", "Train épicycloïdal", DEFAUT, "planetary")])

    def travail(self, s: dict) -> dict:
        return mc.computePlanetary(s)

    def champs(self, z: Zone) -> None:
        P = self.P

        def dentures(c: Zone) -> None:
            kw = {"min_value": 1.0, "max_value": 1000.0}
            mp.num(c, P, "Z1", "Planétaire Z1", **kw)
            mp.num(c, P, "Z21", "Satellite engrenant le planétaire Z21", **kw)
            mp.num(c, P, "Z22", "Satellite engrenant la couronne Z22 (= Z21 si satellite simple)", **kw)
            mp.num(c, P, "Z4", "Couronne Z4", **kw)
            mp.num(c, P, "nSat", "Nombre de satellites", min_value=1.0, max_value=24.0)

        def cinematique(c: Zone) -> None:
            c.liste("Élément bloqué", planetary.ELEMENTS, f"{P}.bloque")
            c.liste("Élément d'entrée", planetary.ELEMENTS, f"{P}.entree")
            mp.num(c, P, "Ne", "Fréquence de rotation de l'entrée", "tr/min")

        z.repliable("Dentures", ouvert=True, rendu=dentures, cle="dentures")
        z.repliable("Cinématique", ouvert=True, rendu=cinematique, cle="cinematique")

    def notes(self, z: Zone) -> None:
        z.legende(
            "L'élément restant est la sortie. Montage : entraxes Z4 = Z1 + Z21 + Z22 et règle du haricot, (Z1 + Z4)/n_sat "
            "entier. Les trois éléments doivent être distincts pour le bloqué et l'entrée."
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.planetaryTrain(s))

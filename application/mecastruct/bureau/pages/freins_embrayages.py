"""Page « Freins et embrayages » : couple et pression d'un frein à disque, synchronisation d'un embrayage.

Formules du cours « Frein – Embrayage » (IUT de Bordeaux, ICM S5) : pression de contact constante ou usure constante,
équation du mouvement de l'arbre moteur et de l'arbre récepteur.
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau.machine_page import PageMachine, PageMachineOnglets
from mecastruct.bureau.widgets import Zone
from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc

FRE, EMB = "frn", "emb"
DEFAUT_FRE, DEFAUT_EMB = mc.defaultBrakeInput(), mc.defaultClutchInput()


class Frein(PageMachine):
    P, DEFAUT = FRE, DEFAUT_FRE

    def travail(self, s: dict) -> dict:
        return mc.computeBrake(s)

    def champs(self, z: Zone) -> None:
        def effort(c: Zone) -> None:
            mp.num(c, FRE, "F", "Effort presseur F par surface", "N", min_value=0.0)
            mp.num(c, FRE, "f", "Coefficient de frottement f", min_value=0.0, max_value=1.0)
            mp.num(c, FRE, "n", "Nombre de surfaces frottantes n", min_value=1.0)

        def disque(c: Zone) -> None:
            mp.num(c, FRE, "Ri", "Rayon intérieur Ri", "mm", min_value=0.0)
            mp.num(c, FRE, "Re", "Rayon extérieur Re", "mm", min_value=0.1)

        z.repliable("Effort et garniture", ouvert=True, rendu=effort, cle="effort")
        z.repliable("Géométrie du disque", ouvert=True, rendu=disque, cle="disque")
        mp.num(z, FRE, "N", "Fréquence de rotation du disque au freinage", "tr/min", min_value=0.0)

    def notes(self, z: Zone) -> None:
        z.legende(
            "Couple Cf = n·f·F·(2/3)(Re³ − Ri³)/(Re² − Ri²) en pression constante, ou n·f·F·(Re + Ri)/2 en usure "
            "constante. La puissance spécifique moyenne est à comparer à la limite du fabricant de la garniture."
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.brakeDisc(s))

    def graphique(self, s: dict):
        return lambda _: machine_schemas.brakePressure(s)


class Embrayage(PageMachine):
    P, DEFAUT = EMB, DEFAUT_EMB

    def travail(self, s: dict) -> dict:
        return mc.computeClutch(s)

    def champs(self, z: Zone) -> None:
        def moteur(c: Zone) -> None:
            mp.num(c, EMB, "CM", "Couple moteur CM", "N·m", min_value=0.0)
            mp.num(c, EMB, "NM", "Fréquence de rotation du moteur", "tr/min", min_value=0.0)
            mp.num(c, EMB, "JR", "Inertie du récepteur JR", "kg·m²", min_value=0.0)
            mp.num(c, EMB, "CR", "Couple résistant CR (négatif)", "N·m", max_value=0.0)

        def manoeuvre(c: Zone) -> None:
            mp.num(c, EMB, "ts", "Durée de synchronisation visée", "s", min_value=0.1)
            mp.num(c, EMB, "cadence", "Cadence", "manœuvres/h", min_value=0.0)

        z.repliable("Moteur et récepteur", ouvert=True, rendu=moteur, cle="moteur")
        z.repliable("Manœuvre", ouvert=True, rendu=manoeuvre, cle="manoeuvre")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Pendant la synchronisation le moteur est supposé à vitesse constante : le couple d'embrayage vaut "
            "|CR| + JR·ω/ts. Vérification indicative : ce couple doit rester inférieur au couple moteur."
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.clutchSync(s))


class PageFreinsEmbrayages(PageMachineOnglets):
    titre = "Freins et embrayages"
    sousPages = [("Frein à disque", Frein), ("Embrayage", Embrayage)]
    pied = (
        "freins",
        "Freins et embrayages",
        [(FRE, "Frein à disque", DEFAUT_FRE, "brake"), (EMB, "Embrayage", DEFAUT_EMB, "clutch")],
    )

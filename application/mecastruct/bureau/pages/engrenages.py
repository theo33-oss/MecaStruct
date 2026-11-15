"""Page « Engrenages » : engrènement à denture droite (géométrie, efforts, pied de dent, module) et train en série.

Formules du cours « Les engrenages » (IUT de Bordeaux) : relations géométriques, rapports, puissance et couple,
résistance d'une dent modélisée par une poutre.
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau import state
from mecastruct.bureau.machine_page import PageMachine, PageMachineOnglets
from mecastruct.bureau.widgets import Zone
from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc

P, TRN = "eng", "trn"
DEFAUT, DEFAUT_TRN = mc.defaultGearInput(), mc.defaultGearTrainInput()


class Engrenement(PageMachine):
    P, DEFAUT = P, DEFAUT

    def travail(self, s: dict) -> dict:
        return mc.computeGearMesh(s, state.dm())

    def champs(self, z: Zone) -> None:
        def geometrie(c: Zone) -> None:
            mp.num(c, P, "m", "Module m", "mm", min_value=0.1)
            c1, c2 = c.colonnes(2)
            mp.num(c1, P, "Z1", "Dents du pignon Z1", min_value=1.0, max_value=1000.0)
            mp.num(c2, P, "Z2", "Dents de la roue Z2", min_value=1.0, max_value=1000.0)

        def transmission(c: Zone) -> None:
            mp.num(c, P, "P", "Puissance au pignon P", "W", min_value=0.0)
            mp.num(c, P, "N", "Fréquence de rotation du pignon", "tr/min", min_value=0.1)

        def denture(c: Zone) -> None:
            mp.num(c, P, "k", "Largeur de denture k = b/m", min_value=1.0)
            c.liste("Matériau du pignon", state.dm().listMaterials(), f"{P}.materiau")
            mp.num(c, P, "s", "Coefficient de sécurité sur l'effort s", min_value=1.0)

        z.repliable("Géométrie", ouvert=True, rendu=geometrie, cle="geometrie")
        z.repliable("Transmission", ouvert=True, rendu=transmission, cle="transmission")
        z.repliable("Denture et matériau", ouvert=True, rendu=denture, cle="denture")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Angle de pression 20°, dent à profil normal. Contrainte de flexion en pied de dent (poutre encastrée) "
            "comparée à Rpe = Re/s : Re est la limite élastique du matériau de la base (valeur moyenne à minorer). "
            "Usuellement k entre 6 et 10 et s = 1,5 si l'effort est mal connu."
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.gearMesh(s))


class Train(PageMachine):
    P, DEFAUT = TRN, DEFAUT_TRN

    def travail(self, s: dict) -> dict:
        return mc.computeGearTrain(s)

    def champs(self, z: Zone) -> None:
        def entree(c: Zone) -> None:
            mp.num(c, TRN, "P", "Puissance d'entrée P", "W", min_value=0.0)
            mp.num(c, TRN, "N", "Fréquence de rotation d'entrée", "tr/min", min_value=0.1)
            mp.num(c, TRN, "eta", "Rendement d'un engrènement η", min_value=0.01, max_value=1.0)

        z.repliable("Entrée", ouvert=True, rendu=entree, cle="entree")
        for i in (1, 2, 3):

            def engrenement(c: Zone, i: int = i) -> None:
                c1, c2 = c.colonnes(2)
                mp.num(c1, TRN, f"Z{2 * i - 1}", f"Dents menant Z{2 * i - 1}", min_value=1.0, max_value=1000.0)
                mp.num(c2, TRN, f"Z{2 * i}", f"Dents mené Z{2 * i}", min_value=1.0, max_value=1000.0)

            z.repliable(f"Engrènement {i} (menant Z{2 * i - 1}, mené Z{2 * i})", ouvert=True, rendu=engrenement,
                        cle=f"engrenement{i}")  # fmt: skip

    def notes(self, z: Zone) -> None:
        z.legende(
            "Chaque engrènement extérieur inverse le sens : rapport −Zmenant/Zmené. La puissance diminue de η à chaque "
            "engrènement et le couple se calcule par C = P/ω."
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.gearTrain(s))


class PageEngrenages(PageMachineOnglets):
    titre = "Engrenages"
    sousPages = [("Engrènement", Engrenement), ("Train d'engrenages", Train)]
    pied = (
        "engrenages",
        "Engrenages",
        [(P, "Engrènement", DEFAUT, "gearMesh"), (TRN, "Train d'engrenages", DEFAUT_TRN, "gearTrain")],
    )

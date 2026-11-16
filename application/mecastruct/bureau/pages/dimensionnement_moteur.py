"""Page « Dimensionnement moteur » : couple équivalent thermique d'un cycle, choix du moteur, inertie ramenée.

Méthode du cours « Description et étude des chaînes de transmission de puissance » (IUT de Bordeaux) : couple
quadratique moyen sur les phases d'accélération, de régime établi et de freinage, puis choix du moteur.
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau.machine_page import PageMachine
from mecastruct.bureau.widgets import Zone
from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc


class PageDimensionnementMoteur(PageMachine):
    titre = "Dimensionnement moteur"
    P = "mot"
    DEFAUT = mc.defaultMotorInput()
    pied = ("moteur", "Dimensionnement moteur", [("mot", "Choix du moteur", DEFAUT, "motor")])

    def travail(self, s: dict) -> dict:
        return mc.computeMotor(s)

    def champs(self, z: Zone) -> None:
        P = self.P

        def cycle(c: Zone) -> None:
            mp.num(c, P, "Ca", "Couple en accélération Ca", "N·m")
            mp.num(c, P, "ta", "Durée de l'accélération", "s", min_value=0.0)
            mp.num(c, P, "Cc", "Couple en régime établi Cc", "N·m")
            mp.num(c, P, "tc", "Durée du régime établi", "s", min_value=0.0)
            mp.num(c, P, "Cfr", "Couple au freinage", "N·m")
            mp.num(c, P, "tfr", "Durée du freinage", "s", min_value=0.0)

        def moteur(c: Zone) -> None:
            mp.num(c, P, "Cn", "Couple nominal", "N·m", min_value=0.0)
            mp.num(c, P, "Cmax", "Couple maxi", "N·m", min_value=0.0)
            mp.num(c, P, "Nmax", "Vitesse maxi", "tr/min", min_value=0.0)
            mp.num(c, P, "Nreq", "Vitesse requise par le cahier des charges", "tr/min", min_value=0.0)

        def inertie(c: Zone) -> None:
            mp.num(c, P, "Jm", "Inertie du moteur Jm", "kg·m²", min_value=0.0)
            mp.num(c, P, "Js", "Inertie de la charge ramenée à sa sortie Js", "kg·m²", min_value=0.0)
            mp.num(c, P, "rs", "Rapport de réduction vers la sortie", min_value=0.01)

        z.repliable("Cycle (couple et durée de chaque phase)", ouvert=True, rendu=cycle, cle="cycle")
        z.repliable("Moteur choisi", ouvert=True, rendu=moteur, cle="moteur")
        z.repliable("Inertie ramenée à l'arbre moteur", ouvert=False, rendu=inertie, cle="inertie")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Les durées des phases ne figurent pas dans le cours : les valeurs par défaut retrouvent le couple équivalent "
            "de 61 N·m du cours. Remplacer par les durées de votre cycle. Vitesse requise également à saisir."
        )
        z.repliable(
            "Classification des organes de transmission (cours)",
            rendu=lambda c: c.texte(
                "- **Transformer l'énergie** : moteurs électriques, thermiques, hydrauliques, pneumatiques ; vérins ; "
                "freins.\n"
                "- **Transformer le mouvement** : vis-écrou, bielle-manivelle, came, pignon-crémaillère, tambour ou "
                "poulie.\n"
                "- **Adapter la vitesse ou la puissance** : réducteurs (engrenages, courroie, chaîne), boîtes de "
                "vitesses, embrayages, coupleurs hydrauliques.\n"
                "- **Transporter ou distribuer l'énergie** : arbres, courroies, chaînes, câbles, joints de cardan, "
                "tuyauteries, différentiels."
            ),
            cle="classification",
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.motorCycle(s))

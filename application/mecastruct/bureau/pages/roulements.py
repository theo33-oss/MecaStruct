"""Page « Roulements » : durée de vie L10 et Lnh, charge équivalente, ensembles iso-fiables et règles de montage.

Formules et règles du cours « Calcul sur les roulements » et « Liaison pivot par roulements » (IUT de Bordeaux).
"""

from mecastruct.bureau import machine_page as mp
from mecastruct.bureau.machine_page import PageMachine, PageMachineOnglets
from mecastruct.bureau.widgets import Page, Zone
from mecastruct.core import bearings
from mecastruct.plots import machine_schemas
from mecastruct.services import machine_courses as mc
from mecastruct.services import sources

P, ENS = "rlt", "rlt_ens"
DEFAUT, DEFAUT_ENS = mc.defaultBearingInput(), mc.defaultBearingSetInput()


class DureeDeVie(PageMachine):
    P, DEFAUT = P, DEFAUT

    def travail(self, s: dict) -> dict:
        return mc.computeBearingLife(s)

    def champs(self, z: Zone) -> None:
        def charges(c: Zone) -> None:
            mp.num(c, P, "Fr", "Charge radiale Fr", "N", min_value=0.0)
            mp.num(c, P, "Fa", "Charge axiale Fa", "N", min_value=0.0)
            mp.num(c, P, "N", "Fréquence de rotation", "tr/min", min_value=0.0)

        def roulement(c: Zone) -> None:
            c.liste("Éléments roulants", ["billes", "rouleaux"], f"{P}.type")
            mp.num(c, P, "C", "Charge dynamique de base C", "N", min_value=0.0)
            mp.num(c, P, "C0", "Charge statique de base C0", "N", min_value=0.0)
            c.case("e et Y dans la table du cours (billes à contact radial)", f"{P}.tableau")
            c1, c2, c3 = c.colonnes(3)
            mp.num(c1, P, "e", "e", min_value=0.0)
            mp.num(c2, P, "X", "X", min_value=0.0)
            mp.num(c3, P, "Y", "Y", min_value=0.0)

        def fiabilite(c: Zone) -> None:
            mp.num(c, P, "F", "Fiabilité F", "%", min_value=1.0, max_value=99.9)
            mp.num(c, P, "Lh", "Durée visée Lh", "h", min_value=0.0)

        z.repliable("Charges et vitesse", ouvert=True, rendu=charges, cle="charges")
        z.repliable("Roulement", ouvert=True, rendu=roulement, cle="roulement")
        z.repliable("Fiabilité et durée visée", ouvert=True, rendu=fiabilite, cle="fiabilite")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Table du cours : e, X et Y pour les billes à contact radial, interpolés linéairement en Fa/C0. "
            "Pour les autres roulements, saisir e, X et Y du constructeur. Fa/Fr ≤ e : P = Fr ; sinon P = X·Fr + Y·Fa. "
            "Un roulement de butée ne reçoit que Fa (Fr = 0)."
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.bearingSection(s))

    def graphique(self, s: dict):
        return lambda r: machine_schemas.bearingLife(r, s)


class Ensemble(PageMachine):
    P, DEFAUT = ENS, DEFAUT_ENS

    def travail(self, s: dict) -> dict:
        return mc.computeBearingSet(s)

    def champs(self, z: Zone) -> None:
        def serie(c: Zone) -> None:
            mp.num(c, ENS, "L1", "Durée du roulement 1", "h", min_value=0.0)
            mp.num(c, ENS, "L2", "Durée du roulement 2", "h", min_value=0.0)
            mp.num(c, ENS, "L3", "Durée du roulement 3 (0 = absent)", "h", min_value=0.0)

        def guidage(c: Zone) -> None:
            mp.num(c, ENS, "LG", "Durée du guidage LG", "h", min_value=0.0)
            mp.num(c, ENS, "nG", "Nombre de roulements iso-fiables", min_value=1.0)

        z.repliable("Durées des roulements en série", ouvert=True, rendu=serie, cle="serie")
        z.repliable("Guidage iso-fiable", ouvert=True, rendu=guidage, cle="guidage")

    def notes(self, z: Zone) -> None:
        z.legende(
            "Roulements en série sur un même arbre : (Σ Lj^(−1,5))^(−1/1,5). Roulements iso-fiables : chacun dure "
            "LG × n^(2/3), et l'ensemble dure LG."
        )

    def apercu(self, z: Zone, s: dict) -> None:
        mp.apercu(z, lambda: machine_schemas.bearingSet(s))


class Regles(Page):
    """Règles de montage : bague serrée ou glissante, ajustement conseillé, immobilisation axiale."""

    def rendre(self, z: Zone) -> None:
        z.texte(
            "Règle du cours : la bague **tournante par rapport à la charge** se monte **serrée**, la bague **fixe** par "
            "rapport à la charge se monte **glissante**. On ne fabrique pas les roulements : on impose les tolérances "
            "de l'arbre et de l'alésage."
        )
        bague = z.radio("Bague", ["intérieure", "extérieure"], "rlt_regle.bague")
        rotations = list(dict.fromkeys(r for (b, r, _), _ in bearings.AJUSTEMENTS if b == bague))
        rotation = z.radio("Rotation de la bague par rapport à la direction de la charge", rotations,
                           f"rlt_regle.rotation.{bague}")  # fmt: skip
        charges = [c for (b, r, c), _ in bearings.AJUSTEMENTS if (b, r) == (bague, rotation)]
        charge = z.liste("Charge", charges, f"rlt_regle.charge.{bague}.{rotation}")
        if rotation == "indéfinie" and bague == "intérieure":
            z.succes("Direction de la charge non définie : le cours range la bague intérieure avec la bague tournante, montée serrée.")
        elif rotation == "indéfinie":
            z.info(
                "Direction de la charge non définie : le cours conseille un alésage K7 pour une charge normale "
                "ou importante."
            )
        else:
            z.succes(f"Bague montée {bearings.mountingRule(bague, rotation)}")
        portee, ajustement = bearings.fitRule(bague, rotation, charge)
        z.texte(f"Ajustement conseillé : {portee} {ajustement}")
        z.legende(sources.source("rlt_regle"))
        if bearings.needsLargerClearance(portee, ajustement):
            z.avertissement(bearings.REMARQUE_JEU)
        z.repliable(
            "Immobilisation axiale (solutions du cours)",
            rendu=lambda c: c.texte(
                "- **Bague intérieure** : anneau élastique, épaulement, entretoise (Ø70 H11-d11 en exemple), "
                "écrou à encoche avec rondelle frein.\n"
                "- **Bague extérieure** : épaulement, anneau élastique, chapeau centré (Ø80 H7-h6 en exemple), "
                "entretoise, boîtier de roulement (Ø85 H7-h6 et Ø80 H7-h6), chapeau sur roulement rainuré, "
                "boîtier réglable avec cale."
            ),
        )

    def construire(self) -> None:
        from mecastruct.bureau.widgets import Section, _defilable

        s = Section(self, self.rendre, suit=True)
        self.sections.append(s)
        self.d.addWidget(_defilable(s))


class PageRoulements(PageMachineOnglets):
    titre = "Roulements"
    sousPages = [("Durée de vie", DureeDeVie), ("Ensemble de roulements", Ensemble), ("Règles de montage", Regles)]
    pied = (
        "roulements",
        "Roulements",
        [(P, "Durée de vie", DEFAUT, "bearing"), (ENS, "Ensemble de roulements", DEFAUT_ENS, "bearingSet")],
    )

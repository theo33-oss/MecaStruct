"""Page « Hooke et jauges » : loi de Hooke (4 modes) et extensométrie (jauge, pont de Wheatstone, rosettes).

Port des onglets de MecaStruct_App.m (buildHookeTab, onHookeMode, computeHooke, computeGauges). La fiche de formules
suit le sous-onglet ouvert.
"""

import copy

from mecastruct.bureau import dossier, state
from mecastruct.bureau.page_calcul import PageCalcul, PageOnglets, synthese_resultat
from mecastruct.bureau.widgets import Zone
from mecastruct.plots import other_plots
from mecastruct.services import compute, sources
from mecastruct.services.examples import loadExample

MODES = {
    "iso3D": "Hooke 3D isotrope",
    "planeStress": "Contraintes planes",
    "planeStrain": "Déformations planes",
    "ortho": "Orthotrope (9 constantes)",
}
MONTAGES = {"quart": "Quart de pont", "demi": "Demi-pont", "complet": "Pont complet"}
ROSETTES = {"45": "Rectangulaire 0°/90°/45°", "60": "Delta 0°/60°/120°"}


class Hooke(PageCalcul):
    fiche, tab = "hooke", "Hoo"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Hoo")), state.dm()
        self.calcule_onglet("Hoo", lambda: compute.computeHooke(s, dm))

    def _recharge(self) -> None:
        """Recharge l'exemple du mode courant (loadExample('Hooke', mode) de MATLAB)."""
        state.remplacer_saisie("Hoo", loadExample("Hoo", state.saisie("Hoo")["mode"]))

    def saisie(self, z: Zone) -> None:
        dm = state.dm()
        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Hoo")
        dossier.file_bar(z, "Hoo")
        z.legende(sources.source("hoo"))
        mode = z.choice("Hoo", "mode", "Loi", list(MODES), format_func=MODES.get, on_change=self.rafraichirSaisie)
        iso, ortho = mode != "ortho", mode == "ortho"
        sig_xy = mode in ("iso3D", "planeStress", "ortho")
        sig_3d = mode in ("iso3D", "ortho")

        def isotrope(c: Zone) -> None:
            c.choice_materiau("Hoo", ["E", "nu", "alpha"], dm, actif=iso)
            c.num("Hoo", "E", "E", "GPa", actif=iso)
            c.num("Hoo", "nu", "ν", "-", actif=iso)
            c.num("Hoo", "alpha", "α", "10⁻⁶/°C", actif=mode == "iso3D")
            c.num("Hoo", "dT", "ΔT", "°C", actif=mode == "iso3D")

        def contraintes(c: Zone) -> None:
            for champ, nom, actif in (("sxx", "σxx", sig_xy), ("syy", "σyy", sig_xy), ("szz", "σzz", sig_3d),
                                      ("syz", "σyz", sig_3d), ("sxz", "σxz", sig_3d), ("sxy", "σxy", sig_xy)):  # fmt: skip
                c.num("Hoo", champ, nom, "MPa", actif=actif)

        def deformations(c: Zone) -> None:
            for champ, nom in (("exx", "εxx"), ("eyy", "εyy"), ("gxy", "γxy = 2εxy")):
                c.num("Hoo", champ, nom, "µdéf", actif=mode == "planeStrain")

        def orthotrope(c: Zone) -> None:
            for champ, nom, unite in (("E1", "E1", "GPa"), ("E2", "E2", "GPa"), ("E3", "E3", "GPa"),
                                      ("nu12", "ν12", "-"), ("nu13", "ν13", "-"), ("nu23", "ν23", "-"),
                                      ("G12", "G12", "GPa"), ("G13", "G13", "GPa"), ("G23", "G23", "GPa")):  # fmt: skip
                c.num("Hoo", champ, nom, unite, actif=ortho)

        z.repliable("Matériau isotrope", ouvert=True, rendu=isotrope, cle="Hoo.iso")
        z.repliable("Contraintes (MPa)", ouvert=True, rendu=contraintes, cle="Hoo.sig")
        z.repliable("Déformations planes (µdéf)", ouvert=mode == "planeStrain", rendu=deformations, cle="Hoo.def")
        z.repliable("Orthotrope (axes 1, 2, 3 = x, y, z)", ouvert=ortho, rendu=orthotrope, cle="Hoo.ortho")
        z.bouton("Recharger l'exemple", self._recharge)

    def visualisation(self, z: Zone) -> None:
        synthese_resultat(z, "Hoo")
        dossier.validation_button(z, "Hoo")
        dossier.explanation_panel(z, "Hoo")
        res = state.result("Hoo")
        if res is None:
            return
        r, t = res["result"], res["tables"]
        z.succes(res["status"])
        z.plot(other_plots.mohr2D(r["mohr"]))

        def matrice(c: Zone) -> None:
            c.legende("Rigidité [C] en GPa (symétrique, définie positive).")
            c.tableau(t["Matrice"], index=True)

        z.onglets(
            {
                "Résultats": lambda c: c.tableau(t["Résultats"]),
                "Matrice": matrice,
                "Rapport": lambda c: c.rapport(r["rapport"]),
                "Formules": lambda c: c.formules(r["mohr"]["latex"]),
            }
        )


class Jauges(PageCalcul):
    fiche, tab = "extensometrie", "Jau"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Jau")), state.dm()
        self.calcule_onglet("Jau", lambda: compute.computeGauges(s, dm))

    def saisie(self, z: Zone) -> None:
        dm = state.dm()
        z.legende(sources.source("jau"))

        def jauge(c: Zone) -> None:
            c.num("Jau", "K", "Facteur de jauge K", "-")
            c.num("Jau", "eps", "ε", "µdéf")
            c.num("Jau", "R0", "R0", "Ω")

        def pont(c: Zone) -> None:
            c.choice("Jau", "cfg", "Montage", list(MONTAGES), format_func=MONTAGES.get)
            c.num("Jau", "Vin", "Alimentation Vin", "V")
            for champ in ("e1", "e2", "e3", "e4"):
                c.num("Jau", champ, f"ε{champ[1]}", "µdéf")
            c.num("Jau", "Vout", "Vout mesurée", "mV")

        def rosette(c: Zone) -> None:
            c.choice("Jau", "rtype", "Type", list(ROSETTES), format_func=ROSETTES.get)
            c.num("Jau", "ra", "ε à 0°", "µdéf")
            c.num("Jau", "rb", "ε à 90° (rect.) / 60° (delta)", "µdéf")
            c.num("Jau", "rc", "ε à 45° (rect.) / 120° (delta)", "µdéf")
            c.choice_materiau("Jau", ["E", "nu"], dm)
            c.num("Jau", "E", "E", "GPa")
            c.num("Jau", "nu", "ν", "-")

        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Jau")
        dossier.file_bar(z, "Jau")
        z.repliable("Jauge (loi de Bridgman)", ouvert=True, rendu=jauge, cle="Jau.jauge")
        z.repliable("Pont de Wheatstone", ouvert=True, rendu=pont, cle="Jau.pont")
        z.repliable("Rosette", ouvert=True, rendu=rosette, cle="Jau.rosette")
        z.bouton("Recharger l'exemple", lambda: dossier._charge_exemple("Jau"))

    def visualisation(self, z: Zone) -> None:
        synthese_resultat(z, "Jau")
        dossier.validation_button(z, "Jau")
        dossier.explanation_panel(z, "Jau")
        res = state.result("Jau")
        if res is None:
            return
        r, t = res["result"], res["tables"]
        z.succes(res["status"])
        z.graphs(
            "Jau_graphes_onglets",
            [
                ("Mohr des déformations (rosette)", lambda c: c.plot(other_plots.mohr2D(r["mohrDeformations"]))),
                ("Mohr des contraintes (rosette)", lambda c: c.plot(other_plots.mohr2D(r["mohrContraintes"]))),
            ],
        )

        def formules(c: Zone) -> None:
            for latex in (r["gauge"]["latex"], r["bridge"]["latex"], r["rosette"]["latex"]):
                c.formules(latex)

        z.onglets(
            {
                "Rosette": lambda c: c.tableau(t["Rosette"]),
                "Jauge et pont": lambda c: c.tableau(t["Jauge et pont"]),
                "Rapport": lambda c: c.rapport(r["rapport"]),
                "Formules": formules,
            }
        )


class PageHookeJauges(PageOnglets):
    titre = "Hooke et jauges"
    sousPages = [("Loi de Hooke", Hooke), ("Jauges, pont et rosettes", Jauges)]

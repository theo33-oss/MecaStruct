"""Page « Flambage » : poutre droite comprimée (compression, Rankine ou Euler), courbe de stabilité, mode propre.

Port de l'onglet « Flambage » de MecaStruct_App.m (buildBucklingTab, loadProfileForBuckling, computeBuckling).
"""

import copy
import math

from mecastruct.bureau import dossier, state, transfert
from mecastruct.bureau.page_calcul import PageCalcul, modes_resultat, synthese_suivie
from mecastruct.bureau.widgets import Zone
from mecastruct.core import buckling
from mecastruct.plots import other_plots
from mecastruct.services import compute

REGIMES = {
    "compression": ("Poutre trapue : compression simple", "avertissement"),
    "rankine": ("Poutre moyenne : formule de Rankine", "info"),
    "euler": ("Poutre élancée : formule d'Euler", "succes"),
}
CONDITIONS = {c["Condition"]: f"{c['Libelle']} (L' = {c['CoefficientTexte']} L)" for c in buckling.listConditions()}


class PageFlambage(PageCalcul):
    titre = "Flambage"
    fiche = "flambage"
    tab = "Fla"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Fla")), state.dm()
        self.calcule_onglet("Fla", lambda: compute.computeBuckling(s, dm))

    def _charge_profile(self) -> None:
        """Charge S, Iz, Iy du profilé choisi, valeurs du catalogue."""
        saisie = state.saisie("Fla")
        p = state.dm().getProfile(saisie["fam"], saisie["prof"])
        saisie["S"], saisie["Iz"], saisie["Iy"] = p["S"] * 1e6, p["Iz"] * 1e12, p["Iy"] * 1e12
        state.v["Fla_info"] = f"Section utilisée : profilé {p['Name']} (valeurs du catalogue)."
        self.rafraichirSaisie()

    def _importe_section(self) -> None:
        """Importe la section de la page Sections (useSectionForBeam : Poutres la reçoit aussi, comme MATLAB)."""
        if transfert.envoie_section(state.dm()) is None:
            state.v["Fla_msg"] = ("avertissement", "Calculez d'abord une section dans la page Sections.")
        self.rafraichirSaisie()

    def _section_manuelle(self) -> None:
        if state.v.get("Fla_info") != "Section utilisée : valeurs saisies à la main.":
            state.v["Fla_info"] = "Section utilisée : valeurs saisies à la main."
            self.rafraichirSaisie()

    def champs(self, z: Zone) -> None:
        dm, saisie = state.dm(), state.saisie("Fla")

        def section(c: Zone) -> None:
            if info := state.v.get("Fla_info"):
                c.texte(f"**{info}**")
            c.choice("Fla", "fam", "Famille de profilé", dm.listProfileFamilies(), on_change=self.rafraichirSaisie)
            profils = dm.listProfiles(saisie["fam"])
            if saisie["prof"] not in profils:
                saisie["prof"] = profils[0]
            c.choice("Fla", "prof", "Profilé", profils)
            c.bouton("Charger le profilé", self._charge_profile)
            c.bouton("← Importer depuis Sections", self._importe_section,
                     aide="Recopie S, Iz, Iy et le matériau de la page Sections (à calculer d'abord).")  # fmt: skip
            c.messageGarde("Fla_msg")
            for champ, label, unite in (("S", "S", "mm²"), ("Iz", "Iz", "mm⁴"), ("Iy", "Iy", "mm⁴")):
                c.num("Fla", champ, label, unite, min_value=0.0, on_change=self._section_manuelle)

        def poutre(c: Zone) -> None:
            c.choice_materiau("Fla", ["E", "Re"], dm)
            c.num("Fla", "E", "E", "GPa")
            c.num("Fla", "Re", "Re", "MPa")
            c.num("Fla", "L", "Longueur L", "m", min_value=0.0)
            c.choice("Fla", "cond", "Conditions aux limites", list(CONDITIONS), format_func=CONDITIONS.get)
            c.num("Fla", "P", "P appliquée (compression > 0, 0 = aucune)", "kN")
            c.num("Fla", "s", "Coefficient de sécurité s", "-")

        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Fla")
        synthese_suivie(z, "Fla")
        dossier.file_bar(z, "Fla")
        dossier.example_picker(z, "Fla")
        z.repliable("Section", ouvert=True, rendu=section, cle="Fla.section")
        z.repliable("Poutre comprimée", ouvert=True, rendu=poutre, cle="Fla.poutre")

    def saisie(self, z: Zone) -> None:
        self.champs(z)

    def _resultats(self, z: Zone, res: dict) -> None:
        b, c = res["result"]["analysis"], res["result"]["curve"]
        titre, niveau = REGIMES[b["regime"]]
        z.message(niveau, f"**Régime : {titre}** — λ = {b['lambda']:.4g} (λlim = {b['lambdaLim']:.4g})")
        if buckling.alerteSeuilLambdaLim(b["lambda"], b["lambdaLim"]):
            z.avertissement(
                f"λ = {b['lambda']:.4g} est à moins de 10 % de λlim = {b['lambdaLim']:.4g} : la charge critique "
                "change de modèle au seuil (Rankine → Euler) et saute de Re·S/2 à Re·S. "
                "Verdict à interpréter avec prudence."
            )
        z.plot(other_plots.bucklingCurve(c, b))
        z.plot(other_plots.bucklingMode(b))
        z.tableau(res["tables"]["Synthèse"])

        def demonstration(d: Zone) -> None:
            d.legende(b["modeText"])
            d.formules(b["derivation"])

        z.onglets(
            {
                "Démonstration": demonstration,
                "Rapport": lambda d: d.rapport(res["result"]["rapport"]),
                "Formules": lambda d: d.formules(b["latex"]),
            }
        )

    def visualisation(self, z: Zone) -> None:
        res = state.result("Fla")
        if res is not None and math.isfinite(res["result"]["analysis"]["P"]):  # P = 0 : aucune charge, pas de verdict
            b = res["result"]["analysis"]
            mot = "vérifié" if b["ok"] else "NON vérifié"
            modes_resultat(z, "Fla", res, status=f"P = {b['P'] / 1e3:.5g} kN, Padm = {b['Padm'] / 1e3:.5g} kN : {mot}",
                           ok=bool(b["ok"]))  # fmt: skip
        dossier.validation_button(z, "Fla")
        dossier.explanation_panel(z, "Fla")
        if state.result("Fla") is not None:
            self._resultats(z, state.result("Fla"))

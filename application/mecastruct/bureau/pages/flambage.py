"""Page « Flambage » : poutre droite comprimée (compression, Rankine ou Euler), courbe de stabilité, mode propre.

Port de l'onglet « Flambage » de MecaStruct_App.m (buildBucklingTab, loadProfileForBuckling, computeBuckling).
"""

import copy
import math

from mecastruct.bureau import dossier, state, transfert
from mecastruct.bureau.page_calcul import PageCalcul, modes_resultat
from mecastruct.bureau.widgets import Zone
from mecastruct.core import buckling
from mecastruct.plots import other_plots
from mecastruct.services import compute

REGIMES = {
    "compression": ("Poutre trapue : compression simple", "avertissement"),
    "rankine": ("Poutre moyenne : formule de Rankine", "info"),
    "euler": ("Poutre élancée : formule d'Euler", "succes"),
}
COURBES = {c: f"{c} (α = {a:.2f})".replace(".", ",") for c, a in buckling.facteursImperfection().items()}
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

        def eurocode(c: Zone) -> None:
            c.check("Fla", "ec3", "Vérifier aussi par les courbes de l'Eurocode 3",
                    help="Ajoute au résultat Ncr, λ̄, Φ, χ et Nb,Rd = χ·A·fy/γM1, et un mode de ruine NEd / Nb,Rd (NEd = P). "
                         "Euler et Rankine restent calculés.", on_change=self.rafraichirSaisie)  # fmt: skip
            actif = bool(saisie.get("ec3"))
            c.choice("Fla", "courbe", "Courbe de flambement", list(COURBES), format_func=COURBES.get, actif=actif,
                     help="Choisir la courbe dans le tableau 6.2 de l'EN 1993-1-1 (à vérifier sur la norme).")  # fmt: skip
            c.num("Fla", "gM1", "γM1, coefficient partiel (stabilité)", "-", min_value=0.0, actif=actif,
                  help="1,0 : valeur recommandée de l'EN 1993-1-1, reprise par la page Poutres pour l'EN et la France. "
                       "Autre pays : voir l'annexe nationale.")  # fmt: skip
            c.legende(
                "Choisir la courbe dans le tableau 6.2 de l'EN 1993-1-1 (à vérifier sur la norme) : MecaStruct ne la "
                "choisit pas selon le profilé. γM1 est saisi comme dans la page Poutres (1,0 : valeur de l'EN et de la France)."
            )

        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Fla")
        dossier.file_bar(z, "Fla")
        dossier.example_picker(z, "Fla")
        z.repliable("Section", ouvert=True, rendu=section, cle="Fla.section")
        z.repliable("Poutre comprimée", ouvert=True, rendu=poutre, cle="Fla.poutre")
        z.repliable("Eurocode 3 : courbes de flambement (EN 1993-1-1, 6.3.1)", ouvert=bool(saisie.get("ec3")),
                    rendu=eurocode, cle="Fla.ec3")  # fmt: skip

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
        e = res["result"].get("ec3")

        def demonstration(d: Zone) -> None:
            d.legende(b["modeText"])
            d.formules(b["derivation"])

        def formules(d: Zone) -> None:
            d.formules(b["latex"])
            if e:
                d.legende(f"Eurocode 3 : courbe {e['curve']} choisie par l'utilisateur (tableau 6.2 non appliqué, à vérifier sur la norme).")
                d.formules(e["latex"])

        z.onglets(
            {
                "Démonstration": demonstration,
                "Rapport": lambda d: d.rapport(res["result"]["rapport"]),
                "Formules": formules,
            }
        )

    def visualisation(self, z: Zone) -> None:
        res = state.result("Fla")
        if res is not None and math.isfinite(res["result"]["analysis"]["P"]):  # P = 0 : aucune charge, pas de verdict
            b, e = res["result"]["analysis"], res["result"].get("ec3")
            mot = "vérifié" if b["ok"] else "NON vérifié"
            status, ok = f"P = {b['P'] / 1e3:.5g} kN, Padm = {b['Padm'] / 1e3:.5g} kN : {mot}", bool(b["ok"])
            if e and e["ok"] is not None:  # un seul mode non admissible rend le calcul « NON vérifié »
                status += f" — NEd/Nb,Rd = {e['ratio']:.4g} (EC3) : {'vérifié' if e['ok'] else 'NON vérifié'}"
                ok = ok and bool(e["ok"])
            modes_resultat(z, "Fla", res, status=status, ok=ok)
        dossier.validation_button(z, "Fla")
        dossier.explanation_panel(z, "Fla")
        if state.result("Fla") is not None:
            self._resultats(z, state.result("Fla"))

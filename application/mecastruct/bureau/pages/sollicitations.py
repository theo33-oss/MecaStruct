"""Page « Sollicitations » : traction, cisaillement et matage, torsion, flexion (quatre sous-onglets).

Port des onglets de MecaStruct_App.m (buildSolicitationsTab, computeTraction, computeShear, computeKey, computePin,
computeTorsion, computeBending). Cisaillement et flexion utilisent la section de la page Sections.
"""

import copy

from mecastruct.bureau import dossier, machine_page, state
from mecastruct.bureau.page_calcul import PageCalcul, PageOnglets, Volet, panels, synthese_suivie
from mecastruct.bureau.widgets import Zone
from mecastruct.core import geometry, key_pin
from mecastruct.plots import section_plots, sollicitation_plots
from mecastruct.services import beam_design, beam_services, compute, machine

CRITERES = {"Tresca": "Tresca (τe = Re/2)", "VonMises": "Von Mises (τe = Re/√3)"}
FORMES_CLE = {"A": "A (bouts ronds)", "B": "B (bouts droits)", "C": "C (un bout rond)"}
# goupille sous couple : (clé, libellé, valeur de départ) ; T en N·m, longueurs en mm
GOUPILLE_COUPLE = [
    ("T", "Couple T (N·m)", 50.0),
    ("D", "Diamètre de l'arbre D (mm)", 30.0),
    ("D1", "Diamètre extérieur du moyeu D1 (mm)", 50.0),
    ("d", "Diamètre de la goupille d (mm)", 8.0),
    ("dint", "Alésage d'une goupille élastique (0 = pleine) (mm)", 0.0),
    ("l", "Longueur engagée l (mm)", 30.0),
]


def _tau_adm(saisie: dict) -> float:
    """τadm (MPa) du matériau et du critère de la saisie Cisaillement, comme pour la clavette et la goupille."""
    return compute.computeKey(saisie, state.dm())["result"]["tauAdm"] / 1e6


def _section_des_sections(saisie: dict) -> None:
    """La section de la saisie est celle de la page Sections (dernier calcul), comme SectionData de MATLAB."""
    r = state.result("Sec")
    if r is not None:
        saisie["section"] = r["result"]["sec"]


def _synthese(z: Zone, res: dict | None, cle: str) -> None:
    """Ligne d'état, tableau de synthèse et rapport d'un calcul."""
    if res is None:
        return
    z.succes(res["status"])
    z.tableau(res["tables"]["Synthèse"])
    z.repliable("Rapport", rendu=lambda c: c.rapport(res["result"]["rapport"]), cle=f"rapport.{cle}")


class _SousPage(PageCalcul):
    """Sous-onglet : Calculer, synthèse, fichiers, exemples, puis les champs propres à l'onglet."""

    def calculer(self) -> None:
        raise NotImplementedError

    def champs(self, z: Zone) -> None:
        raise NotImplementedError

    def resultats(self, z: Zone) -> None:
        raise NotImplementedError

    def saisie(self, z: Zone) -> None:
        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee(f"erreur.{self.tab}")
        synthese_suivie(z, self.tab)
        dossier.file_bar(z, self.tab)
        dossier.example_picker(z, self.tab)
        self.champs(z)

    def visualisation(self, z: Zone) -> None:
        dossier.validation_button(z, self.tab)
        dossier.explanation_panel(z, self.tab)
        self.resultats(z)

    def calcule(self, tab: str, travail) -> None:
        self.calcule_onglet(tab, travail)


# ------------------------------------------------------------------------------------------------- Traction


class Traction(_SousPage):
    fiche, tab = "traction", "Tra"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Tra")), state.dm()
        self.calcule("Tra", lambda: compute.computeTraction(s, dm))

    def champs(self, z: Zone) -> None:
        dm, saisie = state.dm(), state.saisie("Tra")

        def barre(c: Zone) -> None:
            c.num("Tra", "N", "N (> 0 traction)", "kN")
            c.num("Tra", "S0", "S0", "mm²", min_value=0.0)
            c.num("Tra", "L0", "L0", "m", min_value=0.0)
            c.choice_materiau("Tra", ["E", "nu", "alpha", "Re"], dm)
            c.num("Tra", "E", "E", "GPa")
            c.num("Tra", "nu", "ν", "-")
            c.num("Tra", "alpha", "α", "10⁻⁶/°C")
            c.num("Tra", "Re", "Re", "MPa")
            c.num("Tra", "dT", "ΔT", "°C")
            c.num("Tra", "Kt", "Kt", "-", min_value=1.0)
            c.num("Tra", "s", "Coefficient de sécurité s", "-")
            c.num("Tra", "dLmax", "ΔL max (0 = sans limite)", "mm", min_value=0.0)

        def variable(c: Zone) -> None:
            c.check("Tra", "varS", "Utiliser S(x)")
            c.text("Tra", "Sexpr", "S(x) (mm², x en m)")
            c.legende(
                "Expression en x (m) donnant S en mm² : nombres, x, pi, sqrt, exp, log, sin, cos, tan, abs, + − * / ^. "
                "Exemple (barre conique d = 20 → 30 mm) : pi/4*(20 + 10*x)^2."
            )

        z.repliable("Barre et chargement", ouvert=True, rendu=barre, cle="Tra.barre")
        z.repliable("Section variable", ouvert=bool(saisie["varS"]), rendu=variable, cle="Tra.variable")

    def resultats(self, z: Zone) -> None:
        res = state.result("Tra")
        if res is None:
            return
        r, saisie = res["result"], state.saisie("Tra")
        z.plot(sollicitation_plots.tractionStress(r["x"], saisie["N"] * 1e3, r["Sx"], saisie["Kt"], r["sigmaAdm"]))
        z.plot(sollicitation_plots.elongations(r["dL"]))
        _synthese(z, res, "Tra")
        z.formules(r["latex"])


# ------------------------------------------------------------------------------- Cisaillement et matage


class Cisaillement(_SousPage):
    fiche, tab = "cisaillement", "Cis"

    def calculer(self) -> None:
        saisie, dm = state.saisie("Cis"), state.dm()
        _section_des_sections(saisie)
        s = copy.deepcopy(saisie)
        self.calcule("Cis", lambda: compute.computeShear(s, dm))

    def _applique_matage(self) -> None:
        """P_adm prend la pression admissible minimale de la ligne choisie dans la table de matage."""
        i = state.v.get("Cis_matage", "-")
        if i != "-":
            state.saisie("Cis")["Padm"] = float(state.dm().BearingPressures["Pmin"].iloc[i]) / 1e6
        self.rafraichirSaisie()

    def champs(self, z: Zone) -> None:
        dm, saisie = state.dm(), state.saisie("Cis")

        def materiau(c: Zone) -> None:
            c.choice_materiau("Cis", ["Re", "G"], dm)
            c.num("Cis", "Re", "Re", "MPa")
            c.num("Cis", "G", "G", "GPa")
            c.choice("Cis", "crit", "Critère (τe)", list(CRITERES), format_func=CRITERES.get)
            c.num("Cis", "s", "Coefficient de sécurité s", "-")

        def simple(c: Zone) -> None:
            c.num("Cis", "T", "T", "kN")
            c.num("Cis", "S", "S cisaillée", "mm²", min_value=0.0)
            c.num("Cis", "k", "k = τmax/τmoy", "-")
            c.legende("Jourawski : section de la page Sections, Ty = T.")
            c.num("Cis", "Fm", "F", "kN")
            c.num("Cis", "Sm", "S matée", "mm²", min_value=0.0)
            T = dm.BearingPressures
            c.liste("Table de matage", ["-", *range(len(T))], "Cis_matage", defaut="-",
                    format=lambda i: "-" if i == "-" else f"{T['Liaison'].iloc[i]} — {T['Conditions'].iloc[i]}",
                    apres=self._applique_matage)  # fmt: skip
            c.num("Cis", "Padm", "P_adm", "MPa", min_value=0.0)

        def clavette(c: Zone) -> None:
            c.num("Cis", "C", "Couple C", "kN·m")
            c.num("Cis", "Dk", "Diamètre d'arbre D", "mm")
            c.num("Cis", "ak", "Largeur a", "mm")
            c.num("Cis", "bk", "Hauteur b", "mm")
            c.num("Cis", "Lk", "Longueur L (0 = dimensionner)", "mm", min_value=0.0)

            def cle() -> None:
                s = copy.deepcopy(saisie)
                self.calcule("CisKey", lambda: compute.computeKey(s, dm))

            c.bouton("Calculer la clavette", cle)
            c.texte("**Clavette normalisée NF E22-177** : b × h, t1 et t2 lus d'après D ; C, D, L et P_adm ci-dessus.")
            forme = c.radio("Forme", list(key_pin.FORMES), "Cis_cle_forme", format=FORMES_CLE.get)

            def std() -> None:
                s = copy.deepcopy(saisie)
                self.calcule("CisKeyStd", lambda: machine.computeKeyStandard(s, forme, _tau_adm(s)))

            c.bouton("Vérifier la clavette normalisée", std)

        def goupille(c: Zone) -> None:
            c.num("Cis", "Fp", "F", "kN")
            c.num("Cis", "dp", "d", "mm")
            c.num("Cis", "ep", "e — épaisseur matée", "mm")
            c.num("Cis", "np", "Sections cisaillées n", "-", entier=True)

            def pin() -> None:
                s = copy.deepcopy(saisie)
                self.calcule("CisPin", lambda: compute.computePin(s, dm))

            c.bouton("Calculer la goupille", pin)
            c.texte("**Goupille transmettant un couple** (arbre / moyeu ; P_adm et matériau ci-dessus)")
            montage = c.radio("Montage", ["transversale", "longitudinale"], "Cis_gc_montage",
                              apres=self.rafraichirSaisie)  # fmt: skip
            inutile = "l" if montage == "transversale" else "D1"
            for cle, label, defaut in GOUPILLE_COUPLE:
                state.v.setdefault(f"Cis_gc_{cle}", defaut)
                if cle != inutile:
                    c.nombre(label, f"Cis_gc_{cle}", defaut, mini=0.0)

            def couple() -> None:
                p = {cle: state.v.get(f"Cis_gc_{cle}", defaut) for cle, _, defaut in GOUPILLE_COUPLE}
                s = copy.deepcopy(saisie)
                p.update(montage=montage, Padm=s["Padm"])
                self.calcule("CisPinT", lambda: machine.computePinTorque({**p, "tauAdm": _tau_adm(s)}))

            c.bouton("Vérifier la goupille sous couple", couple)

        panels(z, "Cis", [
            Volet("materiau", "Matériau et critère", "Haut", True, materiau),
            Volet("simple", "Cisaillement simple, Jourawski et matage", "Haut", True, simple),
            Volet("clavette", "Clavette parallèle", "Bas", False, clavette),
            Volet("goupille", "Goupille / rivet", "Bas", False, goupille),
        ])  # fmt: skip

    def resultats(self, z: Zone) -> None:
        res = state.result("Cis")
        if res is not None:
            r, saisie = res["result"], state.saisie("Cis")
            sec = saisie["section"]
            P = geometry.analytical(sec)
            shear, jour, bearing = r["shear"], r["jour"], r["bearing"]
            taux = [
                abs(shear["tauMax"]) / shear["tauAdm"],
                abs(jour["tauMax"]) / shear["tauAdm"],
                abs(bearing["P"]) / (saisie["Padm"] * 1e6),
            ]
            z.plot(section_plots.section(sec, P))
            z.plot(section_plots.sectionStress(sec, P, None, jour))
            z.plot(sollicitation_plots.ratios(["τmax/τadm", "τJourawski/τadm", "P/Padm"], taux,
                                              "Taux d'utilisation (cisaillement et matage)"))  # fmt: skip
            _synthese(z, res, "Cis")
        for cle, titre in (("CisKey", "Clavette"), ("CisPin", "Goupille")):
            autre = state.result(cle)
            if autre is not None:
                z.sousTitre(titre)
                _synthese(z, autre, cle)
        for cle, titre in (("CisKeyStd", "Clavette normalisée"), ("CisPinT", "Goupille sous couple")):
            autre = state.result(cle)
            if autre is not None:
                z.sousTitre(titre)
                z.statut(autre["status"], autre["ok"])
                z.tableau(autre["tables"]["Synthèse"])
                z.repliable("Explications du calcul", rendu=lambda c, a=autre: machine_page.explications(c, a),
                            cle=f"expl.{cle}")  # fmt: skip


# ------------------------------------------------------------------------------------------------- Torsion


class Torsion(_SousPage):
    fiche, tab = "torsion", "Tor"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Tor")), state.dm()
        self.calcule("Tor", lambda: compute.computeTorsion(s, dm))

    def champs(self, z: Zone) -> None:
        def arbre(c: Zone) -> None:
            c.num("Tor", "Mt", "Mt", "kN·m")
            c.num("Tor", "D", "D", "mm", min_value=0.0)
            c.num("Tor", "d", "d — alésage (0 = plein)", "mm", min_value=0.0)
            c.num("Tor", "L", "L", "m", min_value=0.0)
            c.choice_materiau("Tor", ["G", "Re"], state.dm())
            c.num("Tor", "G", "G", "GPa")
            c.num("Tor", "Re", "Re", "MPa")
            c.choice("Tor", "crit", "Critère (τe)", list(CRITERES), format_func=CRITERES.get)
            c.num("Tor", "s", "Coefficient de sécurité s", "-")
            c.num("Tor", "Kt", "Kt", "-", min_value=1.0)
            c.num("Tor", "thetaAdm", "θ admissible (0 = sans)", "°/m", min_value=0.0)

        z.repliable("Arbre circulaire", ouvert=True, rendu=arbre, cle="Tor.arbre")

    def resultats(self, z: Zone) -> None:
        res = state.result("Tor")
        if res is None:
            return
        r, saisie = res["result"], state.saisie("Tor")
        z.plot(sollicitation_plots.torsionStress(r, saisie["D"] * 1e-3))
        z.plot(sollicitation_plots.torsionAngle(saisie["L"], r["theta"], r["phi"]["analytique"]))
        _synthese(z, res, "Tor")
        z.formules(r["latex"])


# ------------------------------------------------------------------------------------------------- Flexion


class Flexion(_SousPage):
    fiche, tab = "flexion", "Fle"

    def calculer(self) -> None:
        saisie, dm = state.saisie("Fle"), state.dm()
        _section_des_sections(saisie)
        s = copy.deepcopy(saisie)
        self.calcule("Fle", lambda: compute.computeBending(s, dm))

    def _efforts_poutre(self, mode: str) -> None:
        """Remplit N, Mfz, Mfy avec les efforts de la poutre, recalculée d'abord (loadFromBeam de MATLAB)."""
        cible, dm = state.saisie("Fle"), state.dm()
        try:
            res = beam_services.computeBeam(state.saisie("Beam"), dm)
            state.set_result("Beam", res)
            nouvelle = beam_design.loadFromBeam(cible, res, "Fle", mode)
        except Exception as err:  # noqa: BLE001 : abscisse hors de la poutre, poutre incalculable…
            state.v["Fle_msg"] = ("error", str(getattr(err, "message", err)))
            self.rafraichirSaisie()
            return
        state.v["saisie"]["Fle"] = nouvelle
        note = "⚠ Résultats NON fiables (hyperstatique, Iyz ≠ 0) — " if res["unreliable"] else ""
        state.v["Fle_msg"] = (
            "info",
            f"{note}Efforts lus sur la poutre en s = {nouvelle['s0']:.4g} m : N = {nouvelle['N']:.4g} kN, "
            f"Mfz = {nouvelle['Mfz']:.4g} kN·m, Mfy = {nouvelle['Mfy']:.4g} kN·m",
        )
        state.reset_widgets("Fle")

    def champs(self, z: Zone) -> None:
        z.legende("Section : celle de la page Sections (à calculer d'abord ; sinon la section de l'exemple).")

        def efforts(c: Zone) -> None:
            c.num("Fle", "N", "N : traction > 0", "kN",
                  help="Effort normal : positif en traction, négatif en compression.")  # fmt: skip
            c.num("Fle", "Mfz", "Mfz : plan (x,y)", "kN·m",
                  help="Moment de flexion autour de z (charges dans le plan x,y). Mfz > 0 : fibres du haut (y > 0) "
                  "comprimées, fibres du bas tendues.")  # fmt: skip
            c.num("Fle", "Mfy", "Mfy : plan (x,z)", "kN·m",
                  help="Moment de flexion autour de y (charges dans le plan x,z). Mfy > 0 : fibres z > 0 tendues.")  # fmt: skip

        def poutre(c: Zone) -> None:
            c.num("Fle", "s0", "s sur la poutre", "m", help="Abscisse de la coupure dans la page Poutres (de 0 à L).",
                  min_value=0.0)  # fmt: skip
            cols = c.colonnes(2)
            cols[0].bouton("Efforts en s", lambda: self._efforts_poutre("abscisse"))
            cols[1].bouton("Efforts au point critique", lambda: self._efforts_poutre("max"))
            c.messageGarde("Fle_msg")

        def kt(c: Zone) -> None:
            c.num("Fle", "Kt", "Kt", "-", min_value=1.0)
            c.choice_materiau("Fle", ["Re"], state.dm())
            c.num("Fle", "Re", "Re", "MPa")
            c.num("Fle", "s", "Coefficient de sécurité s", "-")

        z.repliable("Efforts dans la section étudiée", ouvert=True, rendu=efforts, cle="Fle.efforts")
        z.repliable("Reprendre les efforts de la poutre", ouvert=True, rendu=poutre, cle="Fle.poutre")
        z.repliable("Kt, matériau et sécurité", ouvert=True, rendu=kt, cle="Fle.kt")

    def resultats(self, z: Zone) -> None:
        res = state.result("Fle")
        if res is None:
            return
        r = res["result"]
        z.plot(sollicitation_plots.bendingMarks(section_plots.section(r["sec"], r["P"]), r["P"], r["bend"]))
        z.plot(section_plots.sectionStress(r["sec"], r["P"], r["bend"], None))
        _synthese(z, res, "Fle")
        z.formules(r["bend"]["latex"])


class PageSollicitations(PageOnglets):
    titre = "Sollicitations"
    sousPages = [
        ("Traction / compression", Traction),
        ("Cisaillement & matage", Cisaillement),
        ("Torsion", Torsion),
        ("Flexion", Flexion),
    ]

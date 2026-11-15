"""Page « Poutres » : saisie, calcul, diagrammes, tableaux de résultats et fonctions avancées.

Port de l'onglet « Poutres » de MecaStruct_App.m (buildBeamTab, computeBeam, addQuickLoad, applyNationalAnnex,
computeCombinations, checkEurocode, checkFatigue, findLightestProfile, computeMovingLoad, sendToTensor, historique).
Le mode « Ossature 3D » (pages/ossature3d.py) est un second panneau de la même page.
"""

import copy

import numpy as np

from mecastruct.bureau import dossier, state
from mecastruct.bureau.page_calcul import PageCalcul, Volet, panels
from mecastruct.bureau.widgets import Zone, liste_col, nombre_col, texte_col
from mecastruct.core import geometry
from mecastruct.core.pp import asPP
from mecastruct.plots import beam_plots, section_plots
from mecastruct.services import beam_design, beam_services
from mecastruct.services.compute import _sectionLabel

TYPES_APPUI = ["appui_simple", "rotule", "pivot", "pivot_glissant", "encastrement"]
CAS = ["G", "Q", "W", "S"]
COMPOSANTES = ["N", "Ty", "Tz", "Mt", "Mfy", "Mfz"]
FAMILLES = ["IPE", "HEA", "HEB", "IPN", "UPN", "UAP"]
FORMES = {
    "Uniforme": "uniforme",
    "Triangulaire croissante (0 → p)": "triangle_croissant",
    "Triangulaire décroissante (p → 0)": "triangle_decroissant",
    "Trapèze (p1 → p2)": "trapeze",
}
ANNEXES = {
    "EN": "Valeurs recommandées de l'EN",
    "FR": "France (NF EN 1993-1-1/NA)",
    "autre": "Autre : saisir γM0 et γM1",
}
ANNEXES_CLES = ("BeamCombo", "BeamMov", "BeamProf", "BeamEC3", "BeamFat")  # résultats des volets du bas
NON_VERIFIE = (
    "Non vérifiés : voilement sous charges concentrées, flexion déviée, ELS, classe 4 ; annexe nationale : seules "
    "γM0 et γM1 sont paramétrables."
)


def _cas() -> object:
    return liste_col("case", "Cas", CAS, "G")


class PagePoutres(PageCalcul):
    titre = "Poutres"
    fiche = "equilibre"
    tab = "Beam"

    def construire(self) -> None:
        state.init()
        if "beam_history" not in state.v:
            state.push_beam_history()
        super().construire()
        from mecastruct.bureau.pages import ossature3d

        self.panneau3d = ossature3d.construire(self)
        self.d.addWidget(self.panneau3d, 1)
        self.basculer()

    def mode3d(self) -> bool:
        return state.v.get("poutres.mode") == "Ossature 3D"

    def actives(self) -> list:
        return [s for s in self.sections if s.mode3d == self.mode3d()] if self.bati3d() else self.sections

    def bati3d(self) -> bool:
        return hasattr(self, "panneau3d")

    def basculer(self) -> None:
        en3d = self.mode3d()
        self.panneau.setVisible(not en3d)
        self.panneau3d.setVisible(en3d)
        self.rafraichirTout()

    def entete(self, z: Zone) -> None:
        super().entete(z)
        z.radio("Mode", ["Poutre 2D", "Ossature 3D"], "poutres.mode", defaut="Poutre 2D", apres=self.basculer)

    # --- calcul et états -------------------------------------------------------------------------------------------

    def _etat(self, texte: str, ok: bool | None = None, cle: str = "Beam") -> None:
        """Ligne d'état de la page : texte, verdict (True vert, False rouge, None orange) et clé du résultat."""
        state.v["Beam_etat"] = (texte, ok, cle)

    def essaie(self, cle: str, travail, apres=None) -> None:
        """Résultat de `travail()` gardé sous `cle` ; en cas d'erreur, message affiché, résultat et ligne d'état effacés."""

        def fin(valeur) -> None:
            state.set_result(cle, valeur, source="Beam")
            if apres:
                apres(valeur)

        def echec() -> None:
            state.effacer_resultat(cle)
            state.v.pop("Beam_etat", None)  # un verdict précédent ne doit pas survivre à un calcul en erreur

        self.lancer(travail, fin, "erreur.Beam", echec)

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Beam")), state.dm()

        def apres(res: dict) -> None:
            self._etat(res["status"], None if res["unreliable"] else res["check"]["ok"])
            state.push_beam_history()

        self.essaie("Beam", lambda: beam_services.computeBeam(s, dm), apres)

    def _historique(self, step: int) -> None:
        """Annuler (-1) ou rétablir (+1) la dernière modification de la saisie."""
        msg = state.move_beam_history(step)
        state.v["Beam_msg"] = ("info", msg)
        self.rafraichirTout()

    def _applique_materiau(self) -> None:
        """E, G, Re prennent les valeurs du matériau choisi (applyMaterial de MATLAB)."""
        saisie = state.saisie("Beam")
        m = state.dm().getMaterial(saisie["mat"])
        saisie["E"], saisie["G"], saisie["Re"] = m["E"] / 1e9, m["G"] / 1e9, m["Re"] / 1e6
        self.rafraichirSaisie()

    def _section_manuelle(self) -> None:
        """Une valeur de section est saisie à la main : la forme associée n'est plus valable (markBeamManual)."""
        saisie = state.saisie("Beam")
        if saisie.get("section") is not None or saisie.get("secTabulated"):
            saisie["section"] = None
            saisie["secTabulated"] = False
            self.rafraichirSaisie()

    def _importe_section(self) -> None:
        """Recopie la section de la page Sections dans la saisie Poutres (useSectionForBeam)."""
        res = state.result("Sec")["result"]
        mat = state.dm().getMaterial(state.saisie("Sec")["mat"])
        state.remplacer_saisie("Beam", beam_design.sectionToBeamInput(state.saisie("Beam"), res["sec"], res["P"], mat))

    def _applique_annexe(self) -> None:
        """Annexe nationale choisie : γM0 et γM1 valent 1 pour l'EN et la France ; « autre » : champs libres."""
        saisie = state.saisie("Beam")
        if saisie["na"] in ("EN", "FR"):
            saisie["gM0"] = saisie["gM1"] = 1.0
        self.rafraichirSaisie()

    def _ajoute_charge_rapide(self) -> None:
        """Ajoute une ligne au tableau des charges réparties d'après « Charge rapide »."""
        v = state.v
        try:
            nouvelle = beam_services.addQuickLoad(
                state.saisie("Beam"), FORMES[v["Beam_qforme"]], v["Beam_qa"], v["Beam_qb"], v["Beam_qp1"],
                v["Beam_qp2"], v["Beam_qdir"], v["Beam_qcas"],
            )  # fmt: skip
        except Exception as err:  # noqa: BLE001 : b ≤ a
            v["Beam_msg"] = ("error", str(getattr(err, "message", err)))
            self.rafraichirSaisie()
            return
        state.remplacer_saisie("Beam", nouvelle)

    def _envoie_tenseur(self) -> None:
        """Transmet l'état de contrainte du point le plus sollicité à la saisie Tenseurs (sendToTensor)."""
        saisie, dm = state.saisie("Beam"), state.dm()
        try:
            res = beam_services.computeBeam(saisie, dm)
            etat = beam_design.sendToTensor(res)
        except Exception as err:  # noqa: BLE001
            state.v["Beam_msg"] = ("error", str(getattr(err, "message", err)))
            self.rafraichirSaisie()
            return
        state.set_result("Beam", res)
        state.saisie("Ten").update(
            sig=etat["sig"].tolist(), mat=saisie["mat"], Re=saisie["Re"],
            Rm=dm.getMaterial(saisie["mat"])["Rm"] / 1e6, s=saisie["s"],
        )  # fmt: skip
        y, z = etat["loc"][0] * 1e3, etat["loc"][1] * 1e3
        state.v["Beam_msg"] = (
            "tenseur",
            f"État transmis à la page Tenseurs & critères : s = {etat['s']:.4g} m, (y, z) = ({y:.4g} ; {z:.4g}) mm, "
            f"σxx = {etat['sig'][0, 0]:.5g} MPa",
        )
        state.reset_widgets("Ten")
        self.rafraichirTout()

    def _utilise_profile(self) -> None:
        """Met le profilé retenu dans la saisie (section, S, Iz…), comme « Importer depuis Sections »."""
        best = state.result("BeamProf")[1]
        sec = geometry.fromProfile(best)
        state.remplacer_saisie("Beam", beam_design.sectionToBeamInput(state.saisie("Beam"), sec, geometry.analytical(sec), None))

    def _affiche_message(self, z: Zone) -> None:
        """Message laissé par un bouton (erreur, information, lien vers la page Tenseurs)."""
        m = state.v.get("Beam_msg")
        z.messageGarde("Beam_msg")
        if m and m[0] == "tenseur":
            z.lien("tenseurs", "⭕ Ouvrir Tenseurs & critères")

    # --- volets de saisie --------------------------------------------------------------------------------------------

    def _saisie_poutre_et_section(self, z: Zone) -> None:
        """Longueur, matériau, E, G, Re."""
        z.num("Beam", "L", "Longueur L", "m", help="Longueur de la poutre entre ses deux extrémités, en mètres.",
              min_value=0.0)  # fmt: skip
        z.choice("Beam", "mat", "Matériau", state.dm().listMaterials(), on_change=self._applique_materiau)
        z.num("Beam", "E", "E", "GPa", help="Module d'Young : rigidité du matériau (acier ≈ 190–210 GPa).")
        z.num("Beam", "G", "G", "GPa", help="Module de cisaillement : G = E / (2(1+ν)).")
        z.num("Beam", "Re", "Re", "MPa",
              help="Limite élastique : contrainte au-delà de laquelle le matériau se déforme définitivement.")  # fmt: skip

    def _saisie_section(self, z: Zone) -> None:
        saisie = state.saisie("Beam")
        sec = saisie.get("section")
        if sec is None:
            z.texte("**Section utilisée : valeurs saisies à la main (aucune forme associée).**")
        else:
            origine = "valeurs du catalogue" if saisie.get("secTabulated") else "contour exact"
            z.texte(f"**Section utilisée : {_sectionLabel(sec)} (importée de Sections, {origine}).**")
            try:  # dessin de la section utilisée, comme dans la page Sections
                fig = section_plots.section(sec, geometry.analytical(sec))
                fig.update_layout(height=340)
                z.plot(fig)
            except Exception as err:  # noqa: BLE001 : section sans dessin possible, seul le dessin est omis
                z.legende(f"Dessin indisponible : {getattr(err, 'message', err)}")
        champs = [
            ("S", "S", "mm²", "Aire de la section droite."),
            ("Iz", "Iz — flexion (x,y)", "mm⁴", "Moment quadratique pour la flexion dans le plan (x,y), charges verticales."),
            ("Iy", "Iy — flexion (x,z)", "mm⁴", "Moment quadratique pour la flexion dans le plan (x,z), charges horizontales."),
            ("Ix", "Ix — constante de torsion", "mm⁴", "Constante de torsion (moment quadratique polaire pour un arbre rond)."),
            ("Iyz", "Iyz — produit d'inertie (0 si axes principaux)", "mm⁴",
             "Produit d'inertie : 0 si y et z sont les axes principaux (cas courant)."),
            ("ky", "ky — section réduite, tranchant Ty", "-", "Section réduite : le cisaillement est repris par S/ky ; 1 par défaut."),
            ("kz", "kz — section réduite, tranchant Tz", "-", "Section réduite : le cisaillement est repris par S/kz ; 1 par défaut."),
            ("vy", "Fibre extrême |y|max", "mm", "Distance du centre de gravité à la fibre la plus éloignée selon y."),
            ("vz", "Fibre extrême |z|max", "mm", "Distance du centre de gravité à la fibre la plus éloignée selon z."),
        ]  # fmt: skip
        for champ, label, unite, aide in champs:
            z.num("Beam", champ, label, unite, help=aide, on_change=self._section_manuelle)
        z.bouton("← Importer depuis Sections", self._importe_section, actif=state.result("Sec") is not None,
                 aide="Recopie S, Iz, Iy, Ix, Iyz, ky, kz, fibres extrêmes et matériau de la page Sections (à calculer avant).")  # fmt: skip

    def _saisie_charges(self, z: Zone) -> None:
        z.legende(
            "Signes : Fy < 0 = force vers le bas ; Fx > 0 = dans le sens de x (vers la droite) ; "
            "Mz > 0 = sens trigonométrique (axes directs)."
        )
        z.table(
            "Beam", "sup",
            [nombre_col("pos", "Position (m)"), liste_col("type", "Type", TYPES_APPUI, "appui_simple"), texte_col("name", "Nom")],
            help="Appuis. appui_simple et pivot_glissant bloquent les déplacements transversaux y et z (la poutre glisse "
            "selon x) ; rotule et pivot bloquent x, y et z (rotations libres) ; encastrement bloque tout.",
        )  # fmt: skip
        z.texte("**Forces ponctuelles** (composantes globales)")
        z.table("Beam", "pl", [nombre_col("pos", "Position (m)"), nombre_col("Fx", "Fx (kN)"), nombre_col("Fy", "Fy (kN)"),
                               nombre_col("Fz", "Fz (kN)"), texte_col("name", "Nom"), _cas()])  # fmt: skip
        z.texte("**Couples ponctuels**")
        z.table("Beam", "pm", [nombre_col("pos", "Position (m)"), nombre_col("Mx", "Mx (kN·m)"), nombre_col("My", "My (kN·m)"),
                               nombre_col("Mz", "Mz (kN·m)"), texte_col("name", "Nom"), _cas()])  # fmt: skip
        z.texte("**Charges réparties**")
        z.table(
            "Beam", "dl",
            [nombre_col("a", "a (m)"), nombre_col("b", "b (m)"), liste_col("dir", "Dir.", ["x", "y", "z"], "y"),
             liste_col("type", "Type", ["uniforme", "linéaire", "polynomiale"], "uniforme"),
             texte_col("vals", "Valeurs (kN/m)", "-10"), texte_col("name", "Nom"), _cas()],
            help="Valeurs : uniforme « p0 » ; linéaire « p1 p2 » (de a à b) ; polynomiale : coefficients en ξ = s − a, "
            "ordre décroissant (kN/m, kN/m², ...). py < 0 : charge descendante.",
        )  # fmt: skip

    def _saisie_options(self, z: Zone) -> None:
        z.choice("Beam", "plane", "Plan de la déformée", ["xy", "xz"],
                 format_func={"xy": "(x,y) : v, Mfz, Iz", "xz": "(x,z) : w, Mfy, Iy"}.get)  # fmt: skip
        z.check("Beam", "shear", "Tranchant dans Castigliano")
        z.multi("Diagrammes", COMPOSANTES, "Beam.comps",
                aide="Composantes tracées ; aucune choisie = celles qui ne sont pas nulles.")  # fmt: skip
        z.num("Beam", "s", "Coefficient de sécurité s", "-",
              help="Coefficient de sécurité : on exige σ ≤ Re / s (typiquement 1,5 à 3).")  # fmt: skip
        z.num("Beam", "Kt", "Kt", "-", help="Coefficient de concentration de contrainte (1 si aucun trou ni épaulement).")

    def _saisie_charge_rapide(self, z: Zone) -> None:
        z.liste("Forme", list(FORMES), "Beam_qforme")
        z.liste("Direction", ["x", "y", "z"], "Beam_qdir", defaut="y")
        z.liste("Cas de charge", CAS, "Beam_qcas")
        z.nombre("Début a (m)", "Beam_qa", 0.0)
        z.nombre("Fin b (m)", "Beam_qb", 1.0)
        z.nombre("p ou p1 (kN/m, < 0 : vers le bas)", "Beam_qp1", -10.0)
        z.nombre("p2 (kN/m, trapèze seulement)", "Beam_qp2", 0.0)
        z.bouton("Ajouter cette charge", self._ajoute_charge_rapide)

    def _saisie_actions_imposees(self, z: Zone) -> None:
        z.legende(
            "Ressort : appui élastique de raideur k (0 = appui rigide), le déplacement vaut −R/k. Tassement : déplacement "
            "imposé de l'appui (mm, > 0 dans le sens de l'axe, y > 0 vers le haut). L'appui est désigné par son nom "
            "(colonne Nom du tableau Appuis)."
        )
        z.table("Beam", "supx", [texte_col("name", "Appui (nom)"), nombre_col("k", "Ressort k (kN/m)"),
                                 nombre_col("dx", "Tassement x (mm)"), nombre_col("dy", "Tassement y (mm)"),
                                 nombre_col("dz", "Tassement z (mm)")])  # fmt: skip
        z.table("Beam", "hg", [nombre_col("pos", "Position (m)"), texte_col("name", "Nom")],
                help="Rotule intermédiaire : le moment de flexion y est nul au point choisi (poutre Gerber) ; la pente y "
                "est discontinue. Pas sur un appui.")  # fmt: skip
        z.legende(
            "Température : α vient du matériau. ΔT uniforme : allongement α·ΔT (efforts si la poutre est empêchée de "
            "s'allonger). Gradient : T(face +y) − T(face −y), la hauteur est 2·|y|max (idem z) ; fibre chaude en haut : la "
            "poutre se cambre."
        )
        z.num("Beam", "thDT", "ΔT uniforme", "°C")
        z.num("Beam", "thGy", "Gradient selon y : T(+y) − T(−y)", "°C")
        z.num("Beam", "thGz", "Gradient selon z : T(+z) − T(−z)", "°C")
        z.check("Beam", "selfw", "Poids propre (ρ·S·g, cas G)",
                help="Ajoute une charge répartie descendante ρ·S·g sur toute la poutre (ρ du matériau choisi).")  # fmt: skip

    def _saisie_combinaisons(self, z: Zone) -> None:
        z.legende(
            "Chaque charge porte un cas (colonne Cas). « Calculer » additionne tous les cas avec le coefficient 1. "
            "« Calculer les combinaisons » résout chaque ligne avec ses coefficients puis donne l'enveloppe."
        )
        z.table("Beam", "combo", [texte_col("name", "Combinaison"), nombre_col("gG", "γG"), nombre_col("gQ", "γQ"),
                                  nombre_col("gW", "γW"), nombre_col("gS", "γS")])  # fmt: skip

        def apres(T) -> None:
            env = T.iloc[-1]
            self._etat(
                f"Combinaisons : {len(T) - 1} calculée(s), enveloppe Kt·σ max = {env['Kt·σ max (MPa)']:.4g} MPa "
                f"({env['Résistance']})",
                env["Résistance"] == "vérifié",
                "BeamCombo",
            )

        def lance() -> None:
            s, dm = copy.deepcopy(state.saisie("Beam")), state.dm()
            self.essaie("BeamCombo", lambda: beam_services.computeCombinations(s, dm), apres)

        z.bouton("Calculer les combinaisons", lance)

    def _saisie_charge_mobile(self, z: Zone) -> None:
        z.legende(
            "Un convoi d'essieux verticaux (Fy) traverse la poutre. La poutre est résolue pour chaque position, puis "
            "l'enveloppe de Mfz, Ty et des réactions est tracée. Essieux de gauche à droite, F < 0 = vers le bas."
        )
        z.text("Beam", "mvP", "Essieux (kN, de gauche à droite)")
        z.text("Beam", "mvE", "Écartement(s) entre essieux (m)")
        z.num("Beam", "mvN", "Positions de base du convoi (+ positions critiques)", "", min_value=2, entier=True)
        z.check("Beam", "mvFixed", "Ajouter les charges fixes saisies")

        def apres(r) -> None:
            e = r[1]["extrema"]
            self._etat(
                f"Charge mobile ({r[1]['positions']} positions) : Mfz de {e['Mmin'] / 1e3:.4g} à "
                f"{e['Mmax'] / 1e3:.4g} kN·m, Ty de {e['Tmin'] / 1e3:.4g} à {e['Tmax'] / 1e3:.4g} kN",
                None,
                "BeamMov",
            )

        def lance() -> None:
            s, dm = copy.deepcopy(state.saisie("Beam")), state.dm()
            self.essaie("BeamMov", lambda: beam_design.computeMovingLoad(s, dm), apres)

        z.bouton("Calculer l'enveloppe de la charge mobile", lance)

    def _saisie_profile(self, z: Zone) -> None:
        z.choice("Beam", "pfam", "Famille de profilés", FAMILLES)
        z.num("Beam", "pdef", "Flèche max L / … (0 = ignorée)", "",
              help="Exemple : 300 impose f ≤ L/300. En plus de la condition de résistance Kt·σ ≤ Re/s.", min_value=0.0)  # fmt: skip

        def apres(r) -> None:
            best, fam = r[1], state.saisie("Beam")["pfam"]
            if best is None:
                self._etat(f"Aucun profilé {fam} ne vérifie ce chargement : essayer une autre famille.", False, "BeamProf")
            else:
                self._etat(f"Profilé {fam} le plus léger qui vérifie : {best['Name']}. La saisie de la section est inchangée.",
                           True, "BeamProf")  # fmt: skip

        def lance() -> None:
            s, dm = copy.deepcopy(state.saisie("Beam")), state.dm()
            self.essaie("BeamProf", lambda: beam_design.findLightestProfile(s, dm, s["pfam"], s["pdef"]), apres)

        z.bouton("Chercher le profilé le plus léger", lance)

    def _saisie_eurocode(self, z: Zone) -> None:
        z.legende(
            "Profilés IPE, HEA, HEB, IPN et sections en I, classes 1 à 3, fy = Re : flexion, tranchant, voilement de l'âme "
            "par cisaillement, déversement, flambement et interaction N + M (6.3.3, flexion autour de l'axe fort). "
            "Efforts par défaut : enveloppe des combinaisons (ELU γG = 1,35, γQ = 1,5 dans l'exemple). « Dernier "
            "Calculer » additionne les cas avec le coefficient 1 : efforts non pondérés, verdict seulement indicatif."
        )
        z.choice("Beam", "na", "Annexe nationale", list(ANNEXES), format_func=ANNEXES.get,
                 help="La France retient γM0 = γM1 = 1,0 et γM2 = 1,25 : mêmes valeurs que l'EN. Pour un autre pays, saisir "
                 "ses valeurs.", on_change=self._applique_annexe)  # fmt: skip
        z.num("Beam", "gM0", "γM0 (-), résistance des sections")
        z.num("Beam", "gM1", "γM1 (-), stabilité (déversement)")
        z.num("Beam", "Cmy", "Cmy (-), moment équivalent, flambement (1 = prudent)",
              help="Tableau B.3 de l'EN 1993-1-1 : 0,6 + 0,4ψ (moment linéaire, ψ = rapport des moments d'extrémité), "
              "0,95 à 0,9 (charge répartie). Entre 0,4 et 1.")  # fmt: skip
        z.num("Beam", "CmLT", "CmLT (-), moment équivalent, déversement (1 = prudent)",
              help="Idem pour le déversement. Entre 0,4 et 1 ; 1 est toujours du côté de la sécurité.")  # fmt: skip
        z.num("Beam", "Lcr", "Lcr : longueur entre maintiens latéraux (m, 0 = L)")
        z.num("Beam", "LcrF", "Lcr,y : longueur de flambement dans le plan fort (m, 0 = L)",
              help="Flambement autour de l'axe fort (y-y) : les entretoises latérales n'y changent rien. Par défaut (0), "
              "la longueur de la poutre.")  # fmt: skip
        z.num("Beam", "C1", "C1 : forme du moment (1 = uniforme, prudent)",
              help="NCCI SN003 : 1,13 pour une charge uniforme sur appuis simples ; 1,35 pour une charge ponctuelle "
              "centrée ; 1,77 pour des moments d'extrémité ψ = 0.")  # fmt: skip
        z.choice("Beam", "ecsrc", "Efforts de calcul", ["enveloppe", "courant"],
                 format_func={"enveloppe": "Enveloppe des combinaisons (ELU)",
                              "courant": "Dernier « Calculer » (non pondéré, indicatif)"}.get)  # fmt: skip
        z.legende(NON_VERIFIE)
        z.legende("E du matériau choisi : 190 GPa pour les aciers du cours ; l'EN 1993-1-1 (§3.2.6) prend 210 GPa.")

        def apres(r) -> None:
            e = r[0]
            if not e["okAll"]:
                verdict = "NON vérifié"
            elif e["pondere"]:
                verdict = "vérifié"
            else:  # efforts non pondérés : pas de verdict « vérifié »
                verdict = "indicatif, efforts non pondérés : refaire avec l'enveloppe ELU"
            texte = (
                f"Eurocode 3 : classe {e['class']['class']}, MEd/MRd = {e['ratioM']:.3f}, "
                f"VEd/Vpl,Rd = {e['ratioV']:.3f}, MEd/Mb,Rd = {e['ltb']['ratio']:.3f} ({verdict})"
            )
            if e["inter"]:
                texte += f", N + M (6.61/6.62) = {e['inter']['ratio']:.3f}"
            self._etat(texte, None if e["okAll"] and not e["pondere"] else bool(e["okAll"]), "BeamEC3")

        def lance() -> None:
            s, dm = copy.deepcopy(state.saisie("Beam")), state.dm()
            source = "enveloppe" if s["ecsrc"] == "enveloppe" else "poutre"
            self.essaie("BeamEC3", lambda: beam_design.checkEurocode(s, dm, source), apres)

        z.bouton("Vérifier selon l'Eurocode 3", lance)

    def _saisie_fatigue(self, z: Zone) -> None:
        z.num("Beam", "fR", "R = σmin / σmax (-1 alterné, 0 répété)", "")
        z.num("Beam", "fka", "ka : état de surface", "-",
              help="Poli 1 ; usiné 0,7 à 0,9 ; laminé 0,6 à 0,8 ; brut de forge 0,4 à 0,6 (acier).")  # fmt: skip
        z.num("Beam", "fkb", "kb : effet de taille", "-",
              help="Petite pièce (d ≤ 8 mm) 1 ; 0,85 à 0,9 pour 10 à 50 mm ; 0,7 à 0,8 au-delà.")  # fmt: skip

        def apres(r) -> None:
            s, n = state.saisie("Beam"), r[0]["n"]
            ok = n >= s["s"]
            self._etat(f"Fatigue (Goodman) : n = {n:.3g} pour s = {s['s']:.3g} ({'vérifié' if ok else 'NON vérifié'})", ok, "BeamFat")

        def lance() -> None:
            s, dm = copy.deepcopy(state.saisie("Beam")), state.dm()
            self.essaie("BeamFat", lambda: beam_design.checkFatigue(s, dm), apres)

        z.bouton("Vérifier la fatigue", lance)

    def volets(self) -> list[Volet]:
        return [
            Volet("poutre", "Poutre et matériau", "Haut", True, self._saisie_poutre_et_section),
            Volet("section", "Section", "Haut", True, self._saisie_section),
            Volet("charges", "Appuis et charges", "Haut", True, self._saisie_charges),
            Volet("options", "Calcul et affichage", "Haut", True, self._saisie_options),
            Volet("rapide", "Charge rapide (ajoute une ligne au tableau des charges réparties)", "Bas", False,
                  self._saisie_charge_rapide),
            Volet("imposees", "Ressorts, tassements, rotules, température, poids propre", "Bas", False,
                  self._saisie_actions_imposees),
            Volet("combos", "Combinaisons de cas (G permanentes, Q exploitation, W vent, S neige)", "Bas", False,
                  self._saisie_combinaisons),
            Volet("mobile", "Charge mobile (convoi d'essieux, enveloppe)", "Bas", False, self._saisie_charge_mobile),
            Volet("profile", "Dimensionnement : profilé le plus léger", "Bas", False, self._saisie_profile),
            Volet("ec3", "Eurocode 3 simplifié (flexion + tranchant)", "Bas", False, self._saisie_eurocode),
            Volet("fatigue", "Fatigue (Goodman)", "Bas", False, self._saisie_fatigue),
        ]  # fmt: skip

    def saisie(self, z: Zone) -> None:
        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Beam")
        z.section(lambda s: self._synthese(s, state.result("Beam")), suit=True)
        c = z.colonnes(2)
        c[0].bouton("↶ Annuler", lambda: self._historique(-1),
                    aide="Annule la dernière modification de la saisie (retour à l'état du dernier calcul ou exemple).")  # fmt: skip
        c[1].bouton("↷ Rétablir", lambda: self._historique(1))
        dossier.file_bar(z, "Beam")
        dossier.example_picker(z, "Beam")
        panels(z, "Beam", self.volets())
        z.bouton("Envoyer au tenseur (point le plus sollicité)", self._envoie_tenseur)
        z.legende("Les efforts de la poutre se reprennent dans Sections : « Efforts en s » et « Efforts au point critique ».")
        self._affiche_message(z)

    # --- résultats -----------------------------------------------------------------------------------------------------

    def _synthese(self, z: Zone, res: dict) -> None:
        """Valeurs clés du dernier calcul (kN, kN·m, mm, MPa) affichées sous « Calculer »."""
        if res is None:
            return
        if not state.is_current("Beam"):
            z.legende("(saisie modifiée : cliquez sur Calculer)")
            return
        e, bd, sh = res["sol"]["extrema"], res["check"]["bend"], res["check"]["shear"]
        reaction = max((float(np.linalg.norm([r["Rx"], r["Ry"], r["Rz"]])) for r in res["sol"]["reactions"]), default=0.0)
        ok = bool(res["check"]["ok"])
        tranchant = "tranchant non vérifié" if sh is None else f"VEd/Vpl,Rd {sh['ratio']:.3g}"
        z.synthese([
            {"label": "Réaction max", "value": f"{reaction / 1e3:.4g} kN"},
            {"label": "|T| max", "value": f"{max(abs(e[c][b]) for c in ('Ty', 'Tz') for b in ('max', 'min')) / 1e3:.4g} kN"},
            {"label": "|Mf| max", "value": f"{max(abs(e[c][b]) for c in ('Mfy', 'Mfz') for b in ('max', 'min')) / 1e3:.4g} kN·m"},
            {"label": "Flèche max", "value": f"{res['defl']['integration']['fmax'] * 1e3:.4g} mm"},
            {
                "label": "Kt·σ max",
                "value": f"{bd['sigmaMaxKt'] / 1e6:.4g} MPa",
                "delta": f"{'vérifié' if ok else 'NON vérifié'} (σadm {bd['sigmaAdm'] / 1e6:.4g} ; {tranchant})",
                "delta_color": "green" if ok else "red",
            },
        ])  # fmt: skip

    def _schema(self, z: Zone, res: dict | None) -> None:
        """Schéma de la poutre : avec réactions si le calcul date de la saisie actuelle, sinon aperçu de la saisie."""
        a_jour = res is not None and state.is_current("Beam")
        try:
            if a_jour:
                fig = beam_plots.beamSchematic(res["model"], res["sol"])
            else:
                fig = beam_plots.beamSchematic(beam_services.buildBeamModel(state.saisie("Beam"), state.dm()), None)
        except Exception as err:  # noqa: BLE001 : saisie incomplète, l'aperçu est seulement omis
            z.legende(f"Aperçu indisponible : {err}")
            return
        z.plot(fig)
        if res is None:
            if state.v.get("Beam_etat") is None:
                z.legende(
                    "Aperçu de la poutre saisie, mis à jour à chaque modification. "
                    "Cliquez sur « Calculer » pour les diagrammes et les résultats."
                )
        elif not a_jour:
            z.legende(
                "Le schéma suit la saisie. Les diagrammes et les résultats datent du dernier « Calculer » : "
                "cliquez dessus pour les actualiser."
            )

    def _equations_par_troncon(self, z: Zone, sol: dict, comps: list[str]) -> None:
        for k, eq in enumerate(sol["equations"], start=1):
            z.texte(f"**Tronçon {k} : s ∈ [{eq['s1']:.4g} ; {eq['s2']:.4g}] m**")
            z.formules([eq[c] for c in comps])

    def _affiche_profiles(self, z: Zone) -> None:
        """Tableau des essais et bouton « Utiliser ce profilé »."""
        T, best = state.result("BeamProf")
        z.tableau(T)
        if best is not None:
            z.bouton(f"Utiliser le profilé {best['Name']}", self._utilise_profile)

    def visualisation(self, z: Zone) -> None:
        """Graphiques (schéma en premier), ligne d'état, dossier de validation, onglets de résultats."""
        res = state.result("Beam")
        r = state.result
        etat = state.v.get("Beam_etat")
        if etat is not None and not state.is_current(etat[2], source="Beam"):
            del state.v["Beam_etat"]  # résultat effacé ou saisie changée : le verdict ne vaut plus
        graphes = [("Schéma", lambda c: self._schema(c, res))]
        tables = []
        if res is not None:
            sol, d, t = res["sol"], res["defl"], res["tables"]
            comps = state.v.get("Beam.comps") or None
            if not comps:
                comps = [c for c in COMPOSANTES if any(np.any(k != 0) for k in asPP(sol[c]).coefs)] or ["Ty", "Mfz"]
            graphes += [
                ("Diagrammes", lambda c: c.plot(beam_plots.internalForces(sol, comps))),
                ("Déformée α(s), v(s)", lambda c: c.plot(beam_plots.deflection(res["model"], d))),
                ("Équations par tronçon", lambda c: self._equations_par_troncon(c, sol, comps)),
                ("Explications du calcul", lambda c: dossier.explanation_panel(c, "Beam")),
            ]
            tables += [
                ("Rapport", lambda c: c.rapport(res["rapport"])),
                ("Réactions", lambda c: c.tableau(t["Réactions"])),
                ("Équations", lambda c: (c.tableau(t["Équations"]), c.formules(sol["latex"]))),
                ("Flèche : 4 méthodes", lambda c: c.tableau(t["Flèche : 4 méthodes"])),
                ("Énergie", lambda c: c.tableau(t["Énergie"])),
                ("Contraintes", lambda c: c.tableau(t["Contraintes"])),
            ]

        def titre(nom: str, cle: str) -> str:  # résultat annexe d'une saisie plus ancienne : signalé dans l'onglet
            return nom if state.is_current(cle, source="Beam") else f"{nom} (saisie modifiée depuis)"

        if r("BeamCombo") is not None:
            graphes.append(("Combinaisons", lambda c: c.plot(beam_plots.combinations(r("BeamCombo")))))
            tables.append((titre("Combinaisons", "BeamCombo"), lambda c: c.tableau(r("BeamCombo"))))
        if r("BeamMov") is not None:
            graphes.append(("Charge mobile", lambda c: c.plot(beam_plots.movingEnvelope(r("BeamMov")[1]))))
            tables.append((titre("Charge mobile", "BeamMov"), lambda c: c.tableau(r("BeamMov")[0])))
        if r("BeamProf") is not None:
            tables.append((titre("Profilés", "BeamProf"), self._affiche_profiles))
        if r("BeamEC3") is not None:
            tables.append((titre("Eurocode 3", "BeamEC3"), lambda c: c.tableau(r("BeamEC3")[1])))
        if r("BeamFat") is not None:
            tables.append((titre("Fatigue", "BeamFat"), lambda c: c.tableau(r("BeamFat")[1])))
        if any(r(c) is not None and not state.is_current(c, source="Beam") for c in ANNEXES_CLES):
            z.legende(
                "Les onglets marqués « saisie modifiée depuis » datent d'une saisie précédente : relancez leur bouton "
                "(Combinaisons, Eurocode 3…) pour les actualiser."
            )
        tables = z.graphs("Beam_graphes_onglets", graphes, dessous=("Équations par tronçon",)) + tables
        texte, ok, _ = state.v.get("Beam_etat", (None, None, None))
        if texte:
            z.statut(texte, ok)
        dossier.validation_button(z, "Beam")
        if res is None:  # avant le premier calcul : le panneau dit où trouver les équations
            dossier.explanation_panel(z, "Beam")
        if tables:
            z.onglets(dict(tables))

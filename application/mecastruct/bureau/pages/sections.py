"""Page « Sections droites » : caractéristiques de la section (3 méthodes), contraintes σ(y) et τ(y), transfert.

Port de l'onglet « Sections » de MecaStruct_App.m (buildSectionsTab, computeSection, applySectionPreset,
useSectionForBeam). Disposition commune aux pages de calcul : saisie à gauche, résultats à droite.
"""

import copy

import pandas as pd

from mecastruct.bureau import dossier, state, transfert
from mecastruct.bureau.page_calcul import PageCalcul, synthese_resultat
from mecastruct.bureau.widgets import Zone, nombre_col
from mecastruct.core import geometry
from mecastruct.core.data_manager import sectionPresets
from mecastruct.plots import section_plots
from mecastruct.services import beam_design, beam_services, compute

# Dimensions pertinentes par type (port de relevantDims de MecaStruct_App.m)
DIMENSIONS_PAR_TYPE = {
    "rectangle": ("b", "h"),
    "disque": ("D",),
    "couronne": ("D", "d"),
    "rectangle_creux": ("B", "H", "t"),
    "I": ("h", "b", "tw", "tf"),
    "T": ("h", "b", "tw", "tf"),
    "U": ("h", "b", "tw", "tf"),
    "L": ("h", "b", "t"),
}
LIBELLES_DIMENSIONS = {
    "b": "b — largeur selon z (mm)",
    "h": "h — hauteur selon y (mm)",
    "D": "D — diamètre extérieur (mm)",
    "d": "d — diamètre intérieur (mm)",
    "B": "B — largeur (mm)",
    "H": "H — hauteur (mm)",
    "t": "t — épaisseur (mm)",
    "tw": "tw = a — âme (mm)",
    "tf": "tf = e — aile (mm)",
}
TYPE_PROFILE = "profile"
TYPE_COMPOSITE = "composite"


class PageSections(PageCalcul):
    titre = "Sections"
    fiche = "geometrie"
    tab = "Sec"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Sec")), state.dm()
        self.calcule_onglet("Sec", lambda: compute.computeSection(s, dm))

    def _applique_preset(self) -> None:
        """Règle le type et les dimensions sur le tube ou la cornière choisi."""
        nom = state.v.get("Sec.preset")
        preset = next(p for p in sectionPresets() if p["name"] == nom)
        s = state.saisie("Sec")
        s["type"] = preset["type"]
        s.update({cle: float(valeur) for cle, valeur in preset["dims"].items()})
        self.rafraichirSaisie()

    def _envoie_vers_poutres(self) -> None:
        """Transmet la section calculée aux saisies Poutres et Flambage."""
        envoi = transfert.envoie_section(state.dm())
        if envoi is not None:
            state.v["Sec.envoye"] = envoi
        self.surSaisie()

    def _efforts_poutre(self, mode: str) -> None:
        """Remplit N, Mfz, Mfy, Ty avec les efforts de la poutre, recalculée d'abord (loadFromBeam de MATLAB).

        mode : 'abscisse' (coupure en s0) ou 'max' (point le plus sollicité). Le message est gardé dans « Sec_msg ».
        """
        dm, cible = state.dm(), state.saisie("Sec")
        try:
            res = beam_services.computeBeam(state.saisie("Beam"), dm)
            state.set_result("Beam", res)
            nouvelle = beam_design.loadFromBeam(cible, res, "Sec", mode)
        except Exception as err:  # noqa: BLE001 : abscisse hors de la poutre, poutre incalculable…
            state.v["Sec_msg"] = ("error", str(getattr(err, "message", err)))
            self.rafraichirSaisie()
            return
        state.v["saisie"]["Sec"] = nouvelle
        note = "⚠ Résultats NON fiables (hyperstatique, Iyz ≠ 0) — " if res["unreliable"] else ""
        msg = (
            f"{note}Efforts lus sur la poutre en s = {nouvelle['s0']:.4g} m : N = {nouvelle['N']:.4g} kN, "
            f"Mfz = {nouvelle['Mfz']:.4g} kN·m, Mfy = {nouvelle['Mfy']:.4g} kN·m"
        )
        r = state.result("Sec")
        beam = state.saisie("Beam")
        if r is not None:  # pas de != sur les sections : une section composée contient des tableaux NumPy
            sec = r["result"]["sec"]
            # profilé du catalogue : le transfert envoie l'Iz tabulé (sectionToBeamInput), on compare à la même source
            iz_sec = (geometry.tabulated(sec) if sec["type"] == TYPE_PROFILE else r["result"]["P"])["Iz"] * 1e12
            if abs(beam["Iz"] - iz_sec) > 1e-3 * iz_sec:
                msg += (
                    f"  ⚠ Attention : la section de la page Sections (Iz = {iz_sec:.4g} mm⁴) diffère de celle de la "
                    f"poutre (Iz = {beam['Iz']:.4g} mm⁴) : les contraintes ne concernent pas la même section."
                )
        state.v["Sec_msg"] = ("info", msg)
        state.reset_widgets("Sec")

    def _saisie_geometrie(self, z: Zone) -> None:
        """Type de section, profilé du catalogue, préréglages, dimensions pertinentes et sections composées."""
        dm, saisie = state.dm(), state.saisie("Sec")
        types = geometry.sectionTypes()
        libelles = {t["type"]: t["label"] for t in types}
        type_choisi = z.choice("Sec", "type", "Type de section", list(libelles), format_func=libelles.get,
                               on_change=self.rafraichirSaisie)  # fmt: skip
        if type_choisi == TYPE_PROFILE:
            fam = z.choice("Sec", "fam", "Famille de profilé", dm.listProfileFamilies(), on_change=self.rafraichirSaisie)
            profils = dm.listProfiles(fam)
            if saisie["prof"] not in profils:
                saisie["prof"] = profils[0]
            z.choice("Sec", "prof", "Profilé du catalogue", profils)
        z.legende("Tube ou cornière courant")
        z.liste("Préréglage", [p["name"] for p in sectionPresets()], "Sec.preset")
        z.bouton("Remplir les dimensions du préréglage", self._applique_preset)
        if type_choisi in DIMENSIONS_PAR_TYPE:
            for champ in DIMENSIONS_PAR_TYPE[type_choisi]:
                z.num("Sec", champ, LIBELLES_DIMENSIONS[champ], "", min_value=0.0)
        if type_choisi == TYPE_COMPOSITE:
            z.legende("Rectangles pleins (mm) : chaque ligne donne z1, z2, y1, y2 (repère O1, coin bas-gauche).")
            colonnes = [nombre_col(cle, f"{cle} (mm)") for cle in ("z1", "z2", "y1", "y2")]
            z.table("Sec", "rects", colonnes)
            z.legende("Trous rectangulaires (mm), même format.")
            z.table("Sec", "holes", colonnes)

    def _saisie_efforts_et_methode(self, z: Zone) -> None:
        """Méthode intégrale, matériau, efforts N, Mfz, Mfy, Ty, et Kt pour les contraintes."""
        z.choice("Sec", "mode", "Méthode intégrale", ["symbolique", "numerique"],
                 format_func=lambda m: {"symbolique": "symbolique (int)", "numerique": "numérique (integral2)"}[m])  # fmt: skip
        z.choice("Sec", "mat", "Matériau", state.dm().listMaterials())
        z.num("Sec", "N", "N : traction > 0", "kN")
        z.num("Sec", "Mfz", "Mfz : plan (x, y), fibres du haut comprimées si > 0", "kN·m")
        z.num("Sec", "Mfy", "Mfy : plan (x, z), fibres z > 0 tendues si > 0", "kN·m")
        z.num("Sec", "Ty", "Ty : tranchant en y", "kN")
        z.texte("**… ou reprendre les efforts de la poutre calculée**")
        z.num("Sec", "s0", "s sur la poutre", "m", help="Abscisse de la coupure dans la page Poutres (de 0 à L).",
              min_value=0.0)  # fmt: skip
        colonnes = z.colonnes(2)
        colonnes[0].bouton("Efforts en s", lambda: self._efforts_poutre("abscisse"),
                           aide="Remplit N, Mfz, Mfy, Ty avec les efforts de la poutre à l'abscisse s.")  # fmt: skip
        colonnes[1].bouton("Efforts au point critique", lambda: self._efforts_poutre("max"),
                           aide="Remplit N, Mfz, Mfy, Ty avec les efforts de la section la plus sollicitée de la poutre.")  # fmt: skip
        z.messageGarde("Sec_msg")
        z.num("Sec", "Kt", "Kt (-)", min_value=1.0)

    def saisie(self, z: Zone) -> None:
        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Sec")
        dossier.file_bar(z, "Sec")
        dossier.example_picker(z, "Sec")
        z.repliable("Type de section", ouvert=True, rendu=self._saisie_geometrie)
        z.repliable("Matériau, méthode et efforts pour σ(y) et τ(y)", ouvert=True, rendu=self._saisie_efforts_et_methode)

    def _apercu_section(self, z: Zone) -> None:
        """Dessin de la section d'après la saisie actuelle (sans contraintes) ; rien si la saisie est incomplète."""
        try:
            sec = compute._sectionFromSaisie(state.saisie("Sec"), state.dm())
            fig = section_plots.section(sec, geometry.analytical(sec))
        except Exception as err:  # noqa: BLE001 : saisie incomplète, l'aperçu est seulement omis
            z.legende(f"Aperçu indisponible : {err}")
            return
        z.plot(fig)

    def _graphe_section(self, z: Zone, res: dict, a_jour: bool) -> None:
        """Dessin de la section : celui du calcul s'il date de la saisie actuelle, sinon un aperçu de la saisie."""
        if a_jour:
            z.plot(section_plots.section(res["sec"], res["P"]))
            return
        self._apercu_section(z)
        z.legende(
            "Le dessin suit la saisie. Les contraintes et les tableaux datent du dernier « Calculer » : "
            "cliquez dessus pour les actualiser."
        )

    def _resultats(self, z: Zone, res: dict, tables: dict, statut: str, a_jour: bool) -> None:
        """Graphiques (section, contraintes) puis résultats (comparaison, Huygens, cisaillement, rapport, formules)."""
        sec, P = res["sec"], res["P"]
        z.graphs(
            "Sec_graphes_onglets",
            [
                ("Section", lambda c: self._graphe_section(c, res, a_jour)),
                ("Contraintes σ(y) et τ(y)", lambda c: c.plot(section_plots.sectionStress(sec, P, res["bend"], res["jour"]))),
            ],
        )
        z.succes(statut)

        def huygens(c: Zone) -> None:
            if "Tableau de Huygens" in tables:
                c.tableau(tables["Tableau de Huygens"])
            else:
                c.legende("Pas de tableau de Huygens pour cette section.")

        def facteurs(c: Zone) -> None:
            f = {k: v for k, v in P["shear"].items() if isinstance(v, (int, float, str))}
            c.tableau(pd.DataFrame([f]).T.rename(columns={0: "Valeur"}), index=True)

        z.onglets(
            {
                "Comparaison des méthodes": lambda c: c.tableau(tables["Comparaison des méthodes"]),
                "Tableau de Huygens": huygens,
                "Facteurs de cisaillement": facteurs,
                "Rapport": lambda c: c.rapport(res["rapport"]),
                "Formules": lambda c: c.formules(P["latex"]),
            }
        )
        z.bouton("Utiliser cette section pour une poutre", self._envoie_vers_poutres)
        envoi = state.v.pop("Sec.envoye", False)
        if envoi:
            z.succes("Section transmise aux pages Poutres et Flambage.")
            if envoi == "principaux":
                z.info("Iyz ≠ 0 : Flambage reçoit les moments principaux I1 et I2 ; Poutres garde Iz, Iy et Iyz.")
            z.lien("poutres", "📏 Ouvrir Poutres")
            z.lien("flambage", "📐 Ouvrir Flambage")

    def visualisation(self, z: Zone) -> None:
        r = state.result("Sec")
        if r is None:
            z.sousTitre("Section")
            self._apercu_section(z)
            z.legende("Aperçu mis à jour à chaque modification. Cliquez sur « Calculer » pour les résultats.")
        else:
            self._resultats(z, r["result"], r["tables"], r["status"], state.is_current("Sec"))
        synthese_resultat(z, "Sec")
        dossier.validation_button(z, "Sec")
        dossier.explanation_panel(z, "Sec")

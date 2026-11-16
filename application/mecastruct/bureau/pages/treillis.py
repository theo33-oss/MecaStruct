"""Page « Treillis » : treillis articulé plan (efforts dans les barres, réactions, déplacements).

Port de l'onglet « Treillis » de MecaStruct_App.m (buildTrussTab, computeTruss). Le moteur et l'interface MATLAB sont
plans (2D) : la saisie 3D de la fiche n'est pas portée.
"""

import copy

from mecastruct.bureau import dossier, state
from mecastruct.bureau.page_calcul import PageCalcul, modes_resultat, synthese_suivie
from mecastruct.bureau.widgets import Zone, case_col, noeud_col, nombre_col, texte_col
from mecastruct.plots import other_plots
from mecastruct.services import compute


class PageTreillis(PageCalcul):
    titre = "Treillis"
    fiche = "treillis"
    tab = "Tr"

    def calculer(self) -> None:
        s, dm = copy.deepcopy(state.saisie("Tr")), state.dm()
        self.calcule_onglet("Tr", lambda: compute.computeTruss(s, dm))

    def saisie(self, z: Zone) -> None:
        dm = state.dm()
        z.bouton("Calculer", self.calculer, primaire=True)
        z.erreurGardee("erreur.Tr")
        synthese_suivie(z, "Tr")
        dossier.file_bar(z, "Tr")
        dossier.example_picker(z, "Tr")

        def corps(c: Zone) -> None:
            c.choice_materiau("Tr", ["E", "Re"], dm)
            c.num("Tr", "E", "E", "GPa")
            c.num("Tr", "Re", "Re", "MPa", min_value=0.0)
            c.num("Tr", "S", "S, aire d'une barre", "mm²", min_value=0.0)
            c.num("Tr", "Imin", "Imin, moment quadratique minimal d'une barre (0 = flambage non vérifié)", "mm⁴",
                  help="Toutes les barres ont la même section. Flambage d'Euler des barres comprimées (articulées aux "
                       "deux bouts). Tube Ø60 × 3 : environ 200 000 mm⁴.", min_value=0.0)  # fmt: skip
            c.num("Tr", "s", "Coefficient de sécurité s", "", min_value=0.0)
            c.num("Tr", "scale", "Amplification déformée (0 = auto)", "", min_value=0.0)
            c.texte("**Nœuds** (coordonnées en m)")
            c.table("Tr", "nodes", [texte_col("name", "Nom"), nombre_col("x", "x (m)"), nombre_col("y", "y (m)")])
            c.texte("**Barres** (numéros des nœuds, à partir de 1)")
            c.table("Tr", "bars", [noeud_col("i", "Nœud i"), noeud_col("j", "Nœud j", 2)])
            c.texte("**Appuis** (ddl bloqués)")
            c.table("Tr", "sup", [noeud_col("node", "Nœud"), case_col("bx", "Bloqué x"), case_col("by", "Bloqué y")])
            c.texte("**Charges nodales**")
            c.table(
                "Tr",
                "loads",
                [noeud_col("node", "Nœud"), nombre_col("Fx", "Fx (kN)"), nombre_col("Fy", "Fy (kN)", -10.0)],
            )

        z.repliable("Matériau, section et nœuds", ouvert=True, rendu=corps)

    def _figure(self, z: Zone, res: dict | None):
        """Treillis dessiné : avec efforts si le calcul date de la saisie actuelle, sinon aperçu de la saisie."""
        saisie = state.saisie("Tr")
        if res is None or not state.is_current("Tr"):
            try:
                return other_plots.truss(compute._readTruss(saisie))
            except Exception as err:  # noqa: BLE001 : saisie incomplète, l'aperçu est seulement omis
                z.legende(f"Aperçu indisponible : {err}")
                return None
        r = res["result"]
        return other_plots.truss(r["truss"], r["tsol"], saisie["scale"] if saisie["scale"] > 0 else None)

    def visualisation(self, z: Zone) -> None:
        resultat = state.result("Tr")
        if resultat is not None:
            modes_resultat(z, "Tr", resultat, ok=resultat["ok"])
        dossier.validation_button(z, "Tr")
        figure = self._figure(z, resultat)
        if figure is not None:
            z.plot(figure)
        if resultat is None:
            z.legende(
                "Aperçu du treillis saisi, mis à jour à chaque modification. Cliquez sur « Calculer » pour les efforts."
            )
        elif not state.is_current("Tr"):
            z.legende(
                "Le dessin suit la saisie. Les efforts et les tableaux datent du dernier « Calculer » : "
                "cliquez dessus pour les actualiser."
            )
        dossier.explanation_panel(z, "Tr")
        if resultat is not None:
            t = resultat["tables"]
            z.onglets(
                {
                    "Barres": lambda c: c.tableau(t["Barres"]),
                    "Réactions": lambda c: c.tableau(t["Réactions"]),
                    "Déplacements": lambda c: c.tableau(t["Déplacements"]),
                    "Rapport": lambda c: c.rapport(resultat["result"]["rapport"]),
                    "Formules": lambda c: c.formules(resultat["result"]["tsol"]["latex"]),
                }
            )

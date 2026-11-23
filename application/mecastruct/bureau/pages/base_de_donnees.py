"""Page « Matériaux et profilés » : matériaux, profilés, pressions de matage, abaques Kt, données utilisateur, documents.

Port des onglets de MecaStruct_App.m (buildDatabaseTab, refreshMaterialTable, refreshProfileTable, addMaterialFromForm,
addProfileFromForm, computeKt). Unités d'affichage comme MATLAB : GPa, MPa, mm, cm², cm⁴, cm³.
Les ajouts de l'utilisateur ne sont conservés que dans le fichier JSON enregistré.
"""

import copy
import json
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from PySide6.QtWidgets import QMessageBox

from mecastruct.bureau import state
from mecastruct.bureau.widgets import Page, Zone
from mecastruct.core import kt_mohr
from mecastruct.core.errors import MecaStructError
from mecastruct.plots.other_plots import ktChart
from mecastruct.services import compute
from mecastruct.services.limits import checkLimits

DOCS = Path(__file__).resolve().parents[3] / "aide"


def filtre_materiaux(T: pd.DataFrame, categories: list, recherche: str) -> pd.DataFrame:
    """Matériaux des catégories cochées (aucune cochée = aucun résultat) dont le nom contient la recherche (espaces rognés)."""
    vue = T[T["Category"].isin(categories)]
    recherche = (recherche or "").strip()
    if recherche:
        vue = vue[vue["Name"].str.contains(recherche, case=False, regex=False)]
    return vue


def _confirme(parent, texte: str) -> bool:
    """Demande une confirmation (Oui / Non, Non par défaut) avant une suppression."""
    rep = QMessageBox.question(parent, "Confirmer la suppression", texte,
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)  # fmt: skip
    return rep == QMessageBox.StandardButton.Yes


class PageBaseDeDonnees(Page):
    def _message_suivant(self, texte: str) -> None:
        """Message affiché au prochain affichage de la page (après un ajout qui rafraîchit les tableaux)."""
        state.v["db.message"] = ("succes", texte)
        self.rafraichirTout()

    def rendre(self, z: Zone) -> None:
        z.titre("Matériaux et profilés")
        z.intro("Base de matériaux et de profilés normalisés.")
        z.messageGarde("db.message")
        z.onglets(
            {
                "Matériaux": self._materiaux,
                "Profilés": self._profiles,
                "Pressions de matage": self._matage,
                "Abaques Kt": self._abaques_kt,
                "Mes données": self._donnees_utilisateur,
                "Documents": self._documents,
            },
            cle="onglet.base_de_donnees",
        )

    def _materiaux(self, z: Zone) -> None:
        """Tableau des matériaux (filtre par catégorie et recherche), formulaire d'ajout, suppression d'un ajout."""
        dm = state.dm()
        T = dm.Materials
        categories = sorted(T["Category"].dropna().unique())
        state.v.setdefault("db.categories", categories)
        choisies = z.multi("Catégorie", categories, "db.categories", apres=self.rafraichirTout)
        recherche = z.saisie("Rechercher un matériau", "db.recherche", apres=self.rafraichirTout)
        vue = filtre_materiaux(T, choisies, recherche)
        z.tableau(
            pd.DataFrame(
                {
                    "Nom": vue["Name"],
                    "Catégorie": vue["Category"],
                    "E (GPa)": vue["E"] / 1e9,
                    "G (GPa)": vue["G"] / 1e9,
                    "ν (-)": vue["nu"],
                    "Re (MPa)": vue["Re"] / 1e6,
                    "Rm (MPa)": vue["Rm"] / 1e6,
                    "α (1e-6/°C)": vue["alpha"] * 1e6,
                    "ρ (kg/m³)": vue["rho"],
                    "Ajouté par": vue["Author"],
                    "Note": vue["Note"],
                }
            )
        )
        z.legende(
            "Les matériaux dont l'auteur est « Base complémentaire » viennent d'un rapport de synthèse (2026). "
            "Ce sont des valeurs typiques, à vérifier sur la fiche matière du fournisseur avant un usage professionnel."
        )
        z.sousTitre("Ajouter un matériau utilisateur")
        z.saisie("Nom", "mat_nom", "Acier utilisateur")
        z.saisie("Catégorie", "mat_cat", "Utilisateur")
        z.nombre("E (GPa)", "mat_E", 210.0)
        z.nombre("G (GPa), 0 = calculé par G = E/(2(1+ν))", "mat_G", 0.0)
        z.nombre("ν (-)", "mat_nu", 0.3, mini=-0.999, maxi=0.499)
        z.nombre("Re (MPa)", "mat_Re", 300.0)
        z.nombre("Rm (MPa)", "mat_Rm", 500.0)
        z.nombre("α (10⁻⁶/°C)", "mat_alpha", 12.0)
        z.nombre("ρ (kg/m³)", "mat_rho", 7850.0)
        z.saisie("Ajouté par", "mat_auteur", "Utilisateur")

        def ajoute() -> None:
            v = state.v
            try:
                dm.addMaterial(
                    {
                        "Name": v["mat_nom"].strip(),
                        "Category": v["mat_cat"].strip() or "Utilisateur",
                        "E": v["mat_E"] * 1e9,
                        "G": v["mat_G"] * 1e9 if v["mat_G"] > 0 else math.nan,
                        "nu": v["mat_nu"],
                        "Re": v["mat_Re"] * 1e6,
                        "Rm": v["mat_Rm"] * 1e6,
                        "alpha": v["mat_alpha"] * 1e-6,
                        "rho": v["mat_rho"],
                        "Note": "Matériau utilisateur (saisi dans l'interface).",
                        "Author": v["mat_auteur"].strip(),
                    }
                )
            except MecaStructError as err:
                v["db.erreur"] = err
                self.rafraichirTout()
                return
            v.pop("db.erreur", None)
            self._message_suivant(f"Matériau « {v['mat_nom'].strip()} » ajouté.")

        z.bouton("Ajouter / remplacer", ajoute)
        z.erreurGardee("db.erreur")
        ajouts = dm.Materials.loc[dm.Materials["IsUser"], "Name"].tolist()
        if ajouts:
            cible = z.liste("Supprimer un matériau utilisateur", ajouts, "mat_suppr")

            def supprime() -> None:
                if not _confirme(self, f"Supprimer le matériau « {cible} » ? Cette action est définitive."):
                    return
                dm.removeMaterial(cible)
                self._message_suivant(f"Matériau « {cible} » supprimé.")

            z.bouton("Supprimer le matériau utilisateur choisi", supprime)
        else:
            z.legende("Aucun matériau utilisateur à supprimer.")

    def _profiles(self, z: Zone) -> None:
        """Tableau d'une famille de profilés (unités de MATLAB), formulaire d'ajout d'un profilé utilisateur."""
        dm = state.dm()
        famille = z.liste("Famille de profilés", dm.listProfileFamilies(), "pro_fam", apres=self.rafraichirTout)
        z.legende("Convention : Iz = axe fort (= Iy Eurocode), Iy = axe faible.")
        T = dm.Profiles[famille]
        z.tableau(
            pd.DataFrame(
                {
                    "Désignation": T["Name"],
                    "h (mm)": T["h"] * 1e3,
                    "b (mm)": T["b"] * 1e3,
                    "a (mm)": T["a"] * 1e3,
                    "e (mm)": T["e"] * 1e3,
                    "r (mm)": T["r"] * 1e3,
                    "S (cm²)": T["S"] * 1e4,
                    "Iz (cm⁴)": T["Iz"] * 1e8,
                    "Iy (cm⁴)": T["Iy"] * 1e8,
                    "Wz (cm³)": T["Wz"] * 1e6,
                    "Wy (cm³)": T["Wy"] * 1e6,
                    "rz (mm)": T["rz"] * 1e3,
                    "ry (mm)": T["ry"] * 1e3,
                    "masse (kg/m)": T["mass"],
                    "c (mm)": T["c"] * 1e3,
                    "Ajouté par": T["Author"],
                }
            )
        )
        z.sousTitre(f"Ajouter un profilé utilisateur ({famille})")
        z.saisie("Désignation", "pro_nom", "IPE 210 util")
        z.nombre("h (mm)", "pro_h", 210.0)
        z.nombre("b (mm)", "pro_b", 105.0)
        z.nombre("a — âme (mm)", "pro_a", 6.0)
        z.nombre("e — aile (mm)", "pro_e", 9.0)
        z.nombre("r — congé (mm)", "pro_r", 12.0)
        z.saisie("Ajouté par", "pro_auteur", "Utilisateur")
        z.legende("S, Iz, Iy, W et r sont calculés sur la géométrie simplifiée (épaisseurs constantes).")

        def ajoute() -> None:
            v = state.v
            try:
                dm.addProfile(
                    famille,
                    {
                        "Name": v["pro_nom"].strip(),
                        "h": v["pro_h"] * 1e-3,
                        "b": v["pro_b"] * 1e-3,
                        "a": v["pro_a"] * 1e-3,
                        "e": v["pro_e"] * 1e-3,
                        "r": v["pro_r"] * 1e-3,
                        "Author": v["pro_auteur"].strip(),
                    },
                )
            except MecaStructError as err:
                v["db.erreur_pro"] = err
                self.rafraichirTout()
                return
            v.pop("db.erreur_pro", None)
            self._message_suivant(f"Profilé « {v['pro_nom'].strip()} » ajouté à la famille {famille}.")

        z.bouton("Ajouter le profilé", ajoute)
        z.erreurGardee("db.erreur_pro")

    def _matage(self, z: Zone) -> None:
        """Table des pressions de matage admissibles et lecture de Pmin, Pmax pour une liaison et des conditions."""
        dm = state.dm()
        B = dm.BearingPressures
        z.tableau(
            pd.DataFrame(
                {
                    "Liaison": B["Liaison"],
                    "Conditions": B["Conditions"],
                    "Pmin (MPa)": B["Pmin"] / 1e6,
                    "Pmax (MPa)": B["Pmax"] / 1e6,
                    "Note": B["Note"],
                }
            )
        )
        liaison = z.liste("Liaison", list(dict.fromkeys(B["Liaison"])), "mat_liaison", apres=self.rafraichirTout)
        conditions = z.liste("Conditions de fonctionnement", list(dict.fromkeys(B["Conditions"])), "mat_conditions",
                             apres=self.rafraichirTout)  # fmt: skip
        try:
            pmin, pmax = dm.getBearingPressure(liaison, conditions)
            z.metrique("Pmin (matage admissible)", f"{pmin / 1e6:.4g} MPa")
            z.metrique("Pmax (matage admissible)", f"{pmax / 1e6:.4g} MPa")
        except MecaStructError as err:
            z.erreurCalcul(err)

    def _abaques_kt(self, z: Zone) -> None:
        """Choix d'un abaque et de ses paramètres, calcul de Kt, graphique avec le point calculé."""
        charts = kt_mohr.ktCharts()
        titres = {c["id"]: c["title"] for c in charts}
        choix = z.liste("Abaque", list(titres), "kt_id", format=titres.get, defaut="arbre_epaulement_flexion",
                        apres=self.rafraichirTout)  # fmt: skip
        ch = next(c for c in charts if c["id"] == choix)
        z.texte(ch["description"])
        z.formule(ch["latex"])
        if choix == "plaque_trou_traction":
            p1 = z.nombre("d/W (-)", "kt_p1_plaque", 0.3, mini=0.0, maxi=0.999, apres=self.rafraichirTout)
            prm = p1
        else:
            p1 = z.nombre("r/d (-)", "kt_p1_arbre", 0.1, mini=0.01, maxi=0.3, apres=self.rafraichirTout)
            p2 = z.nombre("D/d (-)", "kt_p2_arbre", 1.5, mini=1.01, maxi=6.0, apres=self.rafraichirTout)
            prm = [p1, p2]
        try:
            res = compute.computeKt(choix, prm)["result"]
        except MecaStructError as err:
            z.erreurCalcul(err)
            return
        fig = ktChart(choix)
        fig.add_trace(
            go.Scatter(
                x=[p1],
                y=[res["Kt"]],
                mode="markers",
                marker={"size": 12, "color": "rgb(217,84,26)"},
                name=f"K<sub>t</sub> = {res['Kt']:.4g}",
            )
        )
        z.metrique("Kt", f"{res['Kt']:.4g}")
        z.plot(fig)
        z.brut("\n".join(res["rapport"]))

    def _donnees_utilisateur(self, z: Zone) -> None:
        """Enregistrement et rechargement des ajouts (JSON)."""
        dm = state.dm()
        z.info("Les ajouts ne sont conservés que dans le fichier : enregistrez-le pour les retrouver plus tard.")
        z.telecharger("Enregistrer mes ajouts (.json)", lambda: json.dumps(state.dm().exportUserData(),
                      ensure_ascii=False, indent=2), "mecastruct_donnees_utilisateur.json")  # fmt: skip

        def choisi(fichiers: list[tuple[str, bytes]]) -> None:
            state.v["donnees_fichier"] = fichiers[0]
            self.rafraichirTout()

        z.ouvrirFichier("Recharger mes ajouts (.json)", "Fichier JSON (*.json)", choisi)
        fichier = state.v.get("donnees_fichier")
        if fichier is not None:
            z.legende(f"Fichier choisi : {fichier[0]}")

        def importe() -> None:
            try:
                donnees = json.loads(fichier[1].decode("utf-8-sig"))
                if isinstance(donnees, dict):
                    checkLimits(donnees)
                copie = copy.deepcopy(dm)  # tout ou rien : une ligne refusée n'importe pas les précédentes
                n = copie.importUserData(donnees)
            except MecaStructError as err:
                state.v["db.erreur_import"] = err
            except (json.JSONDecodeError, UnicodeDecodeError):
                state.v["db.erreur_import"] = MecaStructError("db:import", "Fichier illisible : ce n'est pas un fichier JSON valide.")
            except (KeyError, TypeError, AttributeError):
                state.v["db.erreur_import"] = MecaStructError(
                    "db:import", "Fichier invalide : la structure attendue (matériaux, profilés, matage) n'est pas respectée."
                )
            else:
                state.v["dm"] = copie
                state.v.pop("db.erreur_import", None)
                state.v.pop("donnees_fichier", None)
                self._message_suivant(f"{n} ajout(s) importé(s).")
                return
            self.rafraichirTout()

        if fichier is not None:
            z.bouton("Importer ce fichier", importe)
        z.erreurGardee("db.erreur_import")

    def _documents(self, z: Zone) -> None:
        """Enregistrement de la note de calcul et du guide, lus dans le dossier docs de l'application."""
        for nom, libelle in (("NOTE_DE_CALCUL.html", "Note de calcul"), ("GUIDE_UTILISATEUR.html", "Guide d'utilisation")):
            chemin = DOCS / nom
            if chemin.exists():
                z.telecharger(f"Enregistrer : {libelle}", chemin.read_bytes, nom)
            else:
                z.legende(f"{nom} absent du dossier docs.")

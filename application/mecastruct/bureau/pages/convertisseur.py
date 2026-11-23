"""Page « Convertisseur » : conversion entre unités de toutes les grandeurs (port de buildConverterTab).

Les champs de saisie de l'application restent en mm, m, kN et MPa ; les résultats aussi.
"""

import math

import pandas as pd
from PySide6.QtWidgets import QApplication

from mecastruct.bureau import state
from mecastruct.bureau.widgets import Page, Zone
from mecastruct.core import units
from mecastruct.core.errors import MecaStructError

# Unités attendues dans les champs de saisie (port de expectedUnits de MecaStruct_App.m)
UNITES_ATTENDUES = [
    ("Matériaux", "E, G", "GPa"),
    ("Matériaux", "Re, Rm, contraintes", "MPa"),
    ("Sections", "dimensions b, h, D, d, B, H, t, tw, tf", "mm"),
    ("Sections", "N, Ty ; Mfz, Mfy", "kN ; kN·m"),
    ("Poutres", "L, positions, a, b", "m"),
    ("Poutres", "S ; Iz, Iy, Ix ; vy, vz", "mm² ; mm⁴ ; mm"),
    ("Poutres", "forces ; couples ; charges réparties", "kN ; kN·m ; kN/m"),
    ("Treillis", "coordonnées ; S ; forces", "m ; mm² ; kN"),
    ("Traction", "N ; S0 ; L0 ; ΔT ; α", "kN ; mm² ; m ; °C ; 10⁻⁶/°C"),
    ("Cisaillement", "T, F ; S ; C ; D, a, b, L, d, e", "kN ; mm² ; kN·m ; mm"),
    ("Torsion", "Mt ; D, d ; L ; θ adm", "kN·m ; mm ; m ; °/m"),
    ("Flexion", "N ; Mfz, Mfy", "kN ; kN·m"),
    ("Flambage", "L ; S ; Iz, Iy ; P", "m ; mm² ; mm⁴ ; kN"),
    ("Tenseurs", "σij", "MPa"),
    ("Hooke", "σ ; ε, γ ; E", "MPa ; µdéf ; GPa"),
    ("Jauges", "ε ; R0 ; Vin ; Vout", "µdéf ; Ω ; V ; mV"),
    ("Résultats", "tous les rapports et graphes", "mm, kN, kN·m, MPa, mrad"),
]

# Équivalences utiles en RDM (port du tableau « useful » de buildConverterTab)
EQUIVALENCES = [
    ("1 MPa", "= 1 N/mm² = 10⁶ Pa"),
    ("1 GPa", "= 1000 MPa (E acier = 210 GPa = 210 000 MPa)"),
    ("1 daN", "= 10 N"),
    ("1 kgf", "= 9,80665 N"),
    ("1 bar", "= 0,1 MPa"),
    ("1 ksi", "≈ 6,895 MPa"),
    ("1 psi", "≈ 6,895 kPa"),
    ("1 kN·m", "= 10⁶ N·mm"),
    ("1 in", "= 25,4 mm"),
    ("1 µdéf", "= 10⁻⁶ = 0,0001 %"),
    ("1 rad", "≈ 57,2958 °"),
]

GRANDEURS = units.unitCatalog()
NOMS = [g["name"] for g in GRANDEURS]


def _grandeur(nom: str) -> dict:
    """Entrée du catalogue d'unités pour la grandeur `nom`."""
    return next(g for g in GRANDEURS if g["name"] == nom)


def _libelles(nom: str) -> list[str]:
    """Libellés des unités de la grandeur `nom`, dans l'ordre du catalogue."""
    return [u["label"] for u in _grandeur(nom)["units"]]


def convertir(valeur: float, grandeur: str, de: str, vers: str) -> float:
    """Valeur convertie ; refuse une température sous le zéro absolu et un résultat infini (mêmes messages que le site)."""
    if grandeur == "Température absolue" and float(units.convertUnits(valeur, grandeur, de, "K")) < -1e-9:
        raise MecaStructError(
            "MecaStruct:App:invalidInput",
            "Cette température est sous le zéro absolu (0 K, soit −273,15 °C ou −459,67 °F) : elle n'existe pas.",
        )
    resultat = float(units.convertUnits(valeur, grandeur, de, vers))
    if not all(math.isfinite(float(units.convertUnits(valeur, grandeur, de, lib))) for lib in _libelles(grandeur)):
        raise MecaStructError(
            "MecaStruct:App:invalidInput",
            "Valeur trop grande : un des résultats dépasse les nombres que le calcul sait écrire. Essayez une valeur plus petite.",
        )
    return resultat


class PageConvertisseur(Page):
    def _unites_par_defaut(self) -> None:
        """Remet « De » et « Vers » sur les unités par défaut de la grandeur choisie (indices 1-based du catalogue)."""
        g = _grandeur(state.v["conv.grandeur"])
        libelles = _libelles(g["name"])
        state.v["conv.de"] = libelles[g["defFrom"] - 1]
        state.v["conv.vers"] = libelles[g["defTo"] - 1]
        self.rafraichirTout()

    def _inverser(self) -> None:
        """Échange les unités « De » et « Vers »."""
        state.v["conv.de"], state.v["conv.vers"] = state.v["conv.vers"], state.v["conv.de"]
        self.rafraichirTout()

    def rendre(self, z: Zone) -> None:
        z.titre("Convertisseur")
        z.intro("Conversion entre unités de toutes les grandeurs.")
        if "conv.de" not in state.v:
            state.v.setdefault("conv.grandeur", NOMS[0])
            g = _grandeur(NOMS[0])
            state.v["conv.de"] = _libelles(NOMS[0])[g["defFrom"] - 1]
            state.v["conv.vers"] = _libelles(NOMS[0])[g["defTo"] - 1]
        c1, c2, c3, c4, c5 = z.colonnes([20, 12, 12, 12, 10])
        grandeur = c1.liste("Grandeur", NOMS, "conv.grandeur", apres=self._unites_par_defaut)
        valeur = c2.nombre("Valeur", "conv.valeur", 1.0, apres=self.rafraichirTout)
        c3.liste("De", _libelles(grandeur), "conv.de", apres=self.rafraichirTout)
        c4.liste("Vers", _libelles(grandeur), "conv.vers", apres=self.rafraichirTout)
        c5.legende(" ")
        c5.bouton("Inverser", self._inverser)
        de, vers = state.v["conv.de"], state.v["conv.vers"]
        try:
            resultat = convertir(valeur, grandeur, de, vers)
            z.metrique(f"{valeur:.10g} {de} =", f"{float(resultat):.10g} {vers}")
            z.legende("Valeur à copier :")
            texte = f"{float(resultat):.10g}"
            ligne = z.colonnes([1, 3])
            ligne[0].bouton("Copier", lambda: QApplication.clipboard().setText(texte))
            ligne[1].texte(f"`{texte}`")
            libelles = _libelles(grandeur)
            z.tableau(
                pd.DataFrame(
                    {
                        "Unité": libelles,
                        "Valeur équivalente": [
                            f"{float(units.convertUnits(valeur, grandeur, de, u)):.10g}" for u in libelles
                        ],
                    }
                )
            )
        except MecaStructError as err:
            z.erreurCalcul(err)
        z.info("Les champs de saisie de l'application sont en mm, m, kN et MPa ; les résultats aussi.")
        gauche, droite = z.colonnes([14, 10])
        gauche.sousTitre("Unités attendues dans les champs")
        gauche.tableau(pd.DataFrame(UNITES_ATTENDUES, columns=["Où", "Champ", "Unité attendue"]))
        droite.sousTitre("Équivalences utiles en RDM")
        droite.tableau(pd.DataFrame(EQUIVALENCES, columns=["Équivalence", "Valeur"]))

"""Page « Limites et vérifications » : le texte de LIMITES.md, comme sur le site."""

from pathlib import Path

import pandas as pd

from mecastruct.bureau import theme
from mecastruct.bureau.widgets import Page, Zone
from mecastruct.services import verifications
from mecastruct.services.pages_texte import INTROS


def chemin_limites() -> Path | None:
    """LIMITES.md : à la racine du dépôt (code source) ou à côté des données (application empaquetée)."""
    ici = Path(__file__).resolve()
    return next((p for p in (ici.parents[3] / "LIMITES.md", ici.parents[4] / "LIMITES.md") if p.is_file()), None)


COLONNES = ("Calcul", "Données", "Formule de manuel", "Valeur attendue", "Valeur MecaStruct", "Écart relatif", "Verdict")


def tableau_verifications(lignes: list[dict]) -> pd.DataFrame:
    """Les lignes de services/verifications.py en tableau de textes (mêmes colonnes que sur le site)."""
    return pd.DataFrame(
        [
            [
                f"{x['page']} : {x['titre']}",
                x["donnees"],
                x["formule"],
                f"{x['cible_txt']} {x['unite']}",
                f"{x['calculee_txt']} {x['unite']}",
                x["ecart_txt"],
                "✓ conforme" if x["ok"] else "✗ hors tolérance",
            ]
            for x in lignes
        ],
        columns=list(COLONNES),
    )


def _couleur_verdict(valeur: str) -> tuple[str, str]:
    return theme.couleur_message("succes" if valeur.startswith("✓") else "erreur")


class PageLimites(Page):
    def __init__(self, fenetre) -> None:
        super().__init__(fenetre)
        self._verifications: list[dict] | None = None  # calculées à la première ouverture, puis gardées (le code ne change pas)

    def verifications_calculees(self) -> list[dict]:
        if self._verifications is None:
            self._verifications = verifications.verifier()
        return self._verifications

    def rendre(self, z: Zone) -> None:
        z.titre("Limites et vérifications")
        z.intro(INTROS["Limites et vérifications"])
        chemin = chemin_limites()
        if chemin is None:
            z.avertissement("LIMITES.md est introuvable. Il est aussi sur GitHub : github.com/theo33-oss/MecaStruct")
            return
        texte = chemin.read_text(encoding="utf-8")
        z.texte(texte.split("\n", 1)[1] if texte.startswith("# ") else texte)  # sans le titre, déjà affiché
        self.rendre_verifications(z)

    def rendre_verifications(self, z: Zone) -> None:
        """Section « Vérifications indépendantes » : MecaStruct contre des formules de manuel (cas à solution exacte)."""
        z.sousTitre("Vérifications indépendantes")
        z.texte(
            "Chaque ligne compare MecaStruct à une formule fermée de manuel, refaite à la main dans le code : aucune "
            "valeur ne vient d'une norme ni de la mémoire. L'écart est relatif ; la ligne est conforme quand il ne "
            "dépasse pas la tolérance (1e-9, soit de l'arrondi de calcul)."
        )
        lignes = self.verifications_calculees()
        bilan = verifications.resume(lignes)
        if bilan["tout_ok"]:
            z.succes(f"Les {bilan['total']} vérifications sont conformes. Écart relatif maximal : {bilan['ecart_max_txt']}.")
        else:
            z.erreur(
                f"{bilan['total'] - bilan['ok']} vérification(s) sur {bilan['total']} hors tolérance : ne vous fiez pas "
                "aux pages concernées avant correction."
            )
        for x in lignes:
            if x["erreur"]:
                z.erreur(f"{x['titre']} : {x['erreur']}")
        z.tableau(tableau_verifications(lignes), couleurs={"Verdict": _couleur_verdict})

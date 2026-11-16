"""Page « À propos » : version, auteur, confidentialité et limites."""

from mecastruct import __version__
from mecastruct.bureau.widgets import Page, Zone


class PageAPropos(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("À propos")
        z.texte(
            f"**MecaStruct RdM Pro**, version {__version__}. Application de **Théo Brun**, portage de son application "
            "MATLAB de Résistance des Matériaux et d'éléments de machines, basée sur son cours."
        )
        z.texte(
            "Version en ligne, mises à jour et signalement d'erreurs : https://github.com/theo33-oss/MecaStruct. "
            "Licence PolyForm Noncommercial 1.0.0."
        )
        z.sousTitre("Confidentialité")
        z.texte(
            "Tout est calculé sur cet ordinateur : aucune donnée n'est envoyée sur Internet, aucun compte, aucun "
            "traceur. Vos études restent dans les fichiers que vous enregistrez."
        )
        z.sousTitre("Limites")
        z.texte(
            "Outil pédagogique et d'aide au pré-dimensionnement, fourni sans garantie. Les résultats ne remplacent ni "
            "une note de calcul certifiée ni les normes en vigueur et doivent être vérifiés avant tout usage réel."
        )

"""Page « Références » : les normes sur lesquelles l'application s'appuie ou qu'elle cite.

Numéro, titre, année et rôle seulement : les textes des normes sont protégés (AFNOR) et ne sont pas reproduits.
Le détail clause par clause des vérifications Eurocode 3 est dans docs/NORMES.md du dépôt d'origine.
"""

from mecastruct.bureau.widgets import Page, Zone
from mecastruct.core.utils import load_json

# (numéro, titre, année, rôle dans l'application) : data/references.json, aussi lu par le site
NORMES = [(n["numero"], n["titre"], n["annee"], n["role"]) for n in load_json("references.json")]


class PageReferences(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Références")
        z.legende(
            "Normes sur lesquelles l'application s'appuie ou qu'elle cite. Seuls le numéro, le titre et l'année sont "
            "donnés : les textes sont protégés (AFNOR) et se consultent chez l'éditeur. Avant tout usage professionnel, "
            "vérifier les valeurs et les clauses dans le texte officiel et dans l'annexe nationale du pays."
        )
        for numero, titre, annee, role in NORMES:
            c = z.cadre()
            c.texte(f"**{numero}** — {annee}")
            c.texte(titre)
            c.legende(f"Dans l'application : {role}")

"""Page « Références » : les normes sur lesquelles l'application s'appuie ou qu'elle cite.

Numéro, titre, année et rôle seulement : les textes des normes sont protégés (AFNOR) et les cours appartiennent à leurs
auteurs : rien n'est reproduit.
Le détail clause par clause des vérifications Eurocode 3 est dans docs/NORMES.md du dépôt d'origine.
"""

from mecastruct.bureau.widgets import Page, Zone
from mecastruct.core.utils import load_json

# data/references.json : numéro (ou auteur), titre, année, rôle et genre ; aussi lu par le site
REFERENCES = load_json("references.json")
GENRES = (
    ("norme", "Normes"),
    ("cours", "Cours (Université de Bordeaux)"),
    ("document", "Documents techniques et données de matériaux"),
)


class PageReferences(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Références")
        z.intro("Normes, cours et documents cités par l'application.")
        z.legende(
            "Normes et cours sur lesquels l'application s'appuie ou qu'elle cite. Seuls le numéro, le titre et l'année "
            "sont donnés : les textes des normes sont protégés (AFNOR) et se consultent chez l'éditeur, les cours "
            "appartiennent à leurs auteurs. Les mentions sont celles imprimées sur les documents (« non indiqué » "
            "sinon). Avant tout usage professionnel, vérifier les valeurs et les clauses dans le texte officiel et dans "
            "l'annexe nationale du pays."
        )
        for genre, titre_genre in GENRES:
            z.sousTitre(titre_genre)
            for n in (r for r in REFERENCES if r.get("genre", "norme") == genre):
                c = z.cadre()
                c.texte(f"**{n['numero']}** — {n['annee']}")
                c.texte(n["titre"])
                c.legende(f"Dans l'application : {n['role']}")

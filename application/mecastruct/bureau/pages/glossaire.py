"""Page « Glossaire » : symboles, noms, unités et pages, avec un filtre (comme la page du site, docs/js/glossaire.js).

Les entrées sont celles de services/glossaire.py : libellés, unités et aides des champs, variables des fiches de formules.
"""

import pandas as pd
from PySide6.QtWidgets import QLineEdit

from mecastruct.bureau.etudes import vers_bureau
from mecastruct.bureau.recherche import norme
from mecastruct.bureau.widgets import Page, TableauDonnees, Zone
from mecastruct.services import glossaire
from mecastruct.services.pages_texte import INTROS

ENTETES = ("Symbole", "Nom", "Unité", "Pages")


class PageGlossaire(Page):
    def rendre(self, z: Zone) -> None:
        z.titre("Glossaire")
        z.intro(INTROS["Glossaire"])
        z.legende(
            "Chaque entrée est lue dans les libellés, les unités et les aides des champs de l'application, et dans les "
            "variables du « Formulaire rapide ». Une entrée par sens : un même symbole peut désigner deux grandeurs selon "
            "la page. L'unité est celle des champs de saisie ; les formules du « Formulaire rapide » sont en unités du "
            "Système international."
        )
        titres = self.fenetre.libelles
        self.entrees = glossaire.entrees()
        lignes = [
            [e["symbole"], e["nom"] + (f" : {e['aide']}" if e["aide"] else ""), e["unite"] or "–",
             ", ".join(titres.get(vers_bureau(p), p) for p in e["pages"])]  # fmt: skip
            for e in self.entrees
        ]
        self.textes = [norme(" ".join([e["symbole"], e["nom"], e["unite"], e["aide"], ligne[3]])) for e, ligne in zip(self.entrees, lignes, strict=True)]
        self.filtre = QLineEdit()
        self.filtre.setClearButtonEnabled(True)
        self.filtre.setPlaceholderText("Symbole, nom, unité ou page (ex. : σ, module, MPa, roulements)")
        self.filtre.setAccessibleName("Filtrer le glossaire")
        self.filtre.textChanged.connect(self._filtrer)
        z._ajouter(self.filtre)
        self.etat = z._libelle("", "legende")
        self.table = TableauDonnees(pd.DataFrame(lignes, columns=list(ENTETES)))
        self.table.setAccessibleName("Glossaire des symboles")
        for j, largeur in enumerate((110, 560, 110)):
            self.table.setColumnWidth(j, largeur)
        self.table.setFixedHeight(520)  # le tableau défile sur place
        z._ajouter(self.table)
        self.vide = z._libelle("Aucun symbole ne correspond à ce filtre.", "legende")
        self._filtrer()

    def _filtrer(self, _texte: str = "") -> None:
        mots = norme(self.filtre.text()).split()
        n = 0
        for i, t in enumerate(self.textes):
            ok = all(m in t for m in mots)
            self.table.setRowHidden(i, not ok)
            n += ok
        self.vide.setVisible(n == 0)
        total = len(self.textes)
        self.etat.setText(f"{n} symbole{'s' if n > 1 else ''} sur {total}" if mots else f"{total} symboles")

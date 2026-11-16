"""Briques de description des formulaires de la page web : champs, tableaux éditables, groupes.

Chaque champ est un dict JSON que docs/js/machine.js sait dessiner. Aucune logique de calcul ici.
"""


def nb(ident, libelle, unite="", mini=None, maxi=None, aide="", entier=False):
    """Champ numérique (virgule ou point acceptés), borné si mini ou maxi."""
    return {"id": ident, "type": "nombre", "libelle": libelle, "unite": unite, "min": mini, "max": maxi, "aide": aide,
            "entier": entier}  # fmt: skip


def liste(ident, libelle, options, aide="", etiquettes=None):
    """Liste déroulante ; `etiquettes` : textes affichés à la place des valeurs (même ordre)."""
    return {"id": ident, "type": "liste", "libelle": libelle, "options": list(options), "aide": aide,
            "etiquettes": list(etiquettes) if etiquettes else None}  # fmt: skip


def case(ident, libelle, aide=""):
    return {"id": ident, "type": "case", "libelle": libelle, "aide": aide}


def texte(ident, libelle, aide=""):
    return {"id": ident, "type": "texte", "libelle": libelle, "aide": aide}


def col(ident, libelle, genre="nombre", options=None, defaut=0.0, entier=False):
    """Colonne d'un tableau éditable : genre nombre, texte, liste ou case."""
    return {"id": ident, "libelle": libelle, "genre": genre, "options": list(options) if options else None,
            "defaut": defaut, "entier": entier}  # fmt: skip


def tableau(ident, libelle, colonnes, aide="", mini=0):
    """Tableau éditable : une ligne par élément (appui, charge, nœud…), lignes ajoutées ou retirées, collage Excel."""
    return {"id": ident, "type": "tableau", "libelle": libelle, "colonnes": colonnes, "aide": aide, "min": mini}


def groupe(titre, *champs, ouvert=True, ligne=False, note=""):
    return {"titre": titre, "champs": list(champs), "ouvert": ouvert, "ligne": ligne, "note": note}

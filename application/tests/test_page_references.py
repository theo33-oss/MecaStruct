"""Page « Références » : normes citées par l'application, sans texte de norme ni lien Drive."""


def test_la_page_liste_l_eurocode_3_et_les_normes_citees(bureau):
    bureau.ouvre("references")
    for numero in ("NF EN 1993-1-1", "EN 1993-1-5", "EN 338", "EN 1992-1-1"):
        assert bureau.a_texte(numero)
    assert sum("Dans l'application :" in t for t in bureau.textes()) == 6  # un rôle par norme


def test_normes_non_utilisees_et_liens_prives_absents(bureau):
    bureau.ouvre("references")
    texte = " | ".join(bureau.textes())
    for interdit in ("B5560", "ISO 527", "drive.google", "docs.google"):
        assert interdit not in texte


def test_la_page_est_dans_le_groupe_outils_du_menu():
    import main

    idents = [ident for ident, _, _ in main.MENU]
    assert idents.index("base_de_donnees") < idents.index("references") < idents.index("Informations")

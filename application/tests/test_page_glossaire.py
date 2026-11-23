"""Page « Glossaire » du bureau : tableau filtrable, recherche globale, lien au pied des pages de calcul."""

import main
from mecastruct.bureau import recherche
from mecastruct.services import glossaire
from mecastruct.services.pages_texte import INTROS


def _ligne(page, symbole):
    return [i for i in range(page.table.rowCount()) if page.table.item(i, 0).text() == symbole]


def test_la_page_liste_toutes_les_entrees_du_glossaire(bureau):
    page = bureau.ouvre("glossaire")
    assert page.table.rowCount() == len(glossaire.entrees())
    assert [page.table.horizontalHeaderItem(j).text() for j in range(4)] == ["Symbole", "Nom", "Unité", "Pages"]
    assert bureau.a_texte("Symboles des formules")
    ligne = _ligne(page, "E")[0]
    assert page.table.item(ligne, 1).text().startswith("Module d'Young")
    assert "Poutres" in page.table.item(ligne, 3).text()


def test_le_filtre_garde_les_lignes_qui_correspondent(bureau):
    page = bureau.ouvre("glossaire")
    visibles = lambda: [i for i in range(page.table.rowCount()) if not page.table.isRowHidden(i)]  # noqa: E731
    page.filtre.setText("sigma")  # « sigma » trouve « σ »
    assert {"σ", "σe", "σi"} <= {page.table.item(i, 0).text() for i in visibles()}
    assert len(visibles()) < page.table.rowCount()
    page.filtre.setText("roulements charge")  # plusieurs mots : tous doivent être présents
    assert visibles() and all("Roulements" in page.table.item(i, 3).text() for i in visibles())
    page.filtre.setText("xyzzy")
    assert not visibles() and bureau.a_texte("Aucun symbole ne correspond")
    page.filtre.setText("")
    assert len(visibles()) == page.table.rowCount()


def test_la_page_est_dans_le_menu_apres_les_references():
    idents = [i for i, _, _ in main.MENU]
    assert idents.index("references") + 1 == idents.index("glossaire") < idents.index("limites")


def test_la_recherche_trouve_le_glossaire_par_mot_et_par_symbole():
    libelles = {i: lib for i, lib, _ in main.MENU if lib is not None}
    famille, courante = {}, None
    for ident, libelle, _ in main.MENU:
        if libelle is None:
            courante = ident
        else:
            famille[ident] = courante
    index = recherche.Index(libelles, famille, INTROS)
    for saisie in ("glossaire", "symbole", "symboles", "σ", "sigma", "τe", "α", "ΔT", "Kt", "Lcr"):
        res, _ = index.resultats(saisie)
        assert any(r["page"] == "glossaire" for r in res), saisie


def test_chaque_page_de_calcul_a_le_lien_vers_le_glossaire(bureau):
    for ident in ("poutres", "roulements", "sollicitations"):
        bureau.ouvre(ident)
        assert bureau.boutons("Voir le glossaire"), ident
    bureau.clique("Voir le glossaire")
    bureau.attend(60)
    assert bureau.fenetre.menu.currentRow() == bureau.fenetre.pages["glossaire"][0]

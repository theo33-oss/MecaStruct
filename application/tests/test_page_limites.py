"""Page « Limites et vérifications » du bureau : le texte de LIMITES.md puis le tableau des vérifications indépendantes."""

from PySide6.QtWidgets import QTableWidget


def test_page_limites_montre_les_verifications_independantes(bureau):
    page = bureau.ouvre("limites")
    assert bureau.a_texte("Vérifications indépendantes")
    assert bureau.a_texte("vérifications sont conformes")
    tableaux = page.findChildren(QTableWidget)
    assert tableaux, "tableau des vérifications absent"
    t = tableaux[-1]
    entetes = [t.horizontalHeaderItem(j).text() for j in range(t.columnCount())]
    assert entetes[:1] == ["Calcul"] and entetes[-1] == "Verdict"
    assert t.rowCount() >= 40
    assert all(t.item(i, t.columnCount() - 1).text().startswith("✓") for i in range(t.rowCount()))

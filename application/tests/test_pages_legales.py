"""Page « À propos » (qui remplace les quatre pages légales du site) et légende textuelle des graphiques."""

import plotly.graph_objects as go

from mecastruct.bureau.widgets import resume_graphique


def test_page_a_propos_remplace_les_pages_legales(bureau):
    bureau.ouvre("apropos")
    assert bureau.a_texte("À propos")
    assert bureau.a_texte("aucune donnée n'est envoyée sur Internet")
    assert bureau.a_texte("Limites")


def test_le_menu_n_a_plus_de_pages_legales():
    import main

    idents = {ident for ident, libelle, _ in main.MENU if libelle}
    assert not idents & {"mentions_legales", "confidentialite", "cookies", "conditions"}
    assert "apropos" in idents


def test_resume_graphique_donne_titre_axes_et_extrema():
    fig = go.Figure(go.Scatter(x=[0, 1, 2, 3], y=[0, 5, -2, 1], name="v(s)"))
    fig.update_layout(title="Flèche<br><sup>poutre</sup>", xaxis_title="s (m)", yaxis_title="v (mm)")
    texte = resume_graphique(fig)
    assert "Flèche poutre" in texte
    assert "x = s (m), y = v (mm)" in texte
    assert "v(s) : maximum 5 en x = 1, minimum -2 en x = 2." in texte


def test_resume_graphique_d_un_dessin_a_l_echelle_se_limite_au_titre():
    fig = go.Figure(go.Scatter(x=[0, 1, 2], y=[0, 1, 0], name="contour"))
    fig.update_layout(title="Schéma", yaxis_scaleanchor="x")
    assert resume_graphique(fig) == "Schéma"

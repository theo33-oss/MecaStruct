"""Contraste élevé des graphiques : traits épaissis, aires plus opaques, bord d'aire (largeur 0) inchangé."""

import plotly.graph_objects as go

from mecastruct.bureau import state, widgets


def test_renforce():
    fig = go.Figure(
        [
            go.Scatter(y=[0, 1], line={"width": 1.8}),
            go.Scatter(y=[0, 1], fill="tozeroy", line={"width": 0}, fillcolor="rgba(0,115,189,0.3)"),
        ]
    )
    widgets._renforce(fig)
    assert fig.data[0].line.width == 3.24
    assert fig.data[1].line.width == 0 and fig.data[1].fillcolor == "rgba(0,115,189,0.6)"


def test_page_poutres_en_contraste_eleve(bureau):
    state.v["contraste"] = True
    bureau.ouvre("poutres")
    bureau.clique("Calculer")
    assert state.result("Beam") is not None
    assert widgets.contrasteEleve()


def test_case_contraste_de_la_fenetre(bureau):
    """La case « Contraste élevé » du menu règle l'option lue par les graphiques."""
    from PySide6.QtWidgets import QCheckBox

    case = bureau.fenetre.findChild(QCheckBox)
    assert not widgets.contrasteEleve()
    case.setChecked(True)
    assert widgets.contrasteEleve()

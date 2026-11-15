"""Briques de la fenêtre : valeurs clés d'une ligne d'état, alerte de matériau absent, nombres saisis."""

import pytest

from mecastruct.bureau import dossier, state, widgets
from mecastruct.bureau.page_calcul import synthese_statut


class ZoneEspion:
    """Zone qui garde les valeurs clés qu'on lui demande d'afficher."""

    def __init__(self) -> None:
        self.valeurs: list[dict] = []

    def synthese(self, valeurs) -> None:
        self.valeurs.extend(valeurs)


@pytest.fixture
def z():
    return ZoneEspion()


def test_synthese_statut_valeurs_et_verdict(z):
    synthese_statut(z, "σI = 87.08 MPa, σIII = -47.08 MPa — VM = 116.2 MPa (vérifié)")
    assert [(v["label"], v["value"]) for v in z.valeurs] == [
        ("σI", "87.08 MPa"),
        ("σIII", "-47.08 MPa"),
        ("VM", "116.2 MPa"),
    ]
    assert z.valeurs[2]["delta"] == "vérifié" and z.valeurs[2]["delta_color"] == "green"
    assert "delta" not in z.valeurs[0]


def test_synthese_statut_verdict_apres_deux_points_et_note_neutre(z):
    synthese_statut(z, "h = 0 (isostatique) — P = 12.5 kN : NON vérifié")
    assert z.valeurs[0]["delta"] == "isostatique" and z.valeurs[0]["delta_color"] == "off"
    assert z.valeurs[1]["value"] == "12.5 kN" and z.valeurs[1]["delta_color"] == "red"


def test_synthese_statut_texte_libre_sans_metrique(z):
    synthese_statut(z, "Clavette : longueur minimale Lmin = 41.2 mm")
    assert [v["label"] for v in z.valeurs] == []


def test_alerte_materiau_absent_renvoie_a_l_import():
    state.v.clear()
    assert dossier._alerte_materiaux({"Fla": {"mat": "S235"}}) == ""
    msg = dossier._alerte_materiaux({"Fla": {"mat": "Acier maison"}, "Tor": {"mat": "Acier maison"}})
    assert "« Acier maison » (onglets Fla, Tor)" in msg and "Recharger mes ajouts" in msg


def test_nombres_a_la_francaise():
    assert widgets.lireNombre("1,5") == 1.5 and widgets.lireNombre(" 2.25 ") == 2.25
    assert widgets.lireNombre("") is None
    assert widgets.lireNombre("−3") == -3.0  # signe moins typographique
    with pytest.raises(ValueError):
        widgets.lireNombre("abc")
    assert widgets.formatNombre(1.5) == "1,5" and widgets.formatNombre(12.0, entier=True) == "12"
    assert widgets.formatNombre(None) == "" and widgets.formatNombre(float("nan")) == ""


def test_champ_nombre_restaure_l_ancienne_valeur_et_borne(qtbot):
    recus = []
    champ = widgets.ChampNombre(2.0, False, 0.0, 10.0, recus.append)
    qtbot.addWidget(champ)
    champ.setText("pas un nombre")
    champ.editingFinished.emit()
    assert champ.text() == "2" and champ.valeur == 2.0 and recus == []
    champ.setText("4,5")
    champ.editingFinished.emit()
    assert champ.valeur == 4.5 and recus == [4.5]
    champ.setText("99")
    champ.editingFinished.emit()
    assert champ.valeur == 10.0  # borné par le maximum
    champ.setText("-5")
    champ.editingFinished.emit()
    assert champ.valeur == 0.0  # borné par le minimum


def test_champ_nombre_entier(qtbot):
    champ = widgets.ChampNombre(3, True, 1, None, lambda v: None)
    qtbot.addWidget(champ)
    champ.setText("7,6")
    champ.editingFinished.emit()
    assert champ.valeur == 8 and isinstance(champ.valeur, int)

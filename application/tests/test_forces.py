"""Force inclinée dans un plan : composantes Fx, Fy, Fz depuis F, α et le plan."""

import math

import pytest

from mecastruct.services import forces


def test_composantes_des_trois_plans():
    c = forces.composantes(1000.0, 30.0, "xz")
    assert c["Fy"] == 0 and abs(c["Fx"] - 1000 * math.cos(math.radians(30))) < 1e-9 and abs(c["Fz"] - 500) < 1e-9
    c = forces.composantes(1000.0, 30.0, "yz")
    assert c["Fx"] == 0 and abs(c["Fy"] - 866.0254037844386) < 1e-9 and abs(c["Fz"] - 500) < 1e-9
    c = forces.composantes(10.0, -30.0, "xy")
    assert c["Fz"] == 0 and abs(c["Fx"] - 8.660254037844386) < 1e-12 and abs(c["Fy"] + 5) < 1e-12


def test_angle_droit_donne_zero_exact():
    assert forces.composantes(1000.0, -90.0, "yz") == {"Fx": 0.0, "Fy": 0.0, "Fz": -1000.0}


def test_appliquer_polaire_ne_touche_pas_une_ligne_sans_f():
    ligne = {"Fx": 1.0, "Fy": 2.0, "Fz": 3.0, "F": 0.0, "ang": 45.0, "plan": "xz"}
    assert forces.appliquer_polaire(ligne) == ligne
    assert forces.appliquer_polaire({**ligne, "F": 10.0})["Fy"] == 0.0


def test_plan_inconnu():
    with pytest.raises(ValueError):
        forces.composantes(1.0, 0.0, "ab")


def test_cellules_absentes_ou_nan_comptent_pour_zero():
    nan = float("nan")
    ligne = {"noeud": 1, "Fx": 5.0, "F": nan, "ang": nan, "plan": nan}
    assert forces.appliquer_polaire(ligne)["Fx"] == 5.0
    assert forces.appliquer_polaire({"Fx": 5.0, "F": 10.0, "ang": nan, "plan": nan}, "xz")["Fx"] == 10.0

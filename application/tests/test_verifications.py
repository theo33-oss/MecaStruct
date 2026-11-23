"""Vérifications indépendantes (services/verifications.py) : chaque cas du moteur doit égaler sa formule de manuel."""

import math

import pytest

from mecastruct.services import verifications as v

LIGNES = v.verifier()  # un seul calcul pour tout le fichier (moins de 2 s)


def test_ensemble_non_vide_et_identifiants_uniques():
    assert len(LIGNES) >= 40
    ids = [x["id"] for x in LIGNES]
    assert len(ids) == len(set(ids))
    # toutes les pages qui disaient « pas de recalcul indépendant » sont couvertes
    pages = {x["page"] for x in LIGNES}
    assert {"Poutres", "Treillis", "Sections", "Sollicitations", "Flambage", "Tenseurs et critères",
            "Hooke et jauges"} <= pages


@pytest.mark.parametrize("ligne", LIGNES, ids=[x["id"] for x in LIGNES])
def test_cas_dans_sa_tolerance(ligne):
    assert not ligne["erreur"], ligne["erreur"]
    assert ligne["tolerance"] <= 1e-6  # jamais plus large sans justification écrite dans le module
    assert math.isfinite(ligne["valeur_cible"]) and math.isfinite(ligne["valeur_calculee"])
    assert ligne["ecart"] <= ligne["tolerance"], (
        f"{ligne['titre']} : attendu {ligne['cible_txt']}, MecaStruct {ligne['calculee_txt']} {ligne['unite']}"
    )
    assert ligne["ok"]


def test_chaque_ligne_est_complete():
    for x in LIGNES:
        for champ in ("titre", "page", "donnees", "formule", "reference", "unite", "cible_txt", "calculee_txt"):
            assert x[champ], (x["id"], champ)
        assert "http" not in x["reference"]  # référence = formule de manuel, jamais une adresse inventée


def test_resume():
    r = v.resume(LIGNES)
    assert r["total"] == len(LIGNES) and r["ok"] == len(LIGNES) and r["tout_ok"]
    assert r["ecart_max"] <= 1e-9


def test_un_ecart_est_detecte():
    """La comparaison n'est pas complaisante : 1 % d'écart sort de la tolérance, un moteur en panne donne une ligne rouge."""
    ligne = v._ligne("x", "Poutres", "t", "d", "f", "r", 100.0, 101.0, "N")
    assert not ligne["ok"] and ligne["ecart"] == pytest.approx(0.01)
    assert v._ligne("x", "Poutres", "t", "d", "f", "r", 100.0, 100.0 * (1 + 1e-12), "N")["ok"]
    assert not v._ligne("x", "Poutres", "t", "d", "f", "r", 100.0, math.nan, "N")["ok"]


def test_moteur_en_panne_donne_une_ligne_en_echec(monkeypatch):
    def casse():
        raise ValueError("panne simulée")

    monkeypatch.setattr(v, "_GROUPES", [("essai", "Poutres", casse)])
    lignes = v.verifier()
    assert len(lignes) == 1 and not lignes[0]["ok"] and "panne simulée" in lignes[0]["erreur"]
    assert not v.resume(lignes)["tout_ok"]


def test_formater():
    assert v.formater(1586.98) == "1 586,98"
    assert v.formater(-0.00119048) == "−0,00119048"
    assert v.formater(1.2e-5, 2) == "1,2·10⁻⁵"
    assert v.formater(0.0) == "0"
    assert v.formater(float("nan")) == "–"

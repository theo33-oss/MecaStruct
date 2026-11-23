"""Flambement par les courbes de l'Eurocode 3 (EN 1993-1-1, 6.3.1) : valeurs refaites à la main dans le test.

Formules (courbe choisie par l'utilisateur ; le tableau 6.2 qui l'attribue aux profilés n'est pas implémenté) :
    λ̄ = √(A·fy/Ncr),  Ncr = π²·E·I/Lcr²
    Φ = 0,5·[1 + α·(λ̄ − 0,2) + λ̄²]
    χ = min(1 ; 1/(Φ + √(Φ² − λ̄²)))
    Nb,Rd = χ·A·fy/γM1
α : a0 0,13 ; a 0,21 ; b 0,34 ; c 0,49 ; d 0,76. Aucune valeur « golden » : chaque attendu est écrit ci-dessous.
"""

import math

import pytest

from mecastruct.core import buckling
from mecastruct.core.data_manager import DataManager
from mecastruct.core.errors import MecaStructError
from mecastruct.services import compute, criteres, validation_report
from mecastruct.services.examples import loadExample

E, FY, A, L = 210e9, 235e6, 1e-3, 2.0  # acier, 1 000 mm², barre de 2 m (articulée aux deux bouts : Lcr = L)
NPL = A * FY  # 235 000 N


def _inertie(lam: float) -> float:
    """Inertie qui donne exactement λ̄ = lam : Ncr = A·fy/λ̄² donc I = A·fy·Lcr²/(π²·E·λ̄²)."""
    return NPL * L**2 / (math.pi**2 * E * lam**2)


def _ec3(lam: float, courbe: str, gM1: float = 1.0, NEd=None) -> dict:
    p = {"E": E, "fy": FY, "A": A, "I": _inertie(lam), "Lcr": L, "curve": courbe, "gM1": gM1}
    if NEd is not None:
        p["NEd"] = NEd
    return buckling.eurocode3(p)


# ---------------------------------------------------------------------------------------- valeurs à la main


def test_lambda_1_courbe_b():
    """λ̄ = 1, courbe b (α = 0,34) : Φ = 0,5·(1 + 0,34·0,8 + 1) = 1,136 ; χ = 1/(1,136 + √(1,136² − 1)) ≈ 0,5970."""
    r = _ec3(1.0, "b")
    assert r["lambda"] == pytest.approx(1.0, rel=1e-12)
    assert r["Ncr"] == pytest.approx(NPL, rel=1e-12)  # λ̄ = 1 ⇔ Ncr = A·fy
    phi = 0.5 * (1 + 0.34 * 0.8 + 1)
    assert phi == pytest.approx(1.136)
    assert r["Phi"] == pytest.approx(1.136, rel=1e-12)
    chi = 1 / (1.136 + math.sqrt(1.136**2 - 1))  # √(1,290496 − 1) = √0,290496 = 0,538977… ; 1/1,674977 = 0,59702
    assert r["chi"] == pytest.approx(chi, rel=1e-12)
    assert r["chi"] == pytest.approx(0.5970, abs=5e-5)
    assert r["NbRd"] == pytest.approx(chi * 235000.0, rel=1e-12)  # χ·A·fy/γM1 avec γM1 = 1 : ≈ 140 300 N
    assert r["alpha"] == 0.34 and r["curve"] == "b" and r["ok"] is None and math.isnan(r["ratio"])


@pytest.mark.parametrize(
    ("courbe", "alpha"), [("a0", 0.13), ("a", 0.21), ("b", 0.34), ("c", 0.49), ("d", 0.76)]
)
def test_facteurs_d_imperfection_et_chi_des_cinq_courbes(courbe, alpha):
    """λ̄ = 1 pour chaque courbe : Φ = 0,5·(1 + 0,8·α + 1) = 1 + 0,4·α ; χ = 1/(Φ + √(Φ² − 1))."""
    r = _ec3(1.0, courbe)
    phi = 1 + 0.4 * alpha
    assert r["alpha"] == alpha
    assert r["Phi"] == pytest.approx(phi, rel=1e-12)
    assert r["chi"] == pytest.approx(1 / (phi + math.sqrt(phi**2 - 1)), rel=1e-12)


def test_lambda_2_courbe_d():
    """λ̄ = 2, courbe d : Φ = 0,5·(1 + 0,76·1,8 + 4) = 3,184 ; χ = 1/(3,184 + √(3,184² − 4)) = 1/(3,184 + 2,47745) ≈ 0,17662."""
    r = _ec3(2.0, "d")
    assert r["Phi"] == pytest.approx(3.184, rel=1e-12)
    assert r["chi"] == pytest.approx(1 / (3.184 + math.sqrt(3.184**2 - 4)), rel=1e-12)
    assert r["chi"] == pytest.approx(0.17662, abs=5e-5)


def test_gamma_m1_divise_la_resistance():
    """Nb,Rd = χ·A·fy/γM1 : γM1 = 1,2 divise la résistance par 1,2 ; χ ne change pas."""
    r1, r2 = _ec3(1.0, "b", 1.0), _ec3(1.0, "b", 1.2)
    assert r2["chi"] == r1["chi"]
    assert r2["NbRd"] == pytest.approx(r1["NbRd"] / 1.2, rel=1e-12)
    assert r2["NbRd"] == pytest.approx(0.5970 * 235000.0 / 1.2, rel=1e-4)


def test_taux_et_verdict_avec_NEd():
    """NEd/Nb,Rd : 100 kN sur Nb,Rd ≈ 140,3 kN donne ≈ 0,7128 (vérifié) ; 200 kN donne ≈ 1,4255 (non vérifié) ; le signe est ignoré."""
    nb = (1 / (1.136 + math.sqrt(1.136**2 - 1))) * 235000.0
    bon = _ec3(1.0, "b", NEd=100e3)
    assert bon["ratio"] == pytest.approx(100e3 / nb, rel=1e-12) and bon["ok"] is True
    mauvais = _ec3(1.0, "b", NEd=-200e3)
    assert mauvais["NEd"] == 200e3
    assert mauvais["ratio"] == pytest.approx(200e3 / nb, rel=1e-12) and mauvais["ok"] is False
    assert _ec3(1.0, "b", NEd=nb * (1 - 1e-9))["ok"] is True  # juste sous la limite
    assert _ec3(1.0, "b", NEd=nb * (1 + 1e-9))["ok"] is False  # juste au-dessus


def test_exemple_complet_Ncr_lambda_chi():
    """Barre réelle : E = 210 GPa, fy = 235 MPa, A = 1 000 mm², I = 5·10⁵ mm⁴, Lcr = 3 m, courbe c, γM1 = 1,1 (essai).

    Ncr = π²·210e9·5e-7/9 = 115 145 N ; λ̄ = √(235000/115145) = 1,4286 ; Φ = 0,5·(1 + 0,49·1,2286 + 2,0408) ;
    χ = 1/(Φ + √(Φ² − λ̄²)) ; Nb,Rd = χ·235000/1,1. Les étapes sont refaites ici une à une.
    """
    Ncr = math.pi**2 * 210e9 * 5e-7 / 3.0**2
    lam = math.sqrt(235000.0 / Ncr)
    phi = 0.5 * (1 + 0.49 * (lam - 0.2) + lam**2)
    chi = 1 / (phi + math.sqrt(phi**2 - lam**2))
    r = buckling.eurocode3({"E": 210e9, "fy": 235e6, "A": 1e-3, "I": 5e-7, "Lcr": 3.0, "curve": "c", "gM1": 1.1, "NEd": 50e3})
    assert Ncr == pytest.approx(115145.0, rel=1e-5) and lam == pytest.approx(1.4286, abs=1e-4)
    assert r["Ncr"] == pytest.approx(Ncr, rel=1e-12) and r["lambda"] == pytest.approx(lam, rel=1e-12)
    assert r["Phi"] == pytest.approx(phi, rel=1e-12) and r["chi"] == pytest.approx(chi, rel=1e-12)
    assert r["NbRd"] == pytest.approx(chi * 235000.0 / 1.1, rel=1e-12)
    assert r["ratio"] == pytest.approx(50e3 / (chi * 235000.0 / 1.1), rel=1e-12)
    assert len(r["latex"]) == 6 and all(x.startswith("$") and x.endswith("$") for x in r["latex"])
    assert any("Nb,Rd" in ligne for ligne in r["report"])


# ---------------------------------------------------------------------------------------- cas limites


@pytest.mark.parametrize("courbe", ["a0", "a", "b", "c", "d"])
def test_lambda_petit_donne_chi_1(courbe):
    """λ̄ = 0,1 ≤ 0,2 : la formule brute donne χ > 1 (Φ = 0,5·(1 − 0,1·α + 0,01)), on retient χ = 1 et Nb,Rd = A·fy/γM1."""
    r = _ec3(0.1, courbe, 1.25)
    alpha = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}[courbe]
    phi = 0.5 * (1 + alpha * (0.1 - 0.2) + 0.01)
    brut = 1 / (phi + math.sqrt(phi**2 - 0.01))
    assert brut > 1 and r["chiRaw"] == pytest.approx(brut, rel=1e-12)
    assert r["chi"] == 1.0
    assert r["NbRd"] == pytest.approx(235000.0 / 1.25, rel=1e-12)


def test_lambda_0_2_donne_exactement_chi_1():
    """λ̄ = 0,2 : Φ = 0,5·(1 + 0 + 0,04) = 0,52 ; √(0,52² − 0,04) = √0,2304 = 0,48 ; χ = 1/(0,52 + 0,48) = 1, quelle que soit la courbe."""
    for courbe in ("a0", "a", "b", "c", "d"):
        r = _ec3(0.2, courbe)
        assert r["Phi"] == pytest.approx(0.52, rel=1e-12)
        assert r["chi"] == pytest.approx(1.0, rel=1e-12)


def test_lambda_grand_tend_vers_euler():
    """λ̄ = 5, courbe a : Φ = 0,5·(1 + 0,21·4,8 + 25) = 13,504 ; χ = 1/(13,504 + √(13,504² − 25)) ≈ 0,03839, proche de 1/λ̄² = 0,04."""
    r = _ec3(5.0, "a")
    assert r["Phi"] == pytest.approx(13.504, rel=1e-12)
    chi = 1 / (13.504 + math.sqrt(13.504**2 - 25))
    assert r["chi"] == pytest.approx(chi, rel=1e-12) and r["chi"] == pytest.approx(0.03839, abs=1e-5)
    assert r["chi"] < 1 / 25  # sous la courbe d'Euler (χ = 1/λ̄²) : l'imperfection retire de la résistance
    assert r["NbRd"] == pytest.approx(chi * NPL, rel=1e-12)


def test_courbe_ecrite_en_majuscules_ou_avec_espaces():
    assert _ec3(1.0, " B ")["curve"] == "b"
    assert _ec3(1.0, "A0")["alpha"] == 0.13


@pytest.mark.parametrize("courbe", ["e", "z", "", "a1", None, 3, "courbe b"])
def test_courbe_invalide_refusee_en_francais(courbe):
    with pytest.raises(MecaStructError) as err:
        buckling.eurocode3({"E": E, "fy": FY, "A": A, "I": 1e-6, "Lcr": L, "curve": courbe})
    msg = str(err.value)
    assert "Courbe de flambement inconnue" in msg and "a0, a, b, c, d" in msg and "tableau 6.2" in msg


@pytest.mark.parametrize("champ", ["E", "fy", "A", "I", "Lcr", "gM1"])
@pytest.mark.parametrize("valeur", [0.0, -1.0, math.nan, math.inf])
def test_saisie_nulle_ou_negative_refusee(champ, valeur):
    p = {"E": E, "fy": FY, "A": A, "I": 1e-6, "Lcr": L, "curve": "b", "gM1": 1.0}
    p[champ] = valeur
    with pytest.raises(MecaStructError) as err:
        buckling.eurocode3(p)
    assert "strictement positif" in str(err.value)


def test_champ_manquant_et_NEd_invalide():
    with pytest.raises(MecaStructError, match="manquant"):
        buckling.eurocode3({"E": E, "fy": FY, "A": A, "I": 1e-6, "Lcr": L})
    with pytest.raises(MecaStructError, match="NEd"):
        buckling.eurocode3({"E": E, "fy": FY, "A": A, "I": 1e-6, "Lcr": L, "curve": "b", "NEd": math.inf})


def test_gamma_m1_absent_vaut_1():
    p = {"E": E, "fy": FY, "A": A, "I": _inertie(1.0), "Lcr": L, "curve": "b"}
    assert buckling.eurocode3(p)["gM1"] == 1.0


# ---------------------------------------------------------------------------------------- page Flambage


def _saisie(**modif) -> dict:
    return {**loadExample("Fla"), **modif}


def test_un_ancien_fichier_sans_les_champs_ec3_se_calcule():
    """Une saisie d'avant l'Eurocode 3 (sans ec3, courbe, gM1) donne le même résultat qu'avant : pas de bloc ec3."""
    ancienne = {k: v for k, v in loadExample("Fla").items() if k not in ("ec3", "courbe", "gM1")}
    res = compute.computeBuckling(ancienne, DataManager())
    assert "ec3" not in res["result"] and "Eurocode" not in res["status"]
    assert criteres.criteres("fla", ancienne, res)[0]["mode"] == "Flambage : charge P"
    assert len(criteres.criteres("fla", ancienne, res)) == 1


def test_euler_inchange_quand_ec3_est_coche():
    dm = DataManager()
    seul = compute.computeBuckling(_saisie(), dm)["result"]["analysis"]
    avec = compute.computeBuckling(_saisie(ec3=True), dm)["result"]["analysis"]
    for cle in ("lambda", "PE", "PR", "PC", "Pcrit", "Padm", "regime", "ok"):
        assert seul[cle] == avec[cle]


def test_page_ec3_HEA200_resultat_critere_et_formules():
    """Exemple (HEA 200, S235, articulé-articulé, L = 4 m, P = 300 kN) : toutes les étapes refaites depuis les données."""
    dm = DataManager()
    s = _saisie(ec3=True, courbe="b", gM1=1.0)
    res = compute.computeBuckling(s, dm)
    e = res["result"]["ec3"]
    A_, I_ = s["S"] * 1e-6, min(s["Iz"], s["Iy"]) * 1e-12  # m², m⁴ (Imin)
    Ncr = math.pi**2 * (s["E"] * 1e9) * I_ / s["L"] ** 2  # articulé-articulé : Lcr = L
    lam = math.sqrt(A_ * s["Re"] * 1e6 / Ncr)
    phi = 0.5 * (1 + 0.34 * (lam - 0.2) + lam**2)
    chi = min(1.0, 1 / (phi + math.sqrt(phi**2 - lam**2)))
    nb = chi * A_ * s["Re"] * 1e6
    assert e["Ncr"] == pytest.approx(Ncr, rel=1e-12) and e["lambda"] == pytest.approx(lam, rel=1e-12)
    assert e["chi"] == pytest.approx(chi, rel=1e-12) and e["NbRd"] == pytest.approx(nb, rel=1e-12)
    assert e["ratio"] == pytest.approx(300e3 / nb, rel=1e-12)
    # verdict dans la ligne d'état, un critère de plus dans le diagramme, formules LaTeX et démarche
    assert "Nb,Rd (EC3)" in res["status"] and ("vérifié" in res["status"])
    lignes = criteres.criteres("fla", s, res)
    assert [x["mode"] for x in lignes if "Eurocode" in x["mode"]] == ["Flambement Eurocode 3 : NEd / Nb,Rd"]
    ligne = next(x for x in lignes if "Eurocode" in x["mode"])
    assert ligne["taux"] == pytest.approx(300e3 / nb, rel=1e-12) and ligne["ok"] == (300e3 <= nb)
    assert any("Eurocode 3" in t for t in res["result"]["rapport"])
    blocs = validation_report.solverEquations("Fla", res)
    assert [nom for nom, _ in blocs] == ["Flambage", "Flambement Eurocode 3 (courbe choisie)"]
    lignes_main = validation_report.explanationRows("Fla", s, res, dm)
    ec3 = [x for x in lignes_main if x["hand"] is not None and ("Ncr" in x["label"] or x["label"] in ("Coefficient de réduction", "Résistance au flambement", "Taux d'utilisation"))]
    assert len(ec3) == 4
    assert all(validation_report.explanationVerdict(x)[1] for x in lignes_main if x["hand"] is not None)


def test_page_ec3_non_verifie_rend_le_calcul_non_verifie():
    """P trop grand pour Nb,Rd : le calcul est « NON vérifié » (un seul mode non admissible suffit)."""
    res = compute.computeBuckling(_saisie(ec3=True, P=1500.0, s=1.0), DataManager())
    assert res["result"]["ec3"]["ok"] is False
    assert "NON vérifié" in res["status"]
    assert criteres.verdict(res["status"]) is False


def test_page_ec3_sans_charge_pas_de_verdict_ec3():
    res = compute.computeBuckling(_saisie(ec3=True, P=0.0), DataManager())
    e = res["result"]["ec3"]
    assert e["ok"] is None and math.isnan(e["ratio"]) and "Nb,Rd (EC3)" in res["status"]
    assert all("Eurocode" not in x["mode"] for x in criteres.criteres("fla", _saisie(ec3=True, P=0.0), res))


def test_page_ec3_courbe_invalide_ou_gamma_nul_refuses():
    dm = DataManager()
    with pytest.raises(MecaStructError, match="Courbe de flambement inconnue"):
        compute.computeBuckling(_saisie(ec3=True, courbe="x"), dm)
    with pytest.raises(MecaStructError, match="γM1"):
        compute.computeBuckling(_saisie(ec3=True, gM1=0.0), dm)
    # EC3 non coché : une courbe absurde n'est pas lue
    compute.computeBuckling(_saisie(ec3=False, courbe="x"), dm)


# ---------------------------------------------------------------------------------------- page du bureau


@pytest.mark.qt
def test_bureau_page_flambage_ec3(bureau):
    """Bureau : on coche l'Eurocode 3, on choisit la courbe, le calcul ajoute Nb,Rd et un mode de ruine."""
    from mecastruct.bureau import state

    bureau.ouvre("flambage")
    bureau.ouvre_volet("Eurocode 3 : courbes de flambement (EN 1993-1-1, 6.3.1)")
    assert not bureau.champ("γM1, coefficient partiel (stabilité) (-)").isEnabled()
    bureau.case("Vérifier aussi par les courbes de l'Eurocode 3", True)
    assert bureau.champ("γM1, coefficient partiel (stabilité) (-)").isEnabled()
    bureau.choisit("Courbe de flambement", "c (α = 0,49)")
    bureau.clique("Calculer")
    e = state.result("Fla")["result"]["ec3"]
    assert e["curve"] == "c" and e["alpha"] == 0.49
    assert bureau.a_texte("Flambement Eurocode 3")

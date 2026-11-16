"""Exemples chiffrés des cours et des TP de l'auteur (dossier « Calculs ») : l'application doit les retrouver.

Chaque test cite son document et sa page. Les résultats imprimés dans les cours sont repris tels quels ; quand le cours
se trompe, le test écrit la valeur juste et dit pourquoi. Références : data/references.json.
"""

import math

import pytest

from mecastruct.core import bearings, design_checks, geometry, kt_mohr
from mecastruct.core.data_manager import DataManager
from mecastruct.services import beam_services, compute
from mecastruct.services import machine_courses as mc
from mecastruct.services.examples import loadExample

DM = DataManager()


def poutre(**champs):
    """Saisie Poutres de l'exemple (IPE 300, S235, E = 210 GPa) avec les champs donnés."""
    s = beam_services.defaultBeamInput()
    s.update(champs)
    return s


def fleche_mm(s: dict) -> float:
    return beam_services.computeBeam(s, DM)["defl"]["integration"]["fmax"] * 1e3


# ---------------------------------------------------------------------------------------------- RdM


def test_section_rectangle_100_x_200_comme_l_export_de_l_application():
    """MecaStruct_Sec.xlsx (feuille « Tableau de Huygens ») : b = 100, h = 200 mm."""
    s = loadExample("Sec")
    s.update(type="rectangle", b=100.0, h=200.0)
    P = compute.computeSection(s, DM)["result"]["P"]
    assert P["S"] * 1e6 == pytest.approx(20000, rel=1e-12)
    assert P["Iz"] * 1e12 == pytest.approx(6.66667e7, rel=1e-5)
    assert P["Iy"] * 1e12 == pytest.approx(1.66667e7, rel=1e-5)
    assert P["Ix"] * 1e12 == pytest.approx(8.33333e7, rel=1e-5)  # « Ix » du classeur = Iz + Iy
    assert P["Wz"] * 1e9 == pytest.approx(6.66667e5, rel=1e-5)
    assert P["Wy"] * 1e9 == pytest.approx(3.33333e5, rel=1e-5)


def test_treillis_efforts_et_reactions_de_l_export_MecaStruct_Tr():
    """MecaStruct_Tr.pdf : N1 à N7 (kN) et réactions du treillis de l'exemple (le cours ne dépend pas de E)."""
    res = compute.computeTruss(loadExample("Tr"), DM)["tables"]
    attendu = [18.75, 16.25, -22.92, 10.42, -20.0, 14.58, -27.08]
    assert list(res["Barres"]["N (kN)"]) == pytest.approx(attendu, abs=0.005)
    assert list(res["Réactions"]["Rx (kN)"]) == pytest.approx([-5.0, 0.0], abs=1e-9)
    assert list(res["Réactions"]["Ry (kN)"]) == pytest.approx([18.33, 21.67], abs=0.005)


def test_arbre_en_torsion_28_mm_refuse_et_29_mm_accepte():
    """Td1_221012 (p. 1) : P = 73,3 kW à 1500 tr/min, σe = 600 MPa, s = 3, Tresca. Le cours arrondit D à 28 mm ; avec
    τmax = 108,3 MPa pour 100 MPa admissibles, le premier diamètre qui convient est 29 mm."""
    mt = 30 * 73.3e3 / (math.pi * 1500) / 1e3  # kN·m
    assert mt == pytest.approx(0.46664, abs=1e-5)  # Mt = 30P/(πN)

    def calcul(D: float) -> dict:
        s = loadExample("Tor")
        s.update(Mt=mt, D=D, d=0.0, L=1.0, Re=600.0, s=3.0, crit="Tresca", thetaAdm=0.0)
        return compute.computeTorsion(s, DM)

    r28, r29 = calcul(28.0), calcul(29.0)
    assert r28["result"]["tauMax"] / 1e6 == pytest.approx(108.26, abs=0.01) and "NON vérifié" in r28["status"]
    assert r29["result"]["tauMax"] / 1e6 == pytest.approx(97.44, abs=0.01) and "τmax = 97.445 MPa (vérifié)" in r29["status"]
    # même arbre, D = 50 mm : le cours demande σe ≥ 114 MPa, soit s·τmax·2
    s = loadExample("Tor")
    s.update(Mt=mt, D=50.0, d=0.0, Re=600.0, s=3.0, crit="Tresca", thetaAdm=0.0)
    tau = compute.computeTorsion(s, DM)["result"]["tauMax"] / 1e6
    assert 2 * 3 * tau == pytest.approx(114.08, abs=0.01)


def test_consoles_du_moment_des_aires():
    """Moment des airs.pdf (p. 1-2) : console de longueur L, charge à 3L/4 de l'encastrement.
    Force : f = 27·F·L³/(128·E·I). Charge répartie sur [0 ; 3L/4] : f = 117·q·L⁴/(2048·E·I)."""
    E, I, L = 210000.0, 8.356e7, 2000.0  # N/mm², mm⁴, mm (IPE 300)
    appui = [{"pos": 0.0, "type": "encastrement", "name": "A"}]
    force = poutre(L=2.0, sup=appui, dl=[], pl=[{"pos": 1.5, "Fx": 0.0, "Fy": -10.0, "Fz": 0.0, "name": "F", "case": "Q"}])
    assert fleche_mm(force) == pytest.approx(27 * 10e3 * L**3 / (128 * E * I), rel=1e-3)
    reparti = poutre(L=2.0, sup=appui, pl=[],
                     dl=[{"a": 0.0, "b": 1.5, "dir": "y", "type": "uniforme", "vals": "-10", "name": "q", "case": "G"}])  # fmt: skip
    assert fleche_mm(reparti) == pytest.approx(117 * 10 * L**4 / (2048 * E * I), rel=1e-3)


def test_flexion_trois_points_du_tp2_acier_a_210_gpa():
    """TP2 (flexion trois points, acier à plat 25,02 × 5,96 mm, L = 1 m, 9,81 N) : flèche mesurée 2,19 mm. Avec
    E = 210 GPa (la base) la flèche calculée est 2,205 mm ; avec 190 GPa elle serait 2,44 mm."""
    iz = 25.02 * 5.96**3 / 12
    s = poutre(L=1.0, Iz=iz, E=210.0, dl=[], sup=[{"pos": 0.0, "type": "pivot", "name": "A"},
                                                   {"pos": 1.0, "type": "appui_simple", "name": "B"}],
               pl=[{"pos": 0.5, "Fx": 0.0, "Fy": -9.81e-3, "Fz": 0.0, "name": "P", "case": "Q"}])  # fmt: skip
    assert fleche_mm(s) == pytest.approx(2.205, abs=0.002)
    assert abs(fleche_mm(s) - 2.19) / 2.19 < 0.01
    assert fleche_mm({**s, "E": 190.0}) == pytest.approx(2.437, abs=0.002)


# ------------------------------------------------------------------------------------------ fatigue


def test_goodman_annale_2018_exercice_2():
    """4TGA901U (fatigue, annale de décembre 2018, p. 95) : Rm = 1200 MPa, σD = 600 MPa, σa = 2,5·σm : σmax = 700 MPa,
    R = −0,4286 donnent exactement n = 1 sur la droite de Goodman."""
    r = design_checks.goodman(700e6, -3 / 7, 1.0, 1200e6, 1.0, 1.0)
    assert r["sigmaA"] / 1e6 == pytest.approx(500, rel=1e-9) and r["sigmaM"] / 1e6 == pytest.approx(200, rel=1e-9)
    assert r["n"] == pytest.approx(1.0, abs=1e-9)


def test_kf_sur_la_contrainte_moyenne_annale_2018_question_4():
    """Même annale, Q4 : Kf = 1,44, KS = 0,8, Ke = 0,9, σa = 250 et σm = 100 MPa. Le cours (p. 95) applique les coefficients
    d'influence aux amplitudes et aux moyennes : n = 1,049 ; en ne l'appliquant qu'à l'amplitude on trouve 1,091 (+4 %)."""
    sig_max, R = 350e6, -3 / 7
    seul_amplitude = design_checks.goodman(sig_max, R, 1.44, 1200e6, 0.8, 0.9)
    aussi_moyenne = design_checks.goodman(sig_max, R, 1.44, 1200e6, 0.8, 0.9, KfMoyenne=True)
    assert seul_amplitude["n"] == pytest.approx(1.0909, abs=1e-4)
    assert aussi_moyenne["n"] == pytest.approx(1.0490, abs=1e-4)


def test_alliage_al_cu_limite_d_endurance_mesuree():
    """4TGA901U (p. 84, exercice Al-Cu) : Rm = 580 MPa, σD(10⁷) = 200 MPa mesurée. Goodman à R = 0 : σmax = 297,4 MPa
    donne n = 1. L'estimation 0,5·Rm de l'acier (290 MPa) donnerait n = 1,30 : elle ne vaut pas pour cet alliage."""
    sig_max = 2 / (1 / 200 + 1 / 580) * 1e6
    assert design_checks.goodman(sig_max, 0.0, 1.0, 580e6, 1.0, 1.0, Sd=200e6)["n"] == pytest.approx(1.0, abs=1e-9)
    assert design_checks.goodman(sig_max, 0.0, 1.0, 580e6, 1.0, 1.0)["n"] == pytest.approx(1.30, abs=0.005)


def test_fatigue_de_la_poutre_avertit_pour_un_alliage_sans_limite_d_endurance_saisie():
    from mecastruct.services import beam_design

    s = poutre(mat="Aluminium 6061-T6", E=70.0, G=26.3, Re=240.0)
    _, tableau = beam_design.checkFatigue(s, DM)
    assert any("Avertissement" in str(ligne) and "acier" in str(ligne) for ligne in tableau.to_numpy().tolist())
    _, avec_sd = beam_design.checkFatigue({**s, "fSd": 130.0}, DM)
    assert not any("Avertissement" in str(ligne) for ligne in avec_sd.to_numpy().tolist())
    with pytest.raises(Exception, match="Kf"):
        beam_design.checkFatigue({**s, "fKf": 99.0}, DM)  # Kf ≤ Kt (cours p. 59)


def test_kt_arbre_epaule_en_traction_du_cours_de_fatigue():
    """4TGA901U (p. 80) : arbre D = 180, d = 100, r = 10 mm en traction, Kt = 1,95 lu sur l'abaque. L'ajustement de
    Peterson de l'application donne 1,98 (+1,6 %)."""
    kt = float(kt_mohr.evalKt("arbre_epaulement_traction", [10 / 100, 180 / 100]))
    assert kt == pytest.approx(1.981, abs=0.002)
    assert abs(kt - 1.95) / 1.95 < 0.03


# ------------------------------------------------------------------------ milieux continus, Hooke


def _tenseur(sigma):
    s = loadExample("Ten")
    s.update(sig=sigma, mat="S235", Re=235.0, s=1.0)
    return compute.computeTensor(s, DM)


def test_flexion_pure_von_mises_egale_la_contrainte():
    """DST 2021-2022 (corrigé p. 3, Q2-Q5) : σ = −(Mx2/I)·e1⊗e1 ; σVM = |Mx2/I| = 100 MPa pour Mx2/I = 100 ; la
    pression moyenne est −σ/3 et le déviateur −(Mx2/3I)·diag(2, −1, −1) : J2 = ½ s:s = σ²/3."""
    r = _tenseur([[-100.0, 0, 0], [0, 0, 0], [0, 0, 0]])
    criteres = r["tables"]["Critères"].set_index("Critère")["σ équivalente (MPa)"]
    assert criteres["Von Mises"] == pytest.approx(100.0, rel=1e-12)
    assert criteres["Tresca"] == pytest.approx(100.0, rel=1e-12)
    p = r["result"]["principal"]
    assert p["sigmaI"] == pytest.approx(0, abs=1e-6) and p["sigmaIII"] / 1e6 == pytest.approx(-100.0, rel=1e-9)


def test_poutre_suspendue_von_mises_et_deformations():
    """DST 2021-2022 (corrigé p. 5-6, Q7-Q8) : σ33 = γ·X3 (50 MPa ici) : σVM = σ33 ; ε = (σ33/E)·diag(−ν, −ν, 1)."""
    r = _tenseur([[0, 0, 0], [0, 0, 0], [0, 0, 50.0]])
    assert r["tables"]["Critères"].set_index("Critère")["σ équivalente (MPa)"]["Von Mises"] == pytest.approx(50.0, rel=1e-12)
    h = loadExample("Hoo")
    h.update(mode="iso3D", E=210.0, nu=0.3, sxx=0.0, syy=0.0, szz=50.0, sxy=0.0, sxz=0.0, syz=0.0, alpha=12.0, dT=0.0)
    eps = compute.computeHooke(h, DM)["tables"]["Résultats"].set_index("Déformation")["Valeur (µdéf)"]
    assert [eps["εxx"], eps["εyy"], eps["εzz"]] == pytest.approx([-71.429, -71.429, 238.095], abs=0.001)


def test_hooke_flexion_pure_dst_2021():
    """DST 2021-2022 (corrigé p. 3, Q1) : ε = −(Mx2/EI)·diag(1, −ν, −ν), E = 210 GPa, ν = 0,3, σ = −100 MPa."""
    h = loadExample("Hoo")
    h.update(mode="iso3D", E=210.0, nu=0.3, sxx=-100.0, syy=0.0, szz=0.0, sxy=0.0, sxz=0.0, syz=0.0, alpha=12.0, dT=0.0)
    eps = compute.computeHooke(h, DM)["tables"]["Résultats"].set_index("Déformation")["Valeur (µdéf)"]
    assert [eps["εxx"], eps["εyy"], eps["εzz"]] == pytest.approx([-476.190, 142.857, 142.857], abs=0.001)


# ------------------------------------------------------------------------------------- roulements


def test_roulement_6405_exemple_du_cours_et_son_erreur():
    """« Calcul sur les roulements » (p. 19) : C = 35,8 kN, Fr = 1000 daN, Fa = 400 daN, 300 tr/min, e = 0,38, X = 0,56,
    Y = 1,31. P = 1084 daN (juste). Le cours annonce L10 = 185,3 M tours, 10 294 h : c'est (61,8/10,84)³, le résultat
    d'un roulement de C = 61,8 kN. Avec C = 35,8 kN : 36,0 M tours, 2001 h."""
    s = {**mc.defaultBearingInput(), "tableau": False, "e": 0.38, "X": 0.56, "Y": 1.31}
    r = mc.computeBearingLife(s)["result"]
    assert r["P"] == pytest.approx(10840.0, rel=1e-12)
    assert r["L10"] == pytest.approx(36.02, abs=0.01) and r["L10h"] == pytest.approx(2001.2, abs=0.1)
    cours = mc.computeBearingLife({**s, "C": 61800.0})["result"]
    assert cours["L10"] == pytest.approx(185.30, abs=0.01) and cours["L10h"] == pytest.approx(10294, abs=1)


def test_interpolation_de_la_table_e_y_et_coquilles_du_cours():
    """« Calcul sur les roulements » (p. 18), Fa/C0 = 0,064 : le cours écrit e = « 0,0265 » (coquille pour 0,2657) et
    Y = 1,59 (pente inversée). L'interpolation linéaire de la table donne e = 0,2657 et Y = 1,664."""
    e, y = bearings.eYInterpolated(0.064)
    assert e == pytest.approx(0.2657, abs=1e-4) and y == pytest.approx(1.664, abs=0.001)


def test_fiabilite_et_ensembles_de_roulements_du_cours():
    """« Calcul sur les roulements » : a1(96 %) = 0,53 (p. 11) ; deux durées de 15 000 h et 25 000 h donnent 11 630 h ;
    deux roulements iso-fiables de guidage 15 000 h durent 23 811 h chacun (p. 12)."""
    assert bearings.reliabilityFactor(0.96) == pytest.approx(0.53, abs=0.005)  # 0,5315 (le cours arrondit à 0,53)
    r = mc.computeBearingSet(mc.defaultBearingSetInput())["result"]
    assert r["LE"] == pytest.approx(11630.0, abs=0.1) and r["Liso"] == pytest.approx(23811.0, abs=0.1)


def test_bague_interieure_a_charge_indefinie_comme_la_tournante():
    """« Liaison pivot par roulements » (p. 25) : la bague intérieure « tournante ou direction de charge non définie » est
    sur la même ligne du tableau ; à partir de m5, jeu interne augmenté."""
    for charge in ("faible", "normale", "importante", "importante avec chocs"):
        assert bearings.fitRule("intérieure", "indéfinie", charge) == bearings.fitRule("intérieure", "tournante", charge)
    assert bearings.mountingRule("intérieure", "indéfinie") == "serrée"
    assert bearings.needsLargerClearance(*bearings.fitRule("intérieure", "tournante", "importante"))
    assert not bearings.needsLargerClearance(*bearings.fitRule("intérieure", "tournante", "normale"))


# ------------------------------------------------------------------ transmission, freins, moteur


def test_train_d_engrenages_premier_etage_de_l_exemple():
    """« Engrenages droits » (p. 24) : 1000 W à 500 tr/min, η = 0,98, étage 16/46 : arbre intermédiaire 980 W, 173 tr/min,
    54 N·m."""
    s = {**mc.defaultGearTrainInput(), "Z1": 16, "Z2": 46, "Z3": 19, "Z4": 59, "Z5": 17, "Z6": 85}
    ligne = mc.computeGearTrain(s)["result"]["lignes"][1]
    assert abs(ligne["N"]) == pytest.approx(173.9, abs=0.1)
    assert ligne["P"] == pytest.approx(980.0, abs=0.01) and ligne["C"] == pytest.approx(53.8, abs=0.1)


def test_train_epicycloidal_exemple_du_cours():
    """R4.05 ICM S4 « Train épicycloïdal » (p. 19) : Z1 = 15, Z2 = 9, Z4 = 33, couronne bloquée, ω1 = 157 rad/s : le
    porte-satellites tourne à ω3 = 49 rad/s."""
    r = mc.computePlanetary(mc.defaultPlanetaryInput())["result"]
    assert 157 * r["r"] == pytest.approx(49.06, abs=0.01)
    assert r["rb"] == pytest.approx(-15 / 33, abs=1e-12)


def test_embrayage_couple_d_acceleration_du_cours():
    """R5.05 ICM S5 « Frein – Embrayage » (p. 18-19) : JR = 1,2 kg·m², 1500 tr/min, ts = 10 s : couple d'accélération
    18,8 N·m, couple résistant 55 N·m."""
    r = mc.computeClutch(mc.defaultClutchInput())["result"]
    assert r["Cacc"] == pytest.approx(18.85, abs=0.01) and r["CT"] == pytest.approx(55 + r["Cacc"], rel=1e-12)


def test_moteur_ascenseur_couple_thermique_61_nm():
    """« Chaînes de transmission de puissance » (p. 17-18) : 120 N·m en accélération, 54 N·m en régime établi, 0 au
    freinage. Accélération = freinage = vmax/γmax = 0,5 s ; le régime établi (4,32 s) est déduit pour C_th = 61 N·m."""
    s = mc.defaultMotorInput()
    assert (s["ta"], s["tfr"]) == (0.5, 0.5) and 1.0 / 2.0 == s["ta"]
    assert mc.computeMotor(s)["result"]["Cth"] == pytest.approx(61.0, abs=0.01)


# --------------------------------------------------------------------------------------- données


def test_alesage_et_arbre_du_tableau_du_guidage_p26():
    """« Liaison pivot par roulements » (p. 26) : Ø40 k6 pour la bague intérieure tournante, charge normale ; Ø60 N7 pour la
    bague extérieure tournante, charge normale."""
    assert bearings.fitRule("intérieure", "tournante", "normale") == ("arbre", "k5 à k6")
    assert bearings.fitRule("extérieure", "tournante", "normale") == ("alésage", "N7")


def test_g_de_l_acier_est_e_sur_2_un_plus_nu():
    """Rapport de matériaux et feuille de torsion (« Essai 2.xlsx ») : E = 210 GPa, ν = 0,3, G = 80 769 MPa."""
    m = DM.getMaterial("S235")
    assert m["E"] == 210e9 and m["G"] / 1e6 == pytest.approx(80769.2, abs=0.1)
    assert geometry is not None  # module importé pour les sections de ce fichier

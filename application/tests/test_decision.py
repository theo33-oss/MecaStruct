"""Bloc « Décision » (services/decision.py) : verdict, coefficient minimal, mode dimensionnant, action, causes, avertissements.

Même contenu que le bloc du site (docs/js/machine.js) ; logique sans Qt.
"""

import pytest

from mecastruct.services import criteres, decision
from mecastruct.services.decision import CAUSES, avertissement, causes, cle_champ, construire, libelle_mode


def resistance(mode="Flexion composée : Kt·σ max", valeur=100.0, limite=150.0, s=1.5, groupe=""):
    return criteres.ligne(mode, valeur, limite, "MPa", s, groupe=groupe)


def limite(mode="Durée de vie Lnh", valeur=5000.0, lim=10000.0):
    return criteres.ligne(mode, valeur, lim, "h", genre="limite")


def duree(valeur, requis=10000.0):  # durée de vie : la valeur doit rester au-dessus de la limite
    return criteres.ligne("Durée de vie Lnh", valeur, requis, "h", sens="min", genre="limite")


def faits(d):
    return {f.titre: f for f in d.faits}


def test_conforme_donne_le_coefficient_minimal_et_le_mode_dimensionnant():
    c = resistance(valeur=100.0, limite=150.0, s=1.5)  # σadm = 150/1,5... s obtenu = 150 * 1,5 / 100 = 2,25
    d = construire("tra", [c], True)
    assert (d.niveau, d.icone, d.mot) == ("ok", "✓", "Conforme")
    f = faits(d)
    assert f["Coefficient de sécurité minimal"].valeur == "s = 2,25"
    assert f["Coefficient de sécurité minimal"].sous == "demandé 1,5"
    assert f["Mode dimensionnant"].valeur == c["mode"] and f["Mode dimensionnant"].sous == "taux 66,7 %"
    assert d.action == "Aucune action requise : tous les critères sont admissibles."
    assert d.cause == [] and d.court == "Conforme · s min 2,25"


def test_non_conforme_propose_l_action_et_la_cause():
    c = resistance(valeur=200.0, limite=150.0, s=1.5)
    d = construire("tra", [c], False)
    assert (d.niveau, d.mot) == ("ko", "Non conforme")
    assert d.action == f"Réduire la charge ou augmenter la section pour « {c['mode']} »."
    assert d.cause == ["S0"] and d.nom_cause == c["mode"]
    assert faits(d)["Paramètre le plus influent"].champ == "S0"


def test_critere_hors_resistance_donne_une_reserve_et_une_autre_action():
    d = construire("rlt", [limite()], True)
    f = faits(d)
    assert "Coefficient de sécurité minimal" not in f and f["Réserve minimale"].valeur == "50 %"
    assert construire("rlt", [limite(valeur=20000.0, lim=10000.0)], False).action.startswith("Revoir la charge ou les dimensions")
    d = construire("rlt", [duree(1000.0)], False)  # durée de 1000 h pour 10 000 h requises : taux 10, dépassement 900 %
    assert faits(d)["Dépassement"].valeur == "900 %"


def test_reserve_jamais_arrondie_a_100():
    assert decision.reserve(0.0) == "100"
    assert decision.reserve(0.0001) == "> 99,9"
    assert decision.reserve(0.5) == "50"


def test_marge_de_securite_au_lieu_du_coefficient():
    d = construire("tra", [resistance(valeur=100.0, limite=150.0, s=1.5)], True, en_marge=True)
    f = faits(d)["Marge de sécurité minimale"]
    assert f.valeur == "125 %" and f.sous == "demandée 50 %"
    assert d.court == "Conforme · marge min 125 %"


def test_a_verifier_quand_les_criteres_sont_admissibles_sans_verdict():
    d = construire("ossature", [resistance(s=1.0)], None)
    assert (d.niveau, d.mot) == ("neutre", "À vérifier")
    assert d.action == "Vérifiez les hypothèses."


def test_information_sans_critere_de_conformite():
    d = construire("aju", [], None)
    assert (d.niveau, d.icone, d.mot) == ("info", "ℹ", "Information")
    assert d.faits == [] and d.action == "Ce calcul donne des valeurs, sans critère de conformité."


def test_verdict_faux_sans_critere_reste_non_conforme():
    d = construire("epi", [], False)
    assert d.niveau == "ko" and d.cause == []  # pas de mode désigné : pas de lien


def test_resultat_ancien():
    d = decision.ancienne()
    assert d.niveau == "ancien" and d.mot == "Résultat ancien — à recalculer" and d.cause == []


def test_mode_dimensionnant_est_le_plus_charge():
    a, b = resistance("A", 100.0, 150.0), resistance("B", 140.0, 150.0)
    assert faits(construire("beam", [a, b], True))["Mode dimensionnant"].valeur == "B"


def test_etude_precisee_quand_le_nom_du_mode_se_repete():
    m1 = resistance("Pression de matage P", 10.0, 20.0, groupe="Clavette")
    m2 = resistance("Pression de matage P", 10.0, 20.0, groupe="Goupille")
    assert libelle_mode(m1, [m1, m2]) == "Pression de matage P (Clavette)"
    assert libelle_mode(m1, [m1]) == "Pression de matage P"


@pytest.mark.parametrize(
    ("cle", "mode", "groupe", "attendu"),
    [
        ("tra", "Résistance : σ max", "", ["S0"]),
        ("truss", "Résistance : σ max, barre 1 (A–B)", "", ["S"]),
        ("truss", "Flambage d'Euler : barre 2 comprimée", "", ["Imin"]),
        ("cis", "Pression de matage P", "Matage", ["Sm"]),
        ("cis", "Pression de matage P", "Clavette", ["Lk"]),
        ("cis", "Cisaillement τ", "Goupille", ["dp"]),
        ("cis", "Jourawski : τ max dans la section", "Cisaillement simple et Jourawski", ["g:Section pour Jourawski"]),
        ("cis", "Cisaillement : τ max", "Cisaillement simple et Jourawski", ["S"]),
        ("pal", "Pression P", "", ["L"]),
        ("pal", "Collerette : Pression P sous la courbe P-V", "", ["Dfl"]),  # « Collerette » avant « Pression »
        ("pal", "Vitesse de glissement V", "", ["materiau"]),
        ("fre", "Adhérence : couple transmissible au serrage mini", "", ["L"]),
        ("fre", "Arbre : σ équivalente au serrage maxi", "", ["g:Tolérances et montage"]),
        ("mot", "Couple maxi", "", ["Cmax"]),
        ("beam", "Flexion composée : Kt·σ max", "", ["g:Section"]),
        ("beam.ec3", "Déversement : MEd / Mb,Rd", "", ["Lcr"]),
    ],
)
def test_causes_du_site(cle, mode, groupe, attendu):
    assert causes(cle, {"mode": mode, "groupe": groupe}) == attendu


def test_pas_de_cause_pour_un_calcul_ou_un_critere_inconnu():
    assert causes("aju", {"mode": "x", "groupe": ""}) == []
    assert causes("mot", {"mode": "Autre", "groupe": ""}) == []


def test_avertissement_angle_de_pression():
    assert "α ≠ 20°" in avertissement("eng", {"alpha": 25.0})
    assert avertissement("eng", {"alpha": 20.0}) is None
    assert avertissement("eng", {}) is None
    assert avertissement("fre", {"alpha": 25.0}) is None


def test_avertissement_porte_a_faux_de_la_poutre():
    sup = [{"pos": 0.0}, {"pos": 4.0}]
    assert "porte-à-faux" in avertissement("beam", {"L": 6.0, "sup": sup})
    assert "au-delà de la longueur L" in avertissement("beam", {"L": 3.0, "sup": sup})
    assert avertissement("beam", {"L": 4.0, "sup": sup}) is None
    assert avertissement("beam", {"L": 6.0, "sup": [{"pos": 0.0}]}) is None  # un seul appui : console
    assert avertissement("beam", {"L": 6.0, "sup": "?"}) is None
    assert construire("beam", [resistance()], True, {"L": 6.0, "sup": sup}).avertissement


def test_cle_champ_du_bureau():
    assert cle_champ("tra", "S0") == ("Tra", "S0")
    assert cle_champ("truss", "S") == ("Tr", "S")
    assert cle_champ("eng", "m") == "eng.m"


def test_les_causes_designent_des_champs_ou_groupes_du_site():
    """Chaque cible de CAUSES existe dans le formulaire du site (un champ renommé casserait le lien)."""
    from mecastruct.pont import noyau

    for module in ("machines", "outils", "structures"):
        noyau.charger(module)
    formulaires = noyau.tous_formulaires()
    for cle, entrees in CAUSES.items():
        form = formulaires[cle.split(".")[0]]
        ids = {c["id"] for g in form["groupes"] for c in g["champs"]}
        titres = {g["titre"] for g in form["groupes"]}
        for _motif, cibles in entrees:
            for cible in cibles:
                assert (cible[2:] in titres) if cible.startswith("g:") else (cible in ids), (cle, cible)

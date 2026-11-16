"""Tests des pages Treillis et Sollicitations : exécution, exemples calculés, efforts de la poutre."""

import pytest

from mecastruct.bureau import state

ONGLETS = {"Tra": 0, "Cis": 1, "Tor": 2, "Fle": 3}


def _sollicitations(bureau, tab):
    bureau.ouvre("sollicitations")
    bureau.page.onglets.setCurrentIndex(ONGLETS[tab])
    bureau.attend()


@pytest.mark.parametrize("nom", ["treillis", "sollicitations"])
def test_la_page_s_ouvre(bureau, nom):
    bureau.ouvre(nom)
    assert bureau.page.bati


def test_treillis_exemple_se_calcule(bureau):
    bureau.ouvre("treillis")
    bureau.clique("Calculer")
    res = state.result("Tr")
    assert res["result"]["tsol"]["isostatic"] and set(res["tables"]) == {"Barres", "Réactions", "Déplacements", "Vérification des barres"}


def test_treillis_barre_inconnue_donne_un_message(bureau):
    bureau.ouvre("treillis")
    state.saisie("Tr")["bars"][0]["j"] = 99
    bureau.page.rafraichirTout()
    bureau.clique("Calculer")
    assert state.result("Tr") is None  # message d'erreur dans la page, pas d'exception non gérée


@pytest.mark.parametrize(
    ("onglet", "volet", "bouton", "resultat"),
    [
        ("Tra", None, "Calculer", "Tra"),
        ("Cis", None, "Calculer", "Cis"),
        ("Cis", "Clavette parallèle", "Calculer la clavette", "CisKey"),
        ("Cis", "Goupille / rivet", "Calculer la goupille", "CisPin"),
        ("Tor", None, "Calculer", "Tor"),
        ("Fle", None, "Calculer", "Fle"),
    ],
)
def test_sollicitations_chaque_exemple_se_calcule(bureau, onglet, volet, bouton, resultat):
    _sollicitations(bureau, onglet)
    if volet:
        bureau.ouvre_volet(volet)
    bureau.clique(bouton)
    assert state.result(resultat) is not None


def test_goupille_sous_couple_largeur_nulle_donne_un_message(bureau):
    """a = 0 : τadm ne se calcule pas ; l'erreur est affichée, la page ne plante pas."""
    _sollicitations(bureau, "Cis")
    bureau.ouvre_volet("Clavette parallèle")
    bureau.saisit("Largeur a (mm)", "0")
    bureau.ouvre_volet("Goupille / rivet")
    bureau.clique("Vérifier la goupille sous couple")
    assert state.result("CisPinT") is None


def test_clavette_normalisee_longueur_nulle_dimensionne(bureau):
    _sollicitations(bureau, "Cis")
    bureau.ouvre_volet("Clavette parallèle")
    bureau.saisit("Longueur L (0 = dimensionner) (mm)", "0")
    bureau.clique("Vérifier la clavette normalisée")
    r = state.result("CisKeyStd")
    assert r["result"]["dimensionne"] and r["ok"] and "longueur minimale" in r["status"]


def test_traction_section_variable_et_expression_interdite(bureau):
    _sollicitations(bureau, "Tra")
    bureau.choisit("Exemple", "variable")
    bureau.clique("Charger l'exemple")
    bureau.clique("Calculer")
    assert state.result("Tra") is not None
    bureau.ouvre_volet("Section variable")
    bureau.saisit("S(x) (mm², x en m)", "__import__('os').getcwd()")
    bureau.clique("Calculer")
    assert state.result("Tra") is None  # refusée par la liste blanche, jamais exécutée


def test_flexion_efforts_de_la_poutre(bureau):
    """« Reprendre les efforts de la poutre » : efforts en s puis au point critique, abscisse hors poutre refusée."""
    from mecastruct.core.pp import ppEval

    _sollicitations(bureau, "Fle")
    bureau.saisit("s sur la poutre (m)", "2")
    bureau.clique("Efforts en s")
    sol = state.result("Beam")["sol"]
    assert state.saisie("Fle")["Mfz"] == pytest.approx(ppEval(sol["Mfz"], 2.0) / 1e3)
    bureau.clique("Efforts au point critique")
    chk = state.result("Beam")["check"]
    assert state.saisie("Fle")["s0"] == pytest.approx(chk["s"])
    assert state.saisie("Fle")["Mfz"] == pytest.approx(chk["Mfz"] / 1e3)
    bureau.saisit("s sur la poutre (m)", "99")
    bureau.clique("Efforts en s")
    assert state.v.get("Fle_msg") is None  # message affiché : abscisse hors de la poutre


def _volets(bureau):
    return bureau.ordre_vertical(bureau.page.pages[1].sections[1])


def test_cisaillement_clavette_et_goupille_sous_les_fonctions_avancees(bureau):
    """Clavette et Goupille sous « Fonctions avancées » ; le choix « Haut » remonte la clavette."""
    _sollicitations(bureau, "Cis")
    ordre = _volets(bureau)
    i = ordre.index("Fonctions avancées")
    assert ordre.index("Cisaillement simple, Jourawski et matage") < i
    assert ordre.index("Clavette parallèle") > i and ordre.index("Goupille / rivet") > i
    state.v["mise_en_page.Cis.clavette"] = "Haut"
    bureau.page.pages[1].rafraichirSaisie()
    ordre = _volets(bureau)
    assert ordre.index("Clavette parallèle") < ordre.index("Fonctions avancées")


@pytest.mark.parametrize("nom", ["treillis", "sections", "tenseurs", "flambage", "hooke_jauges", "sollicitations"])
def test_valeurs_cles_sous_calculer(bureau, nom):
    """Chaque page de calcul affiche ses valeurs clés après « Calculer », pas avant."""
    bureau.ouvre(nom)
    avant = [w for w in bureau._visibles(__import__("PySide6.QtWidgets", fromlist=["QFrame"]).QFrame) if w.objectName() == "metrique"]
    assert not avant
    bureau.clique("Calculer")
    apres = [w for w in bureau._visibles(__import__("PySide6.QtWidgets", fromlist=["QFrame"]).QFrame) if w.objectName() == "metrique"]
    assert len(apres) >= 1


def test_dessin_du_treillis_suit_la_saisie_apres_un_calcul(bureau):
    bureau.ouvre("treillis")
    bureau.clique("Calculer")
    assert not bureau.a_texte("Le dessin suit la saisie")
    bureau.saisit("E (GPa)", "150")
    assert bureau.a_texte("Le dessin suit la saisie")


def test_ajouter_puis_supprimer_une_ligne_de_tableau(bureau):
    """Boutons « Ajouter une ligne » et « Supprimer la sélection » d'un tableau de saisie."""
    bureau.ouvre("treillis")
    n = len(state.saisie("Tr")["nodes"])
    bureau.clique("Ajouter une ligne")
    assert len(state.saisie("Tr")["nodes"]) == n + 1
    t = bureau.tableaux()[0]
    t.selectRow(n)
    bureau.clique("Supprimer la sélection")
    assert len(state.saisie("Tr")["nodes"]) == n


def test_valeur_saisie_dans_une_case_du_tableau(bureau):
    bureau.ouvre("treillis")
    t = bureau.tableaux()[0]
    bureau.cellule(t, 1, "x (m)", "7,5")
    assert state.saisie("Tr")["nodes"][1]["x"] == 7.5
    bureau.cellule(t, 1, "x (m)", "pas un nombre")  # illisible : l'ancienne valeur revient
    assert state.saisie("Tr")["nodes"][1]["x"] == 7.5

"""Tests de la page « Poutres », mode « Ossature 3D » : ouverture, calcul d'un exemple, mécanisme."""

from mecastruct.bureau import state


def _mode_3d(bureau, exemple):
    """Passe en mode Ossature 3D et choisit l'exemple."""
    bureau.ouvre("poutres")
    bureau.radio("Ossature 3D")
    bureau.choisit("Exemple", exemple)
    return state.extra["P3D"]


def _metriques(bureau):
    from PySide6.QtWidgets import QFrame

    return [w for w in bureau._visibles(QFrame) if w.objectName() == "metrique"]


def test_mode_2d_par_defaut(bureau):
    bureau.ouvre("poutres")
    assert state.v.get("poutres.mode", "Poutre 2D") == "Poutre 2D"
    assert bureau.champ("Longueur L (m)")


def test_potence_en_L_calcul(bureau):
    _mode_3d(bureau, "Potence en L")
    bureau.clique("Calculer")
    assert len(_metriques(bureau)) >= 1
    assert state.v["p3d.res"]["res"]["equilibre"]["ok"]


def test_hangar_contrevente(bureau):
    """Cas d'école complexe : il se calcule, s'équilibre, et la page montre exemple expliqué et matériaux."""
    _mode_3d(bureau, "Hangar contreventé")
    assert bureau.a_texte("Saint-André")
    assert bureau.a_texte("Matériaux utilisés (1)")
    bureau.clique("Calculer")
    res = state.v["p3d.res"]["res"]
    assert res["equilibre"]["ok"] and len(res["deplacements"]) == 15
    bureau.case("Agrandir la visualisation", True)  # zone de droite élargie


def test_saisie_modifiee_apres_calcul_signalee(bureau):
    _mode_3d(bureau, "Potence en L")
    bureau.clique("Calculer")
    assert not bureau.a_texte("Saisie modifiée")
    bureau.case("Poids propre", not state.extra["P3D"]["pp"])
    assert bureau.a_texte("Saisie modifiée")


def test_mecanisme_affiche_une_erreur(bureau):
    P3D = _mode_3d(bureau, "Potence en L")
    for n in P3D["noeuds"]:
        n["appui"] = "libre"  # plus aucun appui : mécanisme
    bureau.page.rafraichirTout()
    bureau.clique("Calculer")
    assert "p3d.res" not in state.v
    assert bureau.a_texte("mécanisme")


def test_resultats_3d_onglets_et_export_csv(bureau, tmp_path):
    _mode_3d(bureau, "Potence en L")
    bureau.clique("Calculer")
    for onglet in ("Déplacements", "Réactions", "Efforts internes", "Contraintes", "Vérification à la main", "Équations"):
        bureau.onglet(onglet)
    bureau.clavier_enregistrer(tmp_path / "ossature_3d.csv")
    bureau.clique("Exporter les résultats (CSV)")
    texte = (tmp_path / "ossature_3d.csv").read_text(encoding="utf-8-sig")
    assert "# Déplacements" in texte and "# Réactions" in texte and "# Contraintes" in texte

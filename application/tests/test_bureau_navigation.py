"""Navigation du bureau comme sur le site : recherche globale, Mes études, cartes de l'accueil, dernière page, Partager."""

import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import main
from mecastruct.bureau import etudes, recherche, state
from mecastruct.bureau.pages import accueil
from mecastruct.services.pages_texte import INTROS

LIBELLES = {i: lib for i, lib, _ in main.MENU if lib is not None}


def _index() -> recherche.Index:
    famille, courante = {}, None
    for ident, libelle, _ in main.MENU:
        if libelle is None:
            courante = ident
        else:
            famille[ident] = courante
    return recherche.Index(LIBELLES, famille, INTROS)


# ----------------------------------------------------------------------------------------------- recherche (sans fenêtre)


@pytest.mark.parametrize(
    ("saisie", "page", "onglet"),
    [
        ("Goodman", "poutres", "Poutre 2D"),
        ("wöhler", "poutres", "Poutre 2D"),
        ("Rankine", "tenseurs", None),
        ("H7", "ajustements", None),
        ("roulements", "roulements", 0),
        ("règles de montage", "roulements", 2),
        ("ossature", "poutres", "Ossature 3D"),
        ("von mises", "tenseurs", None),
        ("pignon", "engrenages", 0),
        ("épicycloïdal", "epicycloidaux", None),
        ("embrayage", "freins_embrayages", 1),
        ("peterson", "base_de_donnees", "Abaques Kt"),
        ("iso 286", "ajustements", None),
        ("jauge", "hooke_jauges", 1),
        ("torsion", "sollicitations", 2),
        ("convertir", "convertisseur", None),
    ],
)
def test_la_recherche_trouve_la_bonne_page(saisie, page, onglet):
    res, _ = _index().resultats(saisie)
    assert res, saisie
    assert (res[0]["page"], res[0]["onglet"]) == (page, onglet), [(r["page"], r["onglet"]) for r in res]


@pytest.mark.parametrize(("saisie", "message", "premiere"), [
    ("ressort", "ressort", "hooke_jauges"),
    ("soudure", "soudure", "poutres"),
])  # fmt: skip
def test_un_calcul_absent_est_dit_avec_les_pages_proches(saisie, message, premiere):
    res, manque = _index().resultats(saisie)
    assert manque and message in manque["message"]
    assert res[0]["page"] == premiere


def test_une_recherche_sans_resultat_ou_vide():
    index = _index()
    assert index.resultats("xyzxyz")[0] == []
    assert index.resultats("   ")[0] == []
    assert len(index.resultats("contrainte")[0]) <= 8


def test_chaque_page_du_menu_est_cherchable_par_son_titre():
    index = _index()
    for ident, libelle in LIBELLES.items():
        if ident == "accueil":
            continue
        pages = [r["page"] for r in index.resultats(libelle)[0]]
        assert ident in pages, (libelle, pages)


# --------------------------------------------------------------------------------------------- recherche (dans la fenêtre)


def test_ctrl_k_cherche_goodman_et_ouvre_la_bonne_page(bureau):
    f = bureau.fenetre
    bureau.ouvre("accueil")
    f.activateWindow()
    bureau.qtbot.waitUntil(f.isActiveWindow, timeout=5000)
    QTest.keyClick(f, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    bureau.qtbot.waitUntil(lambda: f.recherche_ouverte is not None and f.recherche_ouverte.isVisible(), timeout=5000)
    boite = f.recherche_ouverte
    boite.champ.setText("Goodman")
    assert boite.resultats and boite.resultats[0]["page"] == "poutres"
    assert boite.liste.count() == len(boite.resultats) and boite.liste.currentRow() == 0
    QTest.keyClick(boite.champ, Qt.Key.Key_Return)
    bureau.attend()
    assert not boite.isVisible()
    assert f.pile.currentWidget() is f.page("poutres")
    assert state.v.get("poutres.mode") == "Poutre 2D"


def test_la_recherche_se_pilote_aux_fleches_et_se_ferme_avec_echap(bureau):
    f = bureau.fenetre
    f.rechercher()
    boite = f.recherche_ouverte
    boite.champ.setText("roulement")
    assert len(boite.resultats) >= 2
    QTest.keyClick(boite, Qt.Key.Key_Down)
    assert boite.liste.currentRow() == 1
    QTest.keyClick(boite, Qt.Key.Key_Up)
    assert boite.liste.currentRow() == 0
    QTest.keyClick(boite, Qt.Key.Key_Escape)
    assert not boite.isVisible()


def test_la_recherche_ouvre_l_onglet_du_calcul_cherche(bureau):
    f = bureau.fenetre
    f.rechercher()
    f.recherche_ouverte.champ.setText("règles de montage")
    f.recherche_ouverte.choisir(0)
    bureau.attend()
    page = f.page("roulements")
    assert f.pile.currentWidget() is page and page.onglets.currentIndex() == 2
    f.rechercher()
    f.recherche_ouverte.champ.setText("embrayage")
    f.recherche_ouverte.choisir(0)
    bureau.attend()
    assert f.page("freins_embrayages").onglets.currentIndex() == 1
    f.rechercher()
    f.recherche_ouverte.champ.setText("peterson")
    f.recherche_ouverte.choisir(0)
    bureau.attend()
    assert state.v["onglet.base_de_donnees"] == "Abaques Kt"


def test_la_barre_oblique_ouvre_la_recherche_sauf_dans_un_champ(bureau):
    f = bureau.fenetre
    f.activateWindow()
    bureau.qtbot.waitUntil(f.isActiveWindow, timeout=5000)
    bureau.ouvre("convertisseur")
    champ = next(c for c in bureau._visibles(__import__("PySide6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit))
    champ.setFocus()
    f._barre_oblique()
    assert f.recherche_ouverte is None  # on tape dans un champ : rien ne s'ouvre
    champ.clearFocus()
    f.setFocus()
    f._barre_oblique()
    assert f.recherche_ouverte is not None and f.recherche_ouverte.isVisible()


# ------------------------------------------------------------------------------------------------------- Mes études


def test_favori_recents_et_derniere_page(bureau):
    f = bureau.fenetre
    bureau.ouvre("roulements")
    assert f.bouton_favori.isEnabled() and not f.bouton_favori.isChecked()
    f.bouton_favori.click()
    assert f.bouton_favori.isChecked() and etudes.est_favori("roulements")
    bureau.ouvre("ajustements")
    assert not f.bouton_favori.isChecked()
    bureau.ouvre("accueil")
    assert not f.bouton_favori.isEnabled()
    assert [r["id"] for r in etudes.recents()] == ["ajustements", "roulements"]
    # le fichier existe et reprend les identifiants du site
    brut = json.loads(etudes.chemin().read_text(encoding="utf-8"))
    assert brut["format"] == "mecastruct-etudes" and brut["favoris"][0]["id"] == "roulements"
    # la famille « Liaisons et guidages » rouvre la dernière page visitée
    bureau.ouvre("accueil")
    f.boutons_familles["Liaisons et guidages"].click()
    bureau.attend()
    assert f.pile.currentWidget() is f.page("ajustements")
    bureau.ouvre("paliers_lisses")
    bureau.ouvre("accueil")
    f.boutons_familles["Liaisons et guidages"].click()
    bureau.attend()
    assert f.pile.currentWidget() is f.page("paliers_lisses")


def test_les_etudes_survivent_a_la_fermeture():
    etudes.suspendre(False)
    etudes.definir_pages({"roulements": "Liaisons et guidages"})
    etudes.basculer_favori("roulements")
    etudes.noter_visite("roulements")
    etudes._cache.update(chemin="?", donnees=None)  # comme après un redémarrage : tout est relu dans le fichier
    assert etudes.est_favori("roulements") and etudes.recents()[0]["id"] == "roulements"


def test_dupliquer_puis_rouvrir_une_copie(bureau, monkeypatch):
    f = bureau.fenetre
    bureau.ouvre("flambage")
    avant = state.saisie("Fla")["L"]
    monkeypatch.setattr(etudes, "demander_nom", lambda parent, defaut: "Ma colonne")
    monkeypatch.setattr(etudes, "confirmer", lambda parent, texte: True)
    bureau.ouvre("accueil")
    bureau.clique("Dupliquer")  # première ligne de « Récemment utilisés »
    bureau.attend()
    [copie] = etudes.copies()
    assert copie["nom"] == "Ma colonne" and copie["page"] == "flambage" and copie["calcul"] == "fla"
    assert copie["saisie"]["L"] == avant
    # on change la saisie, on rouvre la copie : elle revient
    state.saisie("Fla")["L"] = avant + 777.0
    bureau.clique("Ouvrir")
    bureau.attend()
    assert f.pile.currentWidget() is f.page("flambage")
    assert state.saisie("Fla")["L"] == avant
    bureau.ouvre("accueil")
    bureau.clique("Supprimer")
    bureau.attend()
    assert etudes.copies() == []


def test_copie_d_une_page_a_onglets_garde_l_onglet_actif(bureau, monkeypatch):
    f = bureau.fenetre
    page = bureau.ouvre("sollicitations")
    page.onglets.setCurrentIndex(2)  # Torsion
    assert etudes.calcul_actif(f, "sollicitations") == "tor"
    assert etudes.ajouter_copie("sollicitations", "tor", "Arbre")["calcul"] == "tor"
    bureau.ouvre("flambage")
    monkeypatch.setattr(etudes, "confirmer", lambda parent, texte: True)
    etudes.ouvrir_copie(etudes.copies()[0])
    assert state.saisie("Tor") == etudes.copies()[0]["saisie"]


def test_copie_d_une_page_de_machine(bureau):
    bureau.ouvre("ajustements")
    avant = etudes.lire_saisie("aju")
    c = etudes.ajouter_copie("ajustements", "aju", "H7/g6")
    cle = next(k for k, v in avant.items() if isinstance(v, str))
    state.v[f"aju.{cle}"] = "zzz"
    etudes.ouvrir_copie(c)
    assert etudes.lire_saisie("aju") == avant


def test_export_puis_import_des_etudes(bureau, tmp_path):
    bureau.ouvre("roulements")
    etudes.basculer_favori("roulements")
    etudes.ajouter_copie("flambage", "fla", "Colonne A")
    donnees = etudes.exporter()
    assert donnees["format"] == "mecastruct-etudes" and donnees["version"] == 1
    assert donnees["favoris"][0]["id"] == "roulements" and donnees["copies"][0]["page"] == "flambage"
    assert {"beam", "fla", "aju", "rlt"} <= set(donnees["saisies"])
    texte = json.dumps(donnees)
    # un autre bureau (études vides) lit le fichier
    etudes._donnees().clear()
    assert etudes.favoris() == [] and etudes.copies() == []
    v = etudes.lire_import(texte)
    assert v["ok"] and len(v["donnees"]["favoris"]) == 1 and len(v["donnees"]["copies"]) == 1
    assert etudes.appliquer_import(v["donnees"]) == 0
    assert etudes.est_favori("roulements") and etudes.copies()[0]["nom"] == "Colonne A"
    # deux fois le même fichier : pas de doublon
    etudes.appliquer_import(v["donnees"])
    assert len(etudes.copies()) == 1 and len(etudes.favoris()) == 1


def test_import_d_un_export_du_site_et_fichiers_refuses():
    etudes.definir_pages({"sections": "Structures", "paliers": "Liaisons et guidages", "moteur": "Transmission"})
    site = {"format": "mecastruct-etudes", "version": 1, "outil": "MecaStruct RdM 1.7.0", "exporte": "2026-01-01T00:00:00Z",
            "favoris": [{"id": "sections-page", "t": 1700000000000}, {"id": "inconnue", "t": 1}, {"id": "accueil", "t": 2}],
            "recents": [{"id": "moteur", "t": 1700000000001}],
            "copies": [{"id": "c1", "nom": "Test", "page": "paliers", "calcul": "pal", "cree": "2026-01-01T00:00:00Z", "saisie": {"x": 1}},
                       {"id": "c2", "nom": "Mauvaise", "page": "paliers", "calcul": "inconnu", "cree": "", "saisie": {}}],
            "saisies": {"pal": {"x": 1}, "ossature": {"y": 2}}}  # fmt: skip
    v = etudes.lire_import(json.dumps(site))
    assert v["ok"]
    d = v["donnees"]
    assert [f["id"] for f in d["favoris"]] == ["sections-page"] and len(d["copies"]) == 1
    assert [k for k, _ in d["saisies"]] == ["pal"]  # « ossature » : calcul que le bureau n'a pas
    etudes.appliquer_import(d)
    assert [f["id"] for f in etudes.favoris()] == ["sections"] and etudes.recents()[0]["id"] == "dimensionnement_moteur"
    assert etudes.copies()[0]["page"] == "paliers_lisses"
    # fichiers refusés avec un message, sans rien changer
    assert "JSON" in etudes.lire_import("pas du json")["erreur"]
    assert "export d'études" in etudes.lire_import("{}")["erreur"]
    assert "autre version" in etudes.lire_import(json.dumps({"format": "mecastruct-etudes", "version": 9}))["erreur"]
    assert "aucune étude" in etudes.lire_import(json.dumps({"format": "mecastruct-etudes", "version": 1}))["erreur"]


def test_une_saisie_de_forme_inattendue_est_laissee_de_cote(bureau):
    texte = json.dumps({"format": "mecastruct-etudes", "version": 1, "saisies": {"beam": {"L": "pas un nombre"}}})
    v = etudes.lire_import(texte)
    assert v["ok"]
    avant = json.dumps(state.saisie("Beam"), default=str, sort_keys=True)
    assert etudes.appliquer_import(v["donnees"]) == 1
    assert json.dumps(state.saisie("Beam"), default=str, sort_keys=True) == avant


def test_mes_etudes_sur_l_accueil(bureau):
    etudes.basculer_favori("treillis")
    bureau.ouvre("flambage")
    bureau.ouvre("accueil")
    assert bureau.a_texte("Favoris") and bureau.a_texte("Récemment utilisés")
    assert bureau.boutons("Exporter mes études (JSON)") and bureau.boutons("Importer un fichier d'études")
    bureau.clique("Vider l'historique")
    assert etudes.recents() == [] and etudes.est_favori("treillis")
    # lignes cliquables : « Treillis » ouvre la page
    bureau.clique("Treillis", 0)
    bureau.attend()
    assert bureau.fenetre.pile.currentWidget() is bureau.fenetre.page("treillis")


# --------------------------------------------------------------------------------------------- cartes de l'accueil


def test_les_cartes_sont_repliees_et_s_ouvrent_au_survol(bureau, monkeypatch):
    monkeypatch.setenv("MECASTRUCT_SANS_ANIMATION", "1")
    page = bureau.ouvre("accueil")
    cartes = page.cartes
    assert [c.titre for c in cartes] == list(bureau.fenetre.familles)
    assert not any(c.ouverte() for c in cartes) and not any(c.corps.isVisibleTo(page) for c in cartes)
    c = cartes[0]
    c.survol_entre()
    assert c.ouverte() and c.corps.isVisibleTo(page) and c._par_survol and not c._epingle
    c.survol_sort()
    bureau.qtbot.waitUntil(lambda: not c.ouverte(), timeout=2000)  # se referme 250 ms après le départ du pointeur
    assert not c.corps.isVisibleTo(page)


def test_un_clic_garde_la_carte_ouverte_et_echap_la_ferme(bureau, monkeypatch):
    monkeypatch.setenv("MECASTRUCT_SANS_ANIMATION", "1")
    c = bureau.ouvre("accueil").cartes[1]
    c.survol_entre()
    c.clic()  # ouverte par le survol : le clic la garde
    assert c.ouverte() and c._epingle
    c.survol_sort()
    bureau.qtbot.wait(450)
    assert c.ouverte()  # gardée : le départ du pointeur ne la ferme pas
    c.clic()  # un second clic referme
    assert not c.ouverte()
    c.clic()
    assert c.ouverte()
    QTest.keyClick(c.entete, Qt.Key.Key_Escape)
    assert not c.ouverte()


def test_survol_reel_de_la_souris(bureau, monkeypatch):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent

    monkeypatch.setenv("MECASTRUCT_SANS_ANIMATION", "1")
    c = bureau.ouvre("accueil").cartes[2]
    p = QPointF(5, 5)
    QApplication.sendEvent(c, QEnterEvent(p, p, p))
    assert c.ouverte()
    QApplication.sendEvent(c, QEvent(QEvent.Type.Leave))
    bureau.qtbot.waitUntil(lambda: not c.ouverte(), timeout=2000)


def test_les_cartes_s_animent_sauf_si_le_mouvement_est_reduit(bureau, monkeypatch):
    monkeypatch.delenv("MECASTRUCT_SANS_ANIMATION", raising=False)
    monkeypatch.setattr(accueil, "mouvement_reduit", lambda: False)
    page = bureau.ouvre("accueil")
    c = page.cartes[0]
    c.clic()
    assert c.ouverte() and c._anim.state() != c._anim.State.Stopped  # animation en cours
    bureau.qtbot.waitUntil(lambda: c.corps.maximumHeight() == accueil.QWIDGETSIZE_MAX, timeout=3000)
    assert c.corps.height() > 20
    c.clic()
    bureau.qtbot.waitUntil(lambda: not c.corps.isVisible(), timeout=3000)
    # mouvement réduit : l'état final est immédiat, sans animation
    monkeypatch.setattr(accueil, "mouvement_reduit", lambda: True)
    c.clic()
    assert c._anim.state() == c._anim.State.Stopped and c.corps.isVisible()


def test_mouvement_reduit_par_variable(monkeypatch):
    monkeypatch.setenv("MECASTRUCT_SANS_ANIMATION", "1")
    assert accueil.mouvement_reduit() is True


# --------------------------------------------------------------------------------------------------------- Partager


def test_partager_copie_les_deux_liens_et_le_dit(bureau):
    f = bureau.fenetre
    f.bouton_partager.click()
    texte = QApplication.clipboard().text()
    assert "https://theo33-oss.github.io/MecaStruct/" in texte and "https://github.com/theo33-oss/MecaStruct" in texte
    assert "copiés" in f.statusBar().currentMessage()
    assert "copiés" in f.bouton_partager.text()

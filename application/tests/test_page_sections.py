"""Tests de la page « Sections » : exécution, rectangle par défaut, exemple IPE, section composée, transferts."""

import pytest

from mecastruct.bureau import state


def _page(bureau):
    bureau.ouvre("sections")
    return state.saisie("Sec")


def test_page_s_ouvre(bureau):
    _page(bureau)
    assert bureau.a_texte("Aire, centre de gravité")


def test_rectangle_par_defaut_iz(bureau):
    _page(bureau)
    _type(bureau, "rectangle")
    bureau.clique("Calculer")
    res = state.result("Sec")["result"]
    b, h = 0.100, 0.200  # dimensions par défaut en m (100 mm × 200 mm)
    assert res["P"]["Iz"] == pytest.approx(b * h**3 / 12, rel=1e-9)


def test_exemple_ipe_puis_calcul(bureau):
    _page(bureau)
    bureau.clique("Charger l'exemple")
    bureau.clique("Calculer")
    assert state.result("Sec") is not None
    assert state.saisie("Sec")["prof"] == "IPE 200"


def _type(bureau, nom):
    state.saisie("Sec")["type"] = nom
    bureau.page.rafraichirTout()
    bureau.attend()


def test_section_composee_calcule(bureau):
    _page(bureau)
    _type(bureau, "composite")
    bureau.clique("Calculer")
    assert state.result("Sec")["result"]["sec"]["type"] == "composite"


def test_efforts_de_la_poutre_section_composee_envoyee(bureau):
    """Section composée envoyée à la poutre puis recalculée : « Efforts en s » ne plante pas (tableaux NumPy)."""
    _page(bureau)
    _type(bureau, "composite")
    bureau.clique("Calculer")
    bureau.clique("Utiliser cette section pour une poutre")
    bureau.clique("Calculer")
    bureau.clique("Efforts en s")
    assert state.v.get("Sec_msg") is None  # le message a été affiché
    assert bureau.a_texte("Efforts lus sur la poutre")


def test_profile_catalogue_transfere_sans_fausse_alerte(bureau):
    """IPE 200 envoyé à la poutre : la section est la même, pas d'alerte « section différente » (Iz tabulé)."""
    s = _page(bureau)
    s.update(type="profile", fam="IPE", prof="IPE 200")
    bureau.page.rafraichirTout()
    bureau.clique("Calculer")
    bureau.clique("Utiliser cette section pour une poutre")
    bureau.clique("Efforts en s")
    assert bureau.a_texte("Efforts lus sur la poutre")
    assert not bureau.a_texte("diffère")


def test_efforts_de_la_poutre(bureau):
    """« Efforts en s » et « Efforts au point critique » reprennent les efforts de la poutre (IPE 300, 6 m)."""
    from mecastruct.core.pp import ppEval

    _page(bureau)
    bureau.saisit("s sur la poutre (m)", "2")
    bureau.clique("Efforts en s")
    sec, sol = state.saisie("Sec"), state.result("Beam")["sol"]
    assert sec["Mfz"] == pytest.approx(ppEval(sol["Mfz"], 2.0) / 1e3)
    assert sec["Ty"] == pytest.approx(ppEval(sol["Ty"], 2.0) / 1e3)
    bureau.clique("Efforts au point critique")
    chk = state.result("Beam")["check"]
    assert state.saisie("Sec")["s0"] == pytest.approx(chk["s"])
    assert state.saisie("Sec")["Mfz"] == pytest.approx(chk["Mfz"] / 1e3)
    bureau.saisit("s sur la poutre (m)", "99")
    bureau.clique("Efforts en s")
    assert bureau.a_texte("poutre")  # abscisse hors de la poutre : message affiché, pas d'exception


def test_apercu_de_la_section_avant_le_calcul(bureau):
    _page(bureau)
    assert bureau.a_texte("Section")
    assert bureau.a_texte("Aperçu mis à jour")


def test_sections_envoie_la_section_a_flambage(bureau):
    """« Utiliser cette section » remplit aussi la saisie Flambage (S, Iz, Iy, matériau)."""
    _page(bureau)
    bureau.clique("Charger l'exemple")
    bureau.clique("Calculer")
    bureau.clique("Utiliser cette section pour une poutre")
    fla, beam = state.saisie("Fla"), state.saisie("Beam")
    assert fla["S"] == pytest.approx(beam["S"]) and fla["Iz"] == pytest.approx(beam["Iz"])
    assert fla["Iy"] == pytest.approx(beam["Iy"]) and fla["mat"] == "S235"
    assert fla["E"] == pytest.approx(210.0)


def test_corniere_envoie_les_moments_principaux(bureau):
    from mecastruct.core import geometry

    _page(bureau)
    _type(bureau, "L")
    bureau.clique("Calculer")
    bureau.clique("Utiliser cette section pour une poutre")
    P = geometry.analytical(state.result("Sec")["result"]["sec"])
    fla = state.saisie("Fla")
    assert abs(P["Iyz"]) > 0
    assert fla["Iz"] == pytest.approx(P["I1"] * 1e12) and fla["Iy"] == pytest.approx(P["I2"] * 1e12)

"""Application de bureau : bloc « Décision » en tête des résultats (verdict, mode dimensionnant, « Aller à la cause »)."""

import pytest
from PySide6.QtWidgets import QLabel, QPushButton

from mecastruct.bureau.modes import BlocDecision, ModesRuine

pytestmark = pytest.mark.qt


def blocs(bureau):
    return [w for w in bureau.page.findChildren(BlocDecision) if w.isVisibleTo(bureau.page)]


def textes(bloc):
    return [lab.text() for lab in bloc.findChildren(QLabel)]


def champ_actif(bureau):
    return bureau.fenetre.focusWidget()


def test_page_de_machine_bloc_decision_apres_calcul(bureau):
    bureau.ouvre("engrenages")
    assert not blocs(bureau)  # rien avant « Calculer »
    bureau.clique("Calculer")
    bureau.attend(200)
    (bloc,) = blocs(bureau)
    assert bloc.decision.niveau in ("ok", "ko")
    t = textes(bloc)
    assert any(x in ("✓ Conforme", "✗ Non conforme") for x in t)
    assert any("Mode dimensionnant" in x for x in t)
    assert any("Flexion en pied de dent" in x for x in t)
    # le bloc est au-dessus du diagramme des modes de ruine
    (modes,) = [w for w in bureau.page.findChildren(ModesRuine) if w.isVisibleTo(bureau.page)]
    assert bloc.mapTo(bureau.page, bloc.rect().topLeft()).y() < modes.mapTo(bureau.page, modes.rect().topLeft()).y()


def test_avertissement_angle_de_pression(bureau):
    bureau.ouvre("engrenages")
    bureau.saisit("Angle de pression α (°)", "25")
    bureau.clique("Calculer")
    bureau.attend(200)
    (bloc,) = blocs(bureau)
    assert any("α ≠ 20°" in x for x in textes(bloc))


def test_saisie_modifiee_bloc_a_recalculer(bureau):
    bureau.ouvre("engrenages")
    bureau.clique("Calculer")
    bureau.attend(200)
    bureau.saisit("Module m (mm)", "3")
    (bloc,) = blocs(bureau)
    assert bloc.decision.niveau == "ancien"
    assert any("Résultat ancien" in x for x in textes(bloc))
    assert bloc.lienCause is None


def test_aller_a_la_cause_donne_le_focus_au_champ(bureau):
    """Traction non conforme : le lien mène à la section S0 (le levier), pas à la charge N."""
    bureau.ouvre("sollicitations")
    bureau.clique("Calculer")
    bureau.attend(200)
    (bloc,) = blocs(bureau)
    assert bloc.decision.niveau == "ko" and bloc.lienCause is not None
    assert any("S0" in b.text() for b in bloc.findChildren(QPushButton) if b is not bloc.lienCause)  # paramètre le plus influent
    bloc.lienCause.click()
    bureau.attend()
    sous_page = bureau.page.pages[bureau.page.onglets.currentIndex()]
    assert champ_actif(bureau) is sous_page.champ_vivant(("Tra", "S0")) is not None


def test_aller_a_la_cause_deplie_le_bloc_ferme(bureau):
    """Le champ cherché est dans un volet encore fermé : il est ouvert et le champ reçoit le focus."""
    bureau.ouvre("sollicitations")
    bureau.page.onglets.setCurrentIndex(1)  # Cisaillement & matage
    bureau.attend()
    page = bureau.page.pages[1]
    assert page.champ_vivant(("Cis", "Lk")) is None  # volet « Clavette parallèle » fermé : champ pas encore bâti
    assert page.peut_aller([("champ", ("Cis", "Lk"))])
    assert page.aller_au_champ([("champ", ("Cis", "Lk"))])
    assert page.champ_vivant(("Cis", "Lk")) is not None
    assert champ_actif(bureau) is page.champ_vivant(("Cis", "Lk"))
    assert not page.aller_au_champ([("champ", ("Cis", "inconnu"))])


def test_aller_a_un_groupe_ouvre_son_volet(bureau):
    bureau.ouvre("frettage")
    page = bureau.page
    assert page.aller_au_champ([("groupe", ("Tolérances et montage",))])
    assert not page.aller_au_champ([("groupe", ("Groupe qui n'existe pas",))])


def test_verdict_information_sans_critere(bureau):
    bureau.ouvre("ajustements")
    bureau.clique("Calculer")
    bureau.attend(200)
    (bloc,) = blocs(bureau)
    assert bloc.decision.niveau == "info"
    assert any("ℹ Information" in x for x in textes(bloc))
    assert bloc.lienCause is None


@pytest.mark.parametrize("page", ["poutres", "treillis", "flambage", "tenseurs"])
def test_pages_de_structures_ont_le_bloc(bureau, page):
    bureau.ouvre(page)
    bureau.clique("Calculer")
    bureau.attend(300)
    (bloc,) = blocs(bureau)
    assert bloc.decision.niveau in ("ok", "ko", "neutre")
    assert any("Mode dimensionnant" in x for x in textes(bloc))

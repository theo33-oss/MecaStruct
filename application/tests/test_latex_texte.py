"""Formules LaTeX converties en texte Unicode copiable (plus d'images d'équations)."""

import pytest

from mecastruct.bureau.latex_texte import versTexte


@pytest.mark.parametrize(
    ("tex", "attendu"),
    [
        (r"P=\frac{F}{S_{mat}}", "P=F/Sₘₐₜ"),
        (r"L=\sqrt{(x_j-x_i)^2+(y_j-y_i)^2}", "L=√((xⱼ−xᵢ)²+(yⱼ−yᵢ)²)"),
        (r"\sigma = \frac{54\, F_t}{\pi^2\, k\, m^2} = 81.64\ \mathrm{MPa}", "σ = (54  Fₜ)/(π²  k  m²) = 81.64 MPa"),
        (r"\vec{F}_i", "F⃗ᵢ"),
        (r"$h=m+r-dn$", "h=m+r−dn"),
    ],
)
def test_conversion(tex, attendu):
    assert versTexte(tex) == attendu


def test_commande_inconnue_reste_lisible():
    assert versTexte(r"\foo + 1") == "foo + 1"


def test_formule_affichee_en_texte_selectionnable(bureau):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    bureau.ouvre("treillis")
    bureau.clique("Calculer")
    formules = [w for w in bureau._visibles(QLabel) if w.objectName() == "formule"]
    assert formules
    assert all(w.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse for w in formules)
    assert all(w.pixmap() is None or w.pixmap().isNull() for w in formules)

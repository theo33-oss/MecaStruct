"""Fixture commune des tests de l'interface de bureau : une fenêtre neuve par test (état global remis à zéro)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_configure(config):
    config.addinivalue_line("markers", "qt: test qui ouvre une fenêtre Qt (exclu du jeu rapide : -m 'not qt')")


def pytest_collection_modifyitems(items):
    """Marque « qt » les tests qui demandent une fenêtre : le jeu rapide (-m 'not qt') ne garde que le calcul."""
    for item in items:
        if {"bureau", "qtbot", "qapp"} & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.qt)


@pytest.fixture
def bureau(qapp, qtbot):
    from tests.bureau_outils import Bureau

    b = Bureau(qapp, qtbot)
    yield b
    b.fenetre.close()
    b.fenetre.deleteLater()

"""Fixture commune des tests de l'interface de bureau : une fenêtre neuve par test (état global remis à zéro)."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_configure(config):
    config.addinivalue_line("markers", "qt: test qui ouvre une fenêtre Qt (exclu du jeu rapide : -m 'not qt')")


def pytest_sessionfinish(session, exitstatus):
    session.config._statut_sortie = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    """Sortie directe après les Qt WebEngine : leur démontage plante (Segmentation fault) sous Linux hors écran, après que
    les tests ont tous passé, et fait échouer la CI. Les résultats sont déjà imprimés ; le code de sortie est celui de pytest."""
    statut = getattr(config, "_statut_sortie", None)
    if statut is not None and "PySide6.QtWebEngineWidgets" in sys.modules and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(statut)


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

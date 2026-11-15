"""Fabrique A_PARTAGER_MecaStruct.zip : le .bat, le LISEZ-MOI et application/ sans .venv, caches, tests ni outils."""

import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent
EXCLUS = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "tests", "tools", "captures"}
SORTIE = RACINE / "A_PARTAGER_MecaStruct.zip"


def fichiers():
    yield RACINE / "1_Ouvrir_application.bat"
    yield RACINE / "LISEZ-MOI.txt"
    for f in sorted((RACINE / "application").rglob("*")):
        rel = f.relative_to(RACINE / "application")
        if f.is_file() and not (set(rel.parts) & EXCLUS) and f.name != "AVANCEMENT.md" and f.suffix != ".pyc":
            yield f


with zipfile.ZipFile(SORTIE, "w", zipfile.ZIP_DEFLATED) as z:
    for f in fichiers():
        z.write(f, f.relative_to(RACINE).as_posix())
print(SORTIE, SORTIE.stat().st_size // 1024, "Ko")

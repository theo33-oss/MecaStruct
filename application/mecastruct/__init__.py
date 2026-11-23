"""Paquet MecaStruct RdM : calcul (core, services, plots), pont web (pont) et interface de bureau (bureau)."""

__version__ = "1.7.0"  # seule source du numéro de version : bureau, installateur et site le relisent

# Nom écrit dans les fichiers d'étude (clé « app »). Les fichiers enregistrés sous l'ancien nom « RdM Pro » s'ouvrent toujours.
APP_NOM = "MecaStruct RdM"
APPS_ACCEPTES = (APP_NOM, "MecaStruct RdM Pro")

# Version du format des fichiers JSON (projet, problème, étude de machine, export « Mes études »). Elle s'écrit dans la clé
# « schema_version » à côté de « version » (inchangée, lue par les anciennes versions). Un fichier sans la clé est de version 1 ;
# une clé inconnue est ignorée ; un fichier d'une version plus récente que celle-ci est refusé avec un message clair.
SCHEMA_VERSION = 1


def en_tete_fichier() -> dict:
    """Clés ajoutées à tout fichier JSON écrit : format du schéma et version de l'outil qui l'a écrit."""
    return {"schema_version": SCHEMA_VERSION, "outil": f"{APP_NOM} {__version__}"}


def schema_refuse(d: dict) -> str | None:
    """Phrase d'erreur si le fichier décodé `d` vient d'un format plus récent ou illisible, sinon None (clé absente : version 1)."""
    v = d.get("schema_version", SCHEMA_VERSION)
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        return "Ce fichier a un numéro de format illisible : il ne s'ouvre pas ici."
    if v > SCHEMA_VERSION:
        outil = d.get("outil")
        par = f" (écrit par {outil[:60]})" if isinstance(outil, str) and outil.strip() else ""
        return (f"Ce fichier vient d'une version plus récente de MecaStruct{par} : format {v}, alors que cette version lit "
                f"jusqu'au format {SCHEMA_VERSION}. Mettez l'application à jour pour l'ouvrir.")
    return None

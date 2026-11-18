"""Paquet MecaStruct RdM : calcul (core, services, plots), pont web (pont) et interface de bureau (bureau)."""

__version__ = "1.7.0"  # seule source du numéro de version : bureau, installateur et site le relisent

# Nom écrit dans les fichiers d'étude (clé « app »). Les fichiers enregistrés sous l'ancien nom « RdM Pro » s'ouvrent toujours.
APP_NOM = "MecaStruct RdM"
APPS_ACCEPTES = (APP_NOM, "MecaStruct RdM Pro")

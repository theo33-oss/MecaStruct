"""Pont entre l'interface web (JavaScript) et le calcul Python : entrées et sorties en JSON.

Le navigateur l'appelle par Pyodide ; la fenêtre de bureau pourra l'appeler en Python natif. Rien n'est calculé en
JavaScript : la page affiche ce que ce module renvoie. Aucune dépendance à une interface.
"""

from mecastruct.pont.noyau import appeler, catalogue, versJson

__all__ = ["appeler", "catalogue", "versJson"]

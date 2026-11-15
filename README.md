# MecaStruct RdM Pro

Résistance des matériaux et éléments de machines : poutres, treillis, sections, sollicitations, flambage, tenseurs,
jauges, ajustements ISO 286, frettage, paliers, roulements, engrenages, freins et moteur. Chaque calcul donne un
verdict, les formules remplies avec vos valeurs, et un dossier de validation qui refait le calcul à la main.

[![Ouvrir dans le navigateur](https://img.shields.io/badge/Ouvrir%20dans%20le%20navigateur-5C4B99?style=for-the-badge)](https://theo33-oss.github.io/MecaStruct/)
[![Télécharger pour Windows](https://img.shields.io/badge/T%C3%A9l%C3%A9charger%20pour%20Windows-3D246C?style=for-the-badge)](https://github.com/theo33-oss/MecaStruct/releases/latest)
[![Licence PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/licence-PolyForm%20Noncommercial%201.0.0-3D246C)](LICENSE)

![Page Poutres : saisie, schéma et diagrammes](application/captures/poutres_calcul.png)

## Deux façons de l'utiliser

| | Dans le navigateur | Sur le bureau (Windows) |
|---|---|---|
| Installation | aucune | un installateur à télécharger |
| Démarrage | quelques dizaines de secondes la première fois | quelques secondes |
| Internet | au premier chargement | jamais après l'installation |
| Données | restent dans votre navigateur | restent sur votre ordinateur |
| En plus | lien de partage d'une étude | dossiers PDF et Word, fichiers sur le disque |

Dans les deux cas, rien n'est envoyé à un serveur : tout est calculé sur votre poste.

## Contenu

| Famille | Pages |
|---|---|
| Structures | Poutres (2D et ossature 3D), Treillis, Flambage |
| Sections et contraintes | Sections, Sollicitations, Tenseurs et critères, Hooke et jauges |
| Liaisons et guidages | Ajustements ISO 286, Frettage, Paliers lisses, Roulements |
| Transmission | Engrenages, Trains épicycloïdaux, Freins et embrayages, Dimensionnement moteur |
| Données et aide | Base de matériaux et de profilés, Convertisseur d'unités, Références |

## Fiabilité

Les moteurs viennent d'une application MATLAB et sont comparés à ses résultats par plus de 1 300 tests.
Ce qui est vérifié, et ce qui ne l'est pas, est écrit dans [LIMITES.md](LIMITES.md).
Outil pédagogique et d'aide au pré-dimensionnement, fourni sans garantie : vérifiez les résultats avant tout usage réel.

## Pour les développeurs

```bash
cd application
python -m venv .venv
.venv\Scripts\pip install -r requirements.lock pytest pytest-qt
.venv\Scripts\python main.py                  # application de bureau
.venv\Scripts\python -m pytest -q -m "not qt"  # tests du calcul (environ 2 min)
```

Le calcul (`application/mecastruct/core`, `services`, `plots`) ne dépend d'aucune interface. Le site (`docs/`) charge
ce même code dans le navigateur avec Pyodide ; `python construire_web.py` le régénère.

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE). Auteur : Théo Brun.

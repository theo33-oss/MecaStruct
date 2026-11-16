# MecaStruct RdM Pro, application de bureau

Application Windows (Python, PySide6), portage de l'application MATLAB de Théo Brun. Elle a la même forme que le
[site](https://theo33-oss.github.io/MecaStruct/) : bandeau, menu en haut par familles, une page par outil. Tout est
calculé sur le poste, sans Internet une fois installée.

## Lancer

Pour l'utiliser, téléchargez l'installateur dans les
[Releases](https://github.com/theo33-oss/MecaStruct/releases/latest). Depuis le code source, double-cliquez sur
`1_Ouvrir_application.bat` (dossier au-dessus de celui-ci) : il prépare Python au premier lancement, puis ouvre la
fenêtre. À la main :

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.lock
.venv\Scripts\python main.py
```

## Organisation

- `main.py` : fenêtre principale (bandeau, menu en haut, pages empilées, chaque page bâtie à sa première ouverture).
  `MENU` reprend les familles et les noms de pages du site (`FAMILLES` et `PAGES` de `docs/app.js`).
- `mecastruct/core/` : moteurs de calcul. `mecastruct/plots/` : graphiques Plotly. `mecastruct/services/` : calculs de
  pages, exemples, import et export, dossier de validation. `data/` : matériaux, profilés, ISO 286…
- `mecastruct/pont/` : le lien entre le site et le calcul (JSON). Le bureau s'en sert pour le bloc-notes et l'Excel de
  validation.
- `mecastruct/bureau/` : l'interface. `theme.py` (couleurs du site, clair et sombre), `state.py` (saisies et
  résultats), `widgets.py` (champs, tableaux, onglets, blocs repliables, graphiques), `tache.py` (calculs longs hors du
  fil de l'interface), `page_calcul.py`, `machine_page.py`, `modes.py` (diagramme des modes de ruine), `exports.py`,
  `dossier.py`, `transfert.py`, `formula_panel.py`, et `pages/` (un fichier par page).
- `tests/` : tests du calcul et de l'interface (pytest, pytest-qt). `python -m pytest -q -m "not qt"` lance le calcul
  seul.
- `tools/capture.py` : capture d'écran d'une page (`python tools/capture.py poutres --calcul`).
  `python main.py --captures dossier` les fait toutes ; `python main.py --verifier fichier.txt` ouvre et calcule
  chaque page.

## Règles

Les moteurs ne dépendent pas de l'interface. Ne jamais modifier `mecastruct/core/` pour les besoins de l'affichage.
Le bureau suit le site, pas l'inverse.

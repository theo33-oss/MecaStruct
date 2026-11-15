# MecaStruct RdM Pro — application de bureau

Portage Windows (Python / PySide6) de l'application web Streamlit, elle-même portage de l'application MATLAB de Théo Brun.
Une vraie fenêtre, sans navigateur ni serveur ; tout est calculé sur le poste, sans Internet une fois installée.

## Lancer

Double-cliquer sur `1_Ouvrir_application.bat` (dossier au-dessus de celui-ci) : il prépare Python au premier lancement,
puis ouvre la fenêtre. À la main : `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`,
`.venv\Scripts\python main.py`.

## Organisation

- `main.py` : fenêtre principale (menu à gauche, pages empilées, chaque page bâtie à sa première ouverture).
- `mecastruct/core/` : moteurs de calcul (inchangés). `mecastruct/plots/` : graphiques Plotly. `mecastruct/services/` :
  calculs de pages, exemples, import/export, dossier de validation. `data/` : bases de matériaux, profilés, ISO 286…
- `mecastruct/bureau/` : l'interface. `state.py` (saisies et résultats), `widgets.py` (briques : champs, tableaux,
  onglets, blocs repliables, graphiques dans QWebEngineView), `tache.py` (calculs longs hors du fil de l'interface),
  `page_calcul.py`, `machine_page.py`, `dossier.py`, `transfert.py`, `formula_panel.py`, et `pages/` (un fichier par page).
- `tests/` : tests des moteurs et de l'interface (pytest, pytest-qt). `python -m pytest` depuis ce dossier.
- `tools/capture.py` : capture d'écran d'une page (`python tools/capture.py poutres --calcul`).

## Règles

Les moteurs ne dépendent pas de l'interface. Ne jamais modifier `mecastruct/core/` pour les besoins de l'affichage.

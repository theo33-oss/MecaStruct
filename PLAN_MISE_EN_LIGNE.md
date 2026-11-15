# Plan de mise en ligne de MecaStruct RdM Pro

Rédigé le 15 novembre 2026, d'après la lecture du dossier `5.1_MecaStruct_Bureau` et du compte rendu du projet
« Chaînes de cotes 1D ». Rien n'est encore modifié dans le code : ce dossier est une copie de travail.

## 1. Hypothèses et décisions à prendre

**Hypothèse sur la taille de l'entreprise** (à corriger si elle est fausse) : une seule personne développe et
maintient l'outil, avec Claude, sans budget de serveur et sans équipe de support. Tout le plan en découle :
zéro euro d'hébergement, aucune base de données, aucun compte utilisateur, le plus possible de tâches automatiques,
et à terme une seule interface à entretenir.

**Décisions qui t'appartiennent.** Ma proposition est en gras ; le plan fonctionne avec l'autre choix.

| Sujet | Choix possibles | Conséquence |
|---|---|---|
| Dépôt GitHub | **public** / privé | GitHub Pages gratuit demande un dépôt public. De toute façon, le Python chargé par le navigateur est lisible par tout visiteur. |
| Licence | **PolyForm Noncommercial 1.0.0** (comme Chaînes de cotes) / autre | À revoir si l'outil doit être vendu ou utilisé chez des clients. |
| Nom du dépôt | **`mecastruct`** | Adresse du site : `theo33-oss.github.io/mecastruct/`. |
| Interfaces à terme | **une seule (web), servie aussi dans la fenêtre de bureau** / deux (Qt et web) | Voir la critique, point 3. À trancher à l'étape 8, pas avant. |
| Signature de l'installateur | **non au début** / certificat payant | Sans certificat, Windows affiche « Windows a protégé votre ordinateur », comme aujourd'hui avec le `.bat`. |
| Aciers | **E = 210 GPa** (actuel) / 190 GPa (MATLAB) | Les flèches diffèrent d'environ 10 % de MATLAB. À écrire sur le site. |
| Droits sur le contenu | demander l'accord avant publication | Les pages Roulements, Engrenages, Trains épicycloïdaux, Freins et Moteur reprennent les formules et les exemples des PDF du cours de l'IUT de Bordeaux. Les tables viennent de normes (ISO 286, ISO 773). |

## 2. L'application aujourd'hui (mesuré)

| | |
|---|---|
| Pages | 20 (7 de calcul, 8 d'éléments de machines, 3 d'outils, Accueil, À propos) |
| Calcul, `core/` | 10 675 lignes, aucun import d'interface |
| Services et dossiers, `services/` | 7 822 lignes, sans Qt |
| Graphiques, `plots/` | 2 678 lignes, Plotly |
| Interface Qt, `bureau/` | 5 048 lignes |
| Tests | 1 335, tous passés, en 12 min 16 s |
| Installation | Python à installer d'abord, puis 1 158 Mo de bibliothèques, 5 à 10 min |
| Suivi de versions | aucun (pas de git) |

## 3. Critique des choix

### Ce qui est bon, à garder tel quel

1. **Le calcul ne connaît pas l'interface.** Vérifié : `core/` n'importe ni `services`, ni `plots`, ni `bureau` ;
   `services/` et `plots/` n'importent ni Qt ni Streamlit. C'est ce qui rend le site possible sans réécrire un calcul.
2. **Les services rendent tous la même forme** (`result`, `tables`, `status`, `ok`). Une seule brique d'affichage web
   peut donc servir plusieurs pages.
3. **Les pages d'éléments de machines sont déclaratives** : `ajustements.py` fait 39 lignes (champs, calcul,
   graphique). Les huit pages se ressemblent : on écrit une page web générique, pas huit.
4. **Les données sont en JSON** dans `data/`, pas dans le code.
5. **1 335 tests et des références MATLAB.** L'audit (`AUDIT_CONCEPTEUR.md`) dit franchement ce qui est vérifié ou non.
6. **Le fichier de projet est déjà un JSON** avec un numéro de format : il pourra s'ouvrir dans les deux versions.

### Ce qui pose problème

| n° | Constat | Pourquoi c'est gênant | Ce que le plan en fait |
|---|---|---|---|
| 1 | Installation : Python requis, 1,16 Go, 5 à 10 min, un `.bat`, un avertissement Windows | Un collègue ou un client abandonne avant d'avoir vu l'outil | Étape 3 : un vrai installateur, fabriqué automatiquement |
| 2 | La fenêtre Qt embarque un navigateur complet (QtWebEngine) pour afficher les graphiques Plotly | C'est la plus grosse part du poids, et l'interface est déjà à moitié du web | Argument pour l'interface unique (point 3) |
| 3 | Quatrième interface en vue : MATLAB, puis Streamlit, puis Qt, et maintenant HTML | Avec 20 pages, entretenir Qt **et** le site double chaque évolution. C'est trop pour une personne | Étape 8 : la fenêtre de bureau affiche l'interface web. Qt est gelé dès l'étape 4 (corrections seulement) |
| 4 | `pandas` est importé dans le calcul (4 fichiers de `core/`) et dans presque tous les services | Chaînes de cotes l'avait évité : il alourdit le chargement dans le navigateur | Étape 2 : on mesure. On ne le retire que si le chiffre l'impose |
| 5 | Fichiers très gros : `validation_report.py` 143 Ko, `geometry.py` 85 Ko, `beam_solver.py` 80 Ko, `widgets.py` 50 Ko | Difficiles à relire, risqués à modifier | Pas touchés avant la mise en ligne. Découpage par domaine ensuite, un fichier à la fois |
| 6 | Pas de git, pas de licence, version figée à 0.1.0, fichiers de chantier à la racine, `AVANCEMENT.md` périmé (il liste comme « restant » des pages qui existent) | Aucun retour arrière possible, rien de publiable | Étape 1 |
| 7 | Le `.bat` installe `requirements.txt` (plages de versions) et non `requirements.lock` | Deux postes peuvent avoir des bibliothèques différentes, donc des résultats différents | L'installateur fige les versions |
| 8 | Des références MATLAB ont été alignées à la main (E de 190 à 210 GPa) | Une référence modifiée ne prouve plus rien | Étape 1 : écrit dans les limites connues. Plus tard : références refaites sous MATLAB avec E = 210 |
| 9 | Données non recoupées avec la norme : clavettes ISO 773 ressaisies à la main, colonnes a, b, cd, d, t à zc de l'ISO 286, limites P-V des paliers | Sur un site public, une valeur fausse coûte la crédibilité de tout l'outil | Étape 4 : chaque page affiche son état de vérification |
| 10 | Le dossier HTML charge MathJax depuis Internet | Il n'est pas « autonome » hors connexion, l'audit le note déjà | Étape 7 : MathJax et Plotly servis par le site lui-même |
| 11 | Fenêtre sans barre de menus, sans raccourcis, sans icône, sans question « enregistrer ? » à la fermeture ; annuler et rétablir pour Poutres seulement | Ce sont les habitudes d'un logiciel de bureau | Fait une seule fois, dans l'interface web (étape 4), et hérité par le bureau |
| 12 | Les tests durent 12 minutes | On ne les lance pas à chaque modification | Étape 1 : un jeu rapide (calcul seul) et le jeu complet sur GitHub |
| 13 | Le nom dit « Pro », le mode d'emploi dit « outil pédagogique, résultats à vérifier » | Message contradictoire pour un visiteur | Une phrase claire en haut du site, les mêmes mots partout |
| 14 | Noms en anglais dans `core/` (hérités de MATLAB), en français dans `bureau/` | Gêne légère | Règle : on ne renomme pas `core/` (traçabilité MATLAB), tout ce qui est nouveau est en français |

## 4. Architecture cible

Même principe que Chaînes de cotes, avec une différence : **une seule interface**.

```
                     interface web (HTML, CSS, JavaScript, sans framework)
                                        │
                                   pont (JSON)
                    ┌───────────────────┴────────────────────┐
        site GitHub Pages                            fenêtre de bureau
   Python dans le navigateur (Pyodide)        même page dans la fenêtre Qt,
   aucune installation                        Python natif (rapide, hors ligne,
                                              PDF et Word, fichiers sur le disque)
                    └───────────────────┬────────────────────┘
                        mecastruct/core, services, plots, data (inchangés)
```

- Le **pont** est le seul lien entre l'affichage et le calcul. Il reçoit du JSON, appelle un service, rend du JSON.
  Un fichier de pont par famille de pages (voir 5.1), pas un fichier unique de 300 Ko.
- La **description des champs** (libellé, unité, bornes, aide) quitte le code Qt pour un fichier de données par page.
  Les deux interfaces la lisent : une seule source.
- Dans le navigateur, les bibliothèques se chargent **par groupes**, à la première page qui en a besoin (voir 5.3).
- Tant que l'étape 8 n'est pas faite, l'application Qt actuelle reste la version de bureau. Elle est déjà livrable.

## 5. Regroupements proposés

### 5.1 Le menu : de 19 entrées à 5 familles

| Famille | Pages regroupées | Pourquoi ensemble |
|---|---|---|
| **Structures** | Poutres (2D et ossature 3D), Treillis, Flambage | On part d'une structure chargée et on cherche efforts, flèches, stabilité |
| **Sections et contraintes** | Sections, Sollicitations (traction, cisaillement, torsion, flexion), Tenseurs et critères, Hooke et jauges | On part d'une section ou d'un état de contrainte en un point |
| **Liaisons arbre-moyeu et guidages** | Ajustements ISO 286, Frettage, Clavette, Goupille, Paliers lisses, Roulements | Le parcours réel du concepteur : choisir l'ajustement, vérifier le frettage ou la clavette, puis le guidage. Clavette et Goupille sont aujourd'hui cachées dans Sollicitations : un lien les montre aussi ici, sans déplacer le calcul |
| **Transmission de puissance** | Engrenages et Trains épicycloïdaux (une page, deux onglets), Freins et embrayages, Dimensionnement moteur | La chaîne du moteur au récepteur |
| **Données et aide** | Base de données (matériaux, profilés), Convertisseur, Références, Guide utilisateur, Note de calcul, Limites connues, À propos | Tout ce qui ne calcule pas |

L'Accueil présente ces cinq familles avec une phrase et un exemple à charger pour chacune.
Les passages de valeurs entre pages qui existent déjà (`transfert.py`) deviennent des boutons visibles :
« Envoyer cette section vers Poutres », « Vérifier le frettage de cet ajustement ».

### 5.2 Le dépôt

```
application/
  mecastruct/core/        calcul (inchangé)
  mecastruct/services/    calculs de pages, dossiers, fichiers (inchangé pour l'instant)
  mecastruct/plots/       graphiques Plotly (inchangé)
  mecastruct/pont/        NOUVEAU : un module par famille, entrées et sorties en JSON
  mecastruct/bureau/      interface Qt (gelée à partir de l'étape 4)
  data/                   tables JSON, plus pages/ : la description des champs de chaque page
  aide/                   guide et note de calcul (aujourd'hui application/docs, nom pris par le site)
  tests/
  tools/                  capture.py, preview_plots.py, ouvre.py
docs/                     le site : index.html, style.css, app.js, js/ (une page par fichier), mecastruct.zip (généré)
construire_web.py         fabrique le zip et les empreintes d'adresses (repris de Chaînes de cotes)
construire_bureau.py      fabrique l'installateur
.github/workflows/        tests à chaque envoi, installateur à chaque version
LICENSE, README.md, LIMITES.md, LISEZ-MOI.txt, 1_Ouvrir_application.bat
```

Fichiers de la racine actuelle :

| Fichier | Sort |
|---|---|
| `baseline.txt`, `finale.txt` | supprimés (journaux de tests du portage) |
| `patch_tests.py`, `remplace.py` | supprimés (outils à usage unique du portage) |
| `ouvre.py` | déplacé dans `application/tools/` |
| `fabrique_zip.py`, `A_PARTAGER_MecaStruct.zip` | remplacés par l'installateur ; le zip n'est jamais mis dans git |
| `application/AVANCEMENT.md` | supprimé (périmé) |
| `application/AUDIT_CONCEPTEUR.md` | gardé en privé (`.claude/`) ; sa partie utile au public devient `LIMITES.md` |
| `application/captures/` | gardées, servent au README et à la page d'accueil du site |

### 5.3 Les bibliothèques, par groupes de chargement

| Groupe | Contenu | Chargé quand | Pages servies |
|---|---|---|---|
| Socle | Pyodide, numpy, pandas, le zip `mecastruct`, Plotly côté navigateur | à l'ouverture du site | Accueil, Convertisseur, les 8 pages d'éléments de machines, Treillis, Tenseurs |
| Calcul avancé | scipy | à la première page concernée | Poutres, Flambage, Sollicitations |
| Géométrie | shapely | à l'ouverture de Sections | Sections |
| Symbolique | sympy | à la demande (il est déjà optionnel dans le code) | formules littérales |
| Exports | openpyxl, puis python-docx, reportlab et matplotlib | au clic sur un export | Excel, Word, PDF |

Ce tableau est une cible, à confirmer à l'étape 2. Aujourd'hui `services/compute.py` importe tous les moteurs d'un
coup, et les services de Poutres importent `geometry` (donc scipy et shapely) : sans retouche de ces imports, tout se
charge dès l'ouverture.

Le même découpage range les fichiers `requirements` : calcul, rapports, bureau, développement.

### 5.4 Les pages du site, par lots de mise en ligne

| Lot | Pages | Raison de l'ordre |
|---|---|---|
| A | Accueil, Ajustements, Frettage, Paliers lisses, Convertisseur | Légères et déclaratives : elles servent à poser tout le socle |
| B | Roulements, Engrenages et épicycloïdaux, Freins et embrayages, Dimensionnement moteur | Même brique que le lot A, plus les schémas qui suivent la saisie |
| C | Poutres 2D, puis Treillis | La page phare, la plus grosse (528 lignes côté Qt, 754 pour l'ossature 3D) |
| D | Sections, Sollicitations, Flambage | Demandent scipy et shapely |
| E | Tenseurs, Hooke et jauges, Ossature 3D | Affichage 3D |
| F | Base de données, Références, dossier de validation, fichier de projet, lien de partage | Ce qui traverse toutes les pages |

## 6. Le plan, étape par étape

Les durées sont des ordres de grandeur en jours de travail avec Claude, pas des engagements.
Chaque étape finit par une vérification à l'écran et un envoi sur GitHub.

### Étape 0. Copie de travail (faite le 15 novembre 2026)

`5.1_MecaStruct_Bureau_GitHub` contient les 205 fichiers du projet (9,5 Mo). L'environnement Python (`.venv`,
1 158 Mo) et les caches ne sont pas copiés : le `.bat` les recrée au premier lancement. L'ancien dossier est intact.

### Étape 1. Ranger, mettre sous git, créer le dépôt (0,5 à 1 jour)

1. Appliquer le rangement de la partie 5.2 (racine, `application/docs` renommé en `application/aide`).
2. Écrire `.gitignore`, `LICENSE`, `README.md` (ce que fait l'outil, deux captures, comment lancer), `LIMITES.md`.
3. Écrire les consignes privées `.claude/CLAUDE.md`, ignorées par git : où est quoi, quels fichiers ne pas lire en
   entier, quels tests lancer.
4. Séparer les tests : un jeu rapide (calcul seul, sans fenêtre) pour chaque modification, le jeu complet avant un envoi.
5. Recréer l'environnement, lancer les 1 335 tests, ouvrir l'application : tout doit marcher comme dans l'ancien dossier.
6. `git init`, premier commit, création du dépôt sur GitHub, premier envoi.
7. GitHub Actions : les tests de calcul tournent à chaque envoi.

Fini quand : le dépôt est en ligne, les tests sont verts sur GitHub, l'application s'ouvre depuis le nouveau dossier.

### Étape 2. Essai de la partie risquée : le calcul dans le navigateur (1 jour)

Une page vide qui charge Pyodide et `mecastruct`, puis calcule l'exemple de Poutres, celui de Sections et celui
d'Ajustements. Aucune interface.

À mesurer : poids téléchargé, durée du premier chargement, durée d'un rechargement, durée de chaque calcul,
bibliothèques qui refusent de se charger, écart avec les résultats du bureau (il doit être nul).

| Résultat | Décision |
|---|---|
| Premier chargement sous 30 s, rechargement sous 5 s | On continue tel quel |
| Trop lent à cause de `pandas` | On le retire de `core/` (4 fichiers), tests de référence à l'appui |
| Une bibliothèque ne se charge pas | La page concernée reste réservée au bureau, et le site le dit |

Repère : Chaînes de cotes charge numpy et scipy en 9 à 12 s. MecaStruct ajoute pandas, shapely et Plotly : il faut
s'attendre à plus, d'où le chargement par groupes.

Fini quand : les chiffres sont dans un tableau et la décision est prise avec toi.

### Étape 3. Le téléchargement pour le bureau (1 à 2 jours, peut se faire en parallèle de l'étape 4)

1. `construire_bureau.py` : PyInstaller fabrique un dossier autonome avec Python, les bibliothèques aux versions
   figées et l'application. Inno Setup en fait un installateur : `MecaStruct_Installation_x.y.z.exe`.
2. L'installateur crée l'icône sur le Bureau et l'entrée du menu Démarrer, et s'installe sans droits d'administrateur.
3. GitHub Actions le fabrique à chaque étiquette de version (`v1.0.0`) et le publie dans les « Releases » du dépôt.
4. Le site a un bouton « Télécharger pour Windows » qui pointe toujours vers la dernière version, avec le poids,
   la date et la marche à suivre devant l'avertissement de Windows.
5. Numéro de version unique (dans `pyproject.toml`), affiché dans À propos, et un fichier des changements.
6. Essai sur un poste sans Python.

Fini quand : un poste neuf installe et ouvre l'application en moins de deux minutes, sans Internet après téléchargement.
Poids de l'installateur : à mesurer (QtWebEngine pèse lourd ; l'étape 8 le fera baisser ou disparaître).

### Étape 4. Le socle du site et la première mise en ligne, lot A (3 à 5 jours)

Repris de Chaînes de cotes, sans le réinventer : `construire_web.py` et les empreintes d'adresses, la barre de
chargement à étapes, le thème clair et sombre sans flash, les bulles d'aide, la sauvegarde automatique dans le
navigateur, annuler et rétablir, le collage depuis Excel, les nombres à la française, l'icône et le titre d'onglet.

Nouveau, propre à MecaStruct :

1. Le menu à cinq familles, une adresse par page (`#/ajustements`), un fichier JavaScript par page chargé à la demande.
2. La page générique « champs, Calculer, verdict, graphique, synthèse, explications », pilotée par la description
   des champs. Elle sert les huit pages d'éléments de machines.
3. Le verdict d'abord, en toutes lettres, puis les tableaux. L'avertissement « saisie modifiée depuis le calcul ».
4. Un bandeau fixe : « Tout est calculé dans votre navigateur. Outil d'aide au pré-dimensionnement : résultats à vérifier. »
5. L'état de vérification de chaque page (vérifié contre MATLAB, contre le classeur, contre la norme, ou non vérifié),
   tiré de `LIMITES.md`.
6. La page d'accueil lisible pendant le chargement, avec le bouton de téléchargement.
7. Un test qui compare, pour chaque page en ligne, le résultat du pont et celui du service.

Fini quand : le site est en ligne avec cinq pages, et un calcul donne le même nombre que dans l'application de bureau.

### Étape 5. Lots B et C (5 à 8 jours)

Lot B avec la brique générique et les schémas qui suivent la saisie. Puis Poutres 2D : saisie des appuis et des
charges en tableaux, schéma, diagrammes, explications du calcul, exemples, combinaisons et Eurocode 3. Puis Treillis.
Une page à la fois, mise en ligne dès qu'elle est vérifiée à l'écran.

### Étape 6. Lots D et E (5 à 8 jours)

Sections (shapely chargé à la demande), Sollicitations et ses quatre onglets, Flambage, Tenseurs, Hooke et jauges,
Ossature 3D.

### Étape 7. Lot F : ce qui traverse toutes les pages (3 à 5 jours)

1. Fichier de projet : enregistrer et ouvrir, le même JSON que le bureau, avec un test d'aller-retour entre les deux.
2. Dossier de validation en HTML, avec MathJax et Plotly servis par le site. Le PDF passe par l'impression du
   navigateur. Le Word et le PDF « natifs » restent d'abord réservés au bureau.
3. Lien de partage d'une étude (l'étude est dans l'adresse), fichier ouvert vérifié et limité en taille.
4. Base de données de matériaux et de profilés, avec les ajouts de l'utilisateur gardés dans le navigateur.
5. Export Excel dont les formules refont le calcul, pour une ou deux pages où cela a du sens (Ajustements, Frettage).

### Étape 8. Une seule interface (3 à 5 jours, après parité du site)

La fenêtre de bureau affiche l'interface web et appelle le pont en Python natif, sans Pyodide. Les 5 000 lignes de
pages Qt sont retirées. Le bureau garde ses avantages : démarrage rapide, hors ligne, fichiers sur le disque, PDF et
Word. On mesure le nouvel installateur.

Si tu préfères garder Qt, cette étape est remplacée par une règle : toute évolution se fait dans les deux interfaces,
et un test vérifie que les libellés et les aides sont identiques.

### Étape 9. Finitions professionnelles (2 à 3 jours)

- Site installable et utilisable hors ligne après la première visite (PWA), pour les postes où l'on ne peut rien installer.
- Contrôle au clavier, contrastes, lecture sur téléphone pour les pages simples.
- Aperçu quand on partage le lien, mentions légales, page « Limites connues », moyen de signaler une erreur
  (les « Issues » du dépôt).
- En option : un nom de domaine (environ 10 à 15 € par an). Aucun outil de statistiques par défaut.

## 7. Ce que le plan écarte volontairement

- **Serveur, comptes, base de données** : inutiles ici, et impossibles à tenir seul. GitHub Pages n'en propose pas.
- **Réécriture en C++ ou en TypeScript** : le calcul est léger, il existe, il est testé. Le réécrire serait le
  cinquième portage.
- **Framework web** (React ou autre) : Chaînes de cotes s'en passe, et tu sais déjà relire ce code.
- **Refonte de `core/` et découpage des gros fichiers avant la mise en ligne** : aucun gain pour l'utilisateur,
  un risque sur 1 335 tests.
- **Mac et Linux en téléchargement** : le site les couvre déjà.
- **Bibliothèque commune avec Chaînes de cotes** : on copie ce qui sert. Deux projets ne justifient pas un troisième dépôt.

## 8. Risques

| Risque | Parade |
|---|---|
| Chargement trop long dans le navigateur | Étape 2 avant tout le reste, chargement par groupes, cache hors ligne |
| Vingt pages à refaire en web : gros volume | Page générique pour les huit pages de machines, lots mis en ligne un par un |
| Une valeur fausse publiée | État de vérification visible par page, `LIMITES.md`, recoupement des tables avec les normes |
| Contenu de cours ou de norme publié sans accord | Demander l'accord avant de rendre le dépôt public, sinon retirer les exemples concernés |
| Avertissement Windows à l'installation | Expliqué sur la page de téléchargement ; certificat payant si l'outil se diffuse |
| Deux interfaces qui divergent pendant la transition | Qt gelé dès l'étape 4, corrections de calcul dans `core/` seulement |

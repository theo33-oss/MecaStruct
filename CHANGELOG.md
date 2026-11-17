# Journal des changements

Le numéro de version est celui de `application/mecastruct/__init__.py`. Le site suit toujours la dernière version ;
l'installateur Windows de chaque version est dans les [Releases](https://github.com/theo33-oss/MecaStruct/releases).

## Non publié (site)

- Poutres : plus de gel quand on tape une petite longueur ; section au choix (catalogue, forme paramétrée, tige
  filetée ISO avec son schéma d, d2, ds, d3, page Sections ou valeurs à la main) avec son image ; poids propre coché
  de base et bloc Calcul ouvert ; le schéma de la poutre ne plante plus avec le poids propre.
- Sécurité en coefficient s ou en marge (%) sur toutes les pages qui demandent s (marge = s − 1), dans le diagramme
  des modes de ruine et le bloc-notes.
- Cisaillement : Jourawski, clavette et goupille comptent dans le verdict (un mode non admissible rend le calcul
  « NON vérifié »).
- Pied de page : numéro de build à côté de la version, bouton « Actualiser le site » (efface les copies gardées et recharge), avertissement quand la page est plus ancienne que le site en ligne. Bouton « Calculer » aussi au-dessus du schéma.
- Poutres : le tranchant est vérifié pour toute section (Jourawski, τ max ≤ Re/(2·s)), plus seulement pour les profilés IPE, HEA, HEB, IPN ; le « taux » remplace la « marge » dans la phrase de verdict.
- Tige filetée : tableau ISO de H7g6.fr (M3 à M72, pas gros et pas fins), source citée dans la page Références, dans l'aide des champs et sur le schéma.
- Matériaux : C45 normalisé (C45N), C45 trempé-revenu (C45V) et C35 normalisé (C35N), valeurs minimales de l'EN 10083-2 (à vérifier sur la norme).
- Graphiques à hauteur réglable, liste d'exemples qui garde l'exemple chargé, cas personnalisé (tableaux vides).

## 1.6.0 (16 novembre 2026)

- Bureau : l'accueil est celui du site (titre, deux façons de l'utiliser, une carte par famille) ; « Données et aide »
  dans le même ordre que le site ; nouvelle page « Limites et vérifications ».
- Un modèle de signalement d'erreur sur GitHub ; badges tests et dernière version dans le README.

## 1.5.0 (16 novembre 2026)

- Bureau : même forme que le site. Bandeau (thème, contraste, bouton « Version en ligne »), menu en haut par
  familles, mêmes noms de pages, une phrase sous chaque titre.
- Bureau : thème clair et sombre aux couleurs du site, champs en grille, cartes de valeurs clés sous le verdict.

## 1.4.1 (16 novembre 2026)

- Installateur : le bloc-notes et l'Excel de validation fonctionnent dans l'application installée.

## 1.4.0 (16 novembre 2026)

- Treillis : contrainte et flambage d'Euler de chaque barre, avec tableau, diagramme, Excel et dossier.
- Bureau : diagramme des modes de ruine, boutons Bloc-notes et Excel de validation, verdict en tête des pages,
  virgule décimale dans les valeurs et les tableaux.
- Site : onglets au clavier (flèches), convertisseur « 1 000 000 », messages d'erreur sans « 1e+09 ».
- Pas d'installateur pour cette version, remplacée par la 1.4.1.

## 1.3.2 (16 novembre 2026)

- Poutres, ossature 3D et treillis : exemples nommés en clair, statut en toutes lettres, virgule décimale dans les
  graphiques et les tableaux.
- Ossature 3D : la contrainte de la pièce la plus sollicitée est comparée à Re (l'équilibre seul ne donne plus
  « vérifié »).
- Eurocode 3 : taux seul pour les rapports sans unité.

## 1.3.1 (16 novembre 2026)

- Diagramme des modes de ruine plus clair : coefficient de sécurité pour une résistance, marge pour une limite.
- Site : résultat affiché dès l'ouverture d'une page, matériaux rangés par famille.
- Ajustements sans « vérifié » ; conditions de montage du train épicycloïdal affichées.

## 1.3.0 (16 novembre 2026)

- Diagramme des modes de ruine sous « Résultat » : valeur, limite, coefficient de sécurité obtenu et demandé.
- Exports bloc-notes (.txt) et Excel de validation, où le calcul est refait par des formules (11 calculs).

## 1.2.0 (16 novembre 2026)

- Page Références (normes, cours, documents) ; la source de chaque calcul est citée sous sa page.
- Matériaux alignés sur les fiches (EN-GJL-300, AlSi10Mg, FGS 400-15, TA6V, CuZn39Pb3, 42CrMo4, inox 420, PEEK).
  E de l'acier confirmé à 210 GPa.
- Fatigue : limite d'endurance σD saisissable, Kf réglable.
- Site : boutons de transfert entre pages, abaques Kt, dossier de validation des pages de machines, dossier prêt à
  imprimer en PDF.
- 23 exemples des cours ajoutés aux tests.
- Pas d'installateur pour cette version.

## 1.1.0 (15 novembre 2026)

- Site : toutes les pages de RdM (poutres 2D, ossature 3D, treillis, sections, sollicitations, flambage, tenseurs,
  Hooke et jauges), combinaisons, Eurocode 3, fatigue, charge mobile, base de données, références.
- Site : enregistrer, ouvrir et partager une étude ; export Excel des résultats ; usage hors ligne après la première
  visite.

## 1.0.0 (15 novembre 2026)

- Première version publique : dépôt, licence, limites connues, tests sur GitHub.
- Installateur Windows (application autonome, auto-vérification à chaque version).
- Site : huit pages d'éléments de machines et le convertisseur.

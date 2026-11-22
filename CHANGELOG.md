# Journal des changements

Le numéro de version est celui de `application/mecastruct/__init__.py`. Le site suit toujours la dernière version ;
l'installateur Windows de chaque version est dans les [Releases](https://github.com/theo33-oss/MecaStruct/releases).

## 1.7.0 (17 novembre 2026)

- Bureau : section de Poutres au choix (profil, forme paramétrée, tige filetée ISO avec son schéma d, d2, ds, d3) ; forces inclinées (F, plan, α) dans Poutres et l'ossature 3D ; poids propre coché de base.
- Bureau et site : marge de sécurité en % (marge = s − 1) sur toutes les pages qui demandent s ; diagramme des modes en marge.
- Calcul : cisaillement complet (Jourawski, clavette, goupille) dans le verdict ; tranchant de toute section ; s strictement positif ; flambage borné ; messages d'erreur plus clairs (treillis, fichier, mécanisme) ; matériaux C45N, C45V, C35N ; tableau des filetages ISO de H7g6.fr (source dans Références).
- Site : numéro de build, bouton « Actualiser le site », avertissement de version ancienne, bouton Calculer au-dessus du schéma, repère x, y, z sur le schéma de la poutre, exposants lisibles (2,487·10⁷).

## Non publié (site)

- Site, finitions : « Charger l'exemple » partout, profilé du catalogue affiché après l'exemple, types d'appui et de liaison en français (valeurs internes inchangées), note sur l'exemple de Traction (cas non conforme voulu), noms accessibles pour tableaux, onglets, figures et bloc Décision (un seul verdict annoncé), recherche élargie (Goodman, Wöhler, Rankine, ressort, soudure…), bouton « Dossier à imprimer (PDF via Imprimer) », graphiques lisibles à 375 px (légende sous le graphique, marges réduites).
- Site, lecture du résultat : bloc « Décision » en tête (verdict en texte, icône et couleur, coefficient de sécurité minimal, mode dimensionnant, action conseillée), barre résumé en bas sur petit écran, lien « Aller à la cause » vers le paramètre à modifier (section, longueur, diamètre… plutôt que la charge imposée) ; verdict « Information » pour les calculs sans critère de conformité ; avertissements (angle de pression ≠ 20°, appui différent de la longueur L) ; « Résultat ancien — à recalculer » quand la saisie a changé.
- Site, corrections après audit : mode guidé utilisable sur mobile (le champ visé n'est plus caché), figures qui gardent leur taille après un repli de panneau, panneau « Demander à une IA » au-dessus de la carte du guide, débordement horizontal de Poutres à 375 px.
- Site, chargement : le menu s'affiche sans attendre Pyodide ni Plotly (scripts différés, CSS KaTeX non bloquant) ; pendant la préparation, étapes, secondes écoulées, pages déjà lisibles et bouton « Voir un exemple sans attendre » (capture existante).
- Site, navigation : recherche globale (`/` ou Ctrl+K) par page, grandeur, norme ou mot usuel ; « Mes études » sur l'accueil (récentes, favoris, copies nommées, export et import JSON, conservés dans ce navigateur) ; étoile Favori sur chaque page ; une famille rouvre sa dernière page visitée ; mention « Utilisable hors ligne » ; le service worker ne met plus en cache les adresses `?verif=` et `?maj=`.
- Site, mobile et mise en page : trois colonnes dès 1500 px (schéma replié au-dessus des champs en dessous), champs à 16 px sur tactile (plus de zoom iPhone) et clavier avec « − », hauteur de la barre collante mesurée, couches (infobulle, graphiques, languette IA) corrigées, Échap ferme un seul composant, un seul bouton « Calculer » principal, accueil ouvert sur grand écran.
- Site, accessibilité : seule la phrase du bilan est annoncée par les lecteurs d'écran ; graphiques en `role="img"` avec nom, défilement tactile libre ; onglets ARIA ; contrastes du thème sombre et mode contraste forcé ; aides au survol lisibles au clavier (un seul arrêt par mode de ruine) ; toast présent dès le départ ; textes des graphiques à 12 px minimum, étiquettes de la poutre et du treillis qui ne se recouvrent plus.
- Site, fiabilité : une page lente ne s'ajoute plus sous une autre ; un champ invalide garde son texte et reste signalé ; les liens de partage collés après le chargement fonctionnent ; un stockage local abîmé ne donne plus de page blanche ; échec de chargement avec message et bouton « Réessayer » ; le focus clavier reste sur le champ modifié et va sur le titre au changement de page.
- Site, saisie : erreur de champ seulement à la sortie du champ (ou après une pause), ancien résultat grisé au lieu d'être effacé, messages avec nom et unité, texte invalide conservé dans les tableaux, étude ouverte validée, « Annuler » après « Charger l'exemple », confirmation avant de supprimer un matériau, clics répétés regroupés en un calcul.
- Calcul : Poutres refuse L, E, G, Re ≤ 0 et Kt < 1 ; « Calculer les combinaisons » et la recherche de profilé disent « Mécanisme… » au lieu d'afficher nan ; convertisseur : refus sous le zéro absolu et des résultats infinis ; recherche de matériaux sans espaces parasites, aucune catégorie cochée = aucun résultat.
- Site : défilement indépendant des colonnes ; message de la tige filetée sur deux lignes ; titres de sections au style des autres titres ; « Demander à une IA » en languette latérale ; accueil à titres repliables ; panneau « Représentation » escamotable (mémorisable par page) ; notification et bouton « Actualiser » après un changement de matériau ; mode guidé pas à pas ; zone « Comparer des études » (variantes, tableau, graphique, export JSON, copie vers Excel, impression).
- Site : les bibliothèques des pages lourdes (scipy, shapely, jinja2, sympy) se chargent en arrière-plan dès que l'accueil est prêt.
- Engrenages : champ « Angle de pression » (14,5° à 25°, 20° par défaut) pour les efforts, le schéma, l'Excel et le dossier de validation ; la contrainte en pied de dent reste calculée pour un profil à 20°.
- « Demander à une IA » : bouton fixe en bas à gauche du site (et bouton de la barre d'exports du bureau). Il copie l'étude (consigne + bloc-notes : données, modes de ruine, résultats, démarche) ; on la colle dans Claude ou ChatGPT (liens proposés), l'IA présente le problème, puis on lui pose ses questions. Rien n'est envoyé automatiquement.
- Diagramme des modes de ruine : pour une limite (norme comme VEd/Vpl,Rd, durée, rigidité…), « marge » devient « réserve » (1 − taux, au plus 100 %), pour ne plus la confondre avec la marge de sécurité s − 1 ; une réserve presque pleine s'écrit « > 99,9 % » et non « 100 % ». Même mot dans le bureau et le bloc-notes.
- `construire_web.py` garde le zip tel quel quand son contenu n'a pas changé : une autre version de zlib (Python 3.14+ sous Windows, nouvelle image Ubuntu de la CI) ne fait plus échouer le contrôle « docs/ est à jour ».
- Sécurité : les scripts et styles tiers (Pyodide, Plotly, KaTeX, html-to-image) portent une empreinte `integrity` : le navigateur refuse un fichier modifié sur le CDN. `application/tools/verifier_sri.py` (lancé par la CI) vérifie que les empreintes sont toujours bonnes.
- Tableaux : les écarts de l'ordre de 10⁻¹³ % (bruit d'arrondi) s'affichent « 0 » (flèche des poutres, comparaison des sections).
- Erreurs lisibles : une division par zéro ou un dépassement de capacité affichent une phrase en français (plus de « float division by zero » ni de « (34, 'Numerical result out of range') »). Les champs refusent les valeurs au-delà de 10¹⁸ avec un message (site et bureau), et le calcul fait de même pour les valeurs venues d'un fichier ou d'un lien.
- Retour visible des boutons qui copient ou enregistrent (Copier le lien de l'étude, Copier l'image, Copier le tableau, Copier la valeur, Enregistrer l'étude, Excel) : le bouton passe au vert avec une coche et un petit rebond pendant 2 s, et un message flottant en bas de l'écran confirme l'action (aussi après un téléchargement ou l'ouverture d'une étude). Rouge et secousse si la copie échoue ; sans animation si le système demande de réduire les mouvements.
- Tests : la CI lance maintenant les tests de l'interface de bureau (Qt hors écran) et un contrôle du site : `docs/` doit être celui que `construire_web.py` fabrique, et les 24 calculs donnent les mêmes résultats dans le navigateur (Pyodide) et sur le bureau (`application/tools/parite_site.py`). Le compteur de références du test de la page Références suit `data/references.json`.
- Téléphone : en-tête réduit de moitié (marque et thème sur une ligne, bouton « Télécharger pour Windows » masqué), fondu sur le bord des menus qui défilent et entrée courante centrée ; zones tactiles de 40 px (liens du pied de page, cases à cocher, petits boutons).
- Accessibilité : le champ du coefficient de sécurité (ou de la marge) a son propre nom pour un lecteur d'écran.
- Chargement : la roue de plotly et le zip du calcul se téléchargent en parallèle de Pyodide au lieu d'à la suite.
- Nom : « MecaStruct RdM Pro » devient « MecaStruct RdM » (site, bureau, installateur, dossiers, aides). Les études enregistrées sous l'ancien nom s'ouvrent toujours ; l'installateur remplace l'installation existante.
- Site : le lien « Aller au contenu » ne renvoie plus à l'accueil (le focus va au contenu, la page reste la même) ; « ?maj=… » disparaît de l'adresse après l'actualisation ; adresse canonique ; version dans le pied de page avant le chargement du script.
- Bouton « Copier l'image » au-dessus des graphiques, du schéma, du verdict, des explications du calcul et des tableaux : une image PNG du bloc va dans le presse-papiers (à coller dans Word ou un mail), ou se télécharge si le navigateur refuse la copie. Le bloc est recopié dans un cadre à marge égale : bord droit entier, pas d'espace vide en haut, sans les soulignés des bulles d'aide. Pour « Schéma », « Résultat » et les blocs complémentaires, le bouton est sur la ligne du titre. Image serrée au ras du cadre du verdict.
- Thème : après foncé → clair → foncé, le schéma de la poutre ne reste plus noir sur fond sombre (la figure d'origine n'est plus modifiée par Plotly).
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
- Modes de ruine : quand la valeur calculée dépasse la limite du matériau (s < 1), la ligne ajoute « dépasse la limite du matériau de X % ».
- Poutres et ossature 3D : force inclinée avec les colonnes F, plan et α (xy, xz ou yz ; Poutres : xy ou xz) qui remplissent Fx, Fy, Fz ; une seule flèche sur le schéma des poutres dans le plan xy.
- Force inclinée : on peut revenir à Fx, Fy, Fz à la main (taper une composante ou vider F ; les autres composantes repartent de 0) ; repère x, y, z sur le schéma de la poutre.
- Audit des saisies absurdes : le flambage ne gèle plus avec une section énorme ; s doit être strictement positif ; les nombres infinis (1e400) sont refusés ; Treillis nomme le nœud inexistant d'un appui, d'une charge ou d'une barre ; le train épicycloïdal refuse Ne = 0 ; une pièce non chargée affiche « marge illimitée ».
- Finitions : exposants en « 2,487·10⁷ » au lieu de « 2,487e+07 » ; un message d'erreur ne cache plus le suivant ; messages de fichier vide ou illisible en français ; poutre en mécanisme : « Ajoutez ou déplacez un appui » ; lien de partage abîmé : la page invite à calculer ; liste « Coefficient s / Marge » plus grande au doigt.
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

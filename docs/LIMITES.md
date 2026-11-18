# Limites connues

MecaStruct RdM est un outil pédagogique et d'aide au pré-dimensionnement. Les résultats doivent être vérifiés
avant tout usage réel. Cette page dit ce qui a été vérifié, et contre quoi.

## État de vérification par page

| Page | Vérifié contre | Reste à vérifier |
|---|---|---|
| Poutres 2D | Application MATLAB d'origine (références « golden »), un cas refait à la main | Charge mobile absente des explications ; réactions surabondantes des poutres hyperstatiques non contrôlées |
| Ossature 3D | Équilibre global ΣF, ΣM | Pas de référence indépendante |
| Treillis (efforts), Sections, Sollicitations, Flambage, Tenseurs, Hooke et jauges | Application MATLAB d'origine (références « golden ») | Pas de recalcul indépendant à la main |
| Treillis (vérification des barres, depuis 1.4.0) | Formules refaites à la main dans les tests, dossier de validation et Excel de validation | Flambage d'Euler seul : barre articulée aux deux bouts, section unique, pas de Rankine ni d'Eurocode 3 ; flambage d'ensemble non vérifié |
| Ajustements ISO 286 | Valeurs connues de l'ISO 286-2 (K7, N7, P7, M7, JS7, J7, js6, k6, h8, j6, f7, r6, p6, s6) | Colonnes a, b, cd, d, ef, fg, t, u, v, x, y, z, za, zb, zc non recoupées avec la norme |
| Frettage | Valeurs du classeur Excel de l'auteur (à 1e-12 près) | Arbre plein : contrainte prise à 2p (prudent) |
| Paliers lisses | Valeurs du classeur Excel de l'auteur | Limites P-V par famille de matériau à confirmer chez le fabricant |
| Clavette normalisée | Formules classiques | Tableau ISO 773 ressaisi à la main : à vérifier sur la norme |
| Roulements, Engrenages, Trains épicycloïdaux, Freins et embrayages, Dimensionnement moteur | Formules et exemples du cours de l'IUT de Bordeaux | Pas de catalogue de fabricant ; écarts relevés dans le cours (voir plus bas) |

## Choix qui changent les résultats

- **Marge de sécurité en % (site)** : sur toute page qui demande un coefficient de sécurité s, on peut saisir une marge
  à la place. La convention est marge = s − 1 : 30 % de marge donne s = 1,30, et l'on exige σ ≤ Re / 1,30. Le calcul
  garde s ; la marge n'est qu'une autre façon de le saisir et de le lire. Le choix est gardé dans le navigateur.

- **Aciers S185 à S355 : E = 210 GPa** (Eurocode 3) et G = E / (2(1 + ν)) = 80,77 GPa. L'application MATLAB d'origine
  utilisait 190 GPa : les flèches d'acier diffèrent d'environ 10 %. Aucun des cours de référence ne donne 190 GPa : le
  rapport de matériaux et la feuille de torsion donnent 210 GPa, et le TP de flexion trois points mesure 211 à 215 GPa
  sur l'acier.
- **Matériaux alignés sur les fiches (novembre 2026)** : EN-GJL-300 (α 7 → 11, E 100 → 110 GPa, ν 0,30 → 0,26),
  AlSi10Mg (α 26 → 21), FGS 400-15 (G 40 → 66 GPa), TA6V (E 116 → 110 GPa, α 9,0 → 8,6), laiton CuZn39Pb3
  (α 20,9 → 19,3), 42CrMo4 (α 12,0 → 11,1), inox 420 (α 11,0 → 10,5), PEEK (α 45 → 50), en µm/m/°C. Les écarts de
  moins de 5 % avec les fiches, et les minima garantis (7075, 6082, 2017, 316L) pris à la place des valeurs typiques,
  n'ont pas été modifiés. Les résultats thermiques de ces matériaux ont changé.
- **Fatigue** : la limite d'endurance estimée à 0,5·Rm ne vaut que pour l'acier (le cours de fatigue de Master donne
  environ 0,35·Rm à 10⁷ cycles pour un Al-Cu). La page propose maintenant de saisir σD, de régler Kf (1 ≤ Kf ≤ Kt) et
  d'appliquer Kf aussi à la contrainte moyenne ; par défaut le calcul est inchangé (Kf = Kt sur l'amplitude seulement,
  écart de 4 % côté non sûr sur l'annale de 2018). Gerber, Soderberg, Miner et la fatigue multiaxiale ne sont pas traités.
- **Frettage** : pour la contrainte équivalente d'un arbre plein, l'abaque du cours donne p et le classeur 2p ; le
  coefficient de sécurité garde 2p (prudent), la valeur du cours est affichée à côté. Pour la rugosité, le cours retire
  4(Ra arbre + Ra alésage) (6,4 et 12,8 µm), la norme 5 et 10 µm.
- **Conventions des pages Tenseurs et Hooke** : l'invariant I2 est de signe opposé à celui du cours de Master (mêmes
  contraintes principales) ; l'ordre des cisaillements de la matrice de Hooke est xx, yy, zz, yz, xz, xy contre 11, 22,
  33, 12, 13, 23 au cours.
- **Dossier de validation** : il prouve que le calcul est cohérent avec ses propres formules, pas que ces formules
  conviennent à votre cas. Pour Eurocode 3, la fatigue et Navier, les valeurs sont reprises du solveur.

## Écarts relevés dans le cours de roulements

Cours « Calcul sur les roulements » (IUT de Bordeaux), p. 18 et 19, relu page par page :

- Pour Fa/C0 = 0,064 le cours écrit Y = 1,59 (pente inversée) et e = 0,0265 pour 0,2657 ; l'interpolation donne Y = 1,66.
- Exemple du roulement 6405 : le cours prend Y = 1,31 (borne de la table) et annonce L10 = 185,3 M tours, 10 294 h ;
  avec C = 35,8 kN et P = 10,84 kN, (C/P)³ donne 36 M tours. 185,3 vaut exactement (61,8/10,84)³ : c'est le résultat d'un
  roulement de C = 61,8 kN. L'application interpole e et Y (P = 10 623 N, L10 = 38,3 M tours).
- Formule de l'ensemble iso-fiable (p. 12) : « 25000 » imprimé pour 15000 ; le résultat 23 811 h est juste.

## Ce qui n'a pas pu être comparé aux cours

Le « Guide du calcul mécanique » (scan de 257 pages sans texte) : flambage (λlim, Rankine), cisaillement de Jourawski et
abaques Kt ne sont donc pas recoupés avec lui. Les Recueils de bonnes pratiques en BE n° 08 et n° 18 (fichiers chiffrés).
Les formules dessinées des cours de frein, de Willis, du couple équivalent et la table des modules d'engrenages
(images non relues). Aucun cours du dossier ne traite des jauges, des ponts de Wheatstone et des rosettes. Les notes
GoodNotes ne sont pas lisibles.

## Différences entre le site et l'application de bureau

Les deux versions exécutent le même code de calcul : pour une même saisie, elles donnent les mêmes nombres (un test
le vérifie pour chaque page). Le site n'a pas : les dossiers PDF et Word fabriqués par le logiciel (sur le site, le dossier de validation est un
fichier HTML, avec un bouton qui l'ouvre prêt à imprimer en PDF), ni le dossier de validation de l'ossature 3D, des
ajustements, du frettage et des paliers lisses (le bureau non plus pour ces trois pages).
Sur le site, les échanges entre pages se font par des boutons (« Envoyer la section vers Poutres et Flambage », « Lire
les efforts de la poutre », « Prendre la section de la page Sections ») : rien n'est repris automatiquement, alors que
sur le bureau Cisaillement et Flexion suivent la page Sections à chaque calcul. Les ajouts de matériaux et de profilés faits sur le site restent dans ce navigateur : pour
les retrouver ailleurs, enregistrez-les dans un fichier (page Matériaux et profilés, onglet Mes ajouts).


## Diagramme des modes de ruine, bloc-notes et Excel de validation (site et bureau, depuis 1.4.0)

Le diagramme reprend les vérifications déjà faites par le calcul : il n'en ajoute aucune. Le coefficient de sécurité
obtenu est la limite du matériau divisée par la valeur calculée (Re/σ) ; le mode est admissible quand il atteint le
coefficient demandé. Pour l'ossature 3D, la contrainte de la pièce la plus sollicitée est comparée à Re sans
coefficient de sécurité (indicatif). Treillis, sections, Hooke, jauges, ajustements, trains d'engrenages et freins n'ont
pas de limite à comparer : ils gardent un simple message. La flèche d'une poutre n'est pas un critère du calcul
principal (seulement de la recherche du profilé le plus léger).

Dans l'Excel de validation, le calcul est refait par des formules Excel pour : traction (section constante),
cisaillement, torsion, flexion (axes principaux), flambage, frettage (effort, pression mini, couple, arbre),
roulements, engrènement, frein à disque, embrayage et moteur. Certaines valeurs sont reprises de MecaStruct et
signalées comme telles : e, X, Y et a1 des roulements, pressions du serrage normalisé, section et point le plus
sollicité en flexion, Re du matériau. Pour les poutres, treillis, ossatures, sections, tenseurs, Hooke, jauges,
ajustements, paliers lisses et trains, le solveur n'est pas refait dans Excel : le classeur donne les valeurs de
MecaStruct, et seuls le coefficient de sécurité, le taux et le verdict sont des formules. Pour ces pages, le dossier
de validation refait chaque grandeur à la main.

## Non disponible

Cannelures, goupilles en chape ou radiales dans un tube, denture hélicoïdale ou déportée, catalogues de fabricants.

Une erreur ? Signalez-la dans les [Issues](https://github.com/theo33-oss/MecaStruct/issues).

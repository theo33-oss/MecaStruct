# Limites connues

MecaStruct RdM Pro est un outil pédagogique et d'aide au pré-dimensionnement. Les résultats doivent être vérifiés
avant tout usage réel. Cette page dit ce qui a été vérifié, et contre quoi.

## État de vérification par page

| Page | Vérifié contre | Reste à vérifier |
|---|---|---|
| Poutres 2D | Application MATLAB d'origine (références « golden »), un cas refait à la main | Charge mobile absente des explications ; réactions surabondantes des poutres hyperstatiques non contrôlées |
| Ossature 3D | Équilibre global ΣF, ΣM | Pas de référence indépendante |
| Treillis, Sections, Sollicitations, Flambage, Tenseurs, Hooke et jauges | Application MATLAB d'origine (références « golden ») | Pas de recalcul indépendant à la main |
| Ajustements ISO 286 | Valeurs connues de l'ISO 286-2 (K7, N7, P7, M7, JS7, J7, js6, k6, h8, j6, f7, r6, p6, s6) | Colonnes a, b, cd, d, ef, fg, t, u, v, x, y, z, za, zb, zc non recoupées avec la norme |
| Frettage | Valeurs du classeur Excel de l'auteur (à 1e-12 près) | Arbre plein : contrainte prise à 2p (prudent) |
| Paliers lisses | Valeurs du classeur Excel de l'auteur | Limites P-V par famille de matériau à confirmer chez le fabricant |
| Clavette normalisée | Formules classiques | Tableau ISO 773 ressaisi à la main : à vérifier sur la norme |
| Roulements, Engrenages, Trains épicycloïdaux, Freins et embrayages, Dimensionnement moteur | Formules et exemples du cours de l'IUT de Bordeaux | Pas de catalogue de fabricant ; écarts relevés dans le cours (voir plus bas) |

## Choix qui changent les résultats

- **Aciers S185 à S355 : E = 210 GPa** (Eurocode 3) et G = E / (2(1 + ν)) = 80,77 GPa. L'application MATLAB d'origine
  utilisait 190 GPa : les flèches d'acier diffèrent d'environ 10 %.
- **Dossier de validation** : il prouve que le calcul est cohérent avec ses propres formules, pas que ces formules
  conviennent à votre cas. Pour Eurocode 3, la fatigue et Navier, les valeurs sont reprises du solveur.

## Écarts relevés dans le cours de roulements

- Pour Fa/C0 = 0,064 le cours écrit Y = 1,59 ; l'interpolation donne 1,66.
- Exemple du roulement : le cours annonce L10 = 185,3 M tours ; (C/P)³ avec C = 35,8 kN et P = 10,84 kN donne 36 M tours.

## Différences entre le site et l'application de bureau

Les deux versions exécutent le même code de calcul : pour une même saisie, elles donnent les mêmes nombres (un test
le vérifie pour chaque page). Le site n'a pas encore : les dossiers PDF et Word (le dossier HTML, pour les pages de
RdM, s'imprime en PDF depuis le navigateur), les abaques de concentration de contrainte, les transferts automatiques
entre pages (section vers Poutres, poutre vers Tenseurs), le dossier de validation des pages de machines et de
l'ossature 3D. Sur le site, les pages Cisaillement et Flexion utilisent la section de l'exemple ; le bureau reprend
celle de la page Sections. Les ajouts de matériaux et de profilés faits sur le site restent dans ce navigateur : pour
les retrouver ailleurs, enregistrez-les dans un fichier (page Matériaux et profilés, onglet Mes ajouts).

## Non disponible

Cannelures, goupilles en chape ou radiales dans un tube, denture hélicoïdale ou déportée, catalogues de fabricants.

Une erreur ? Signalez-la dans les [Issues](https://github.com/theo33-oss/MecaStruct/issues).

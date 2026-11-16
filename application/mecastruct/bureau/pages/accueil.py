"""Page d'Accueil : par où commencer, unités de saisie, conventions de signe, « Comment faire », limites et sources.

Port de buildHomeTab (MecaStruct_App.m) ; la visite guidée devient un encadré de texte.
"""

from mecastruct.bureau import dossier, state
from mecastruct.bureau.widgets import Page, Zone


class PageAccueil(Page):
    def rendre(self, z: Zone) -> None:
        state.init()
        z.titre("Bienvenue dans MecaStruct RdM Pro")
        z.texte(
            "MecaStruct RdM Pro est une application gratuite, sans compte, de calcul de Résistance des Matériaux et "
            "d'éléments de machines, pour apprendre et pré-dimensionner. **Calculs disponibles** : poutres "
            "(réactions, efforts, flèche), treillis, caractéristiques de sections, sollicitations simples (traction, "
            "cisaillement, torsion, flexion), flambage, tenseurs et critères de plasticité, loi de Hooke et jauges de "
            "déformation ; ajustements ISO 286, frettage, paliers lisses, roulements, engrenages, trains "
            "épicycloïdaux, freins et embrayages, dimensionnement moteur ; base de matériaux et de profilés, "
            "convertisseur d'unités. **Limites** : outil pédagogique, résultats à vérifier, aucune garantie ; il ne "
            "remplace ni une note de calcul certifiée ni les normes."
        )
        z.texte(
            "Chaque page est déjà remplie avec un exemple d'école : cliquez sur « Calculer » pour voir un résultat, "
            "puis changez les valeurs. Que voulez-vous faire ?"
        )
        z.lien("poutres", "📏 Calculer une poutre (réactions, diagrammes, flèche)")
        z.lien("sollicitations", "🔩 Dimensionner un arbre en torsion")
        z.lien("flambage", "📐 Vérifier une poutre au flambage")
        z.lien("convertisseur", "🔁 Convertir une unité (psi, kip, in…)")

        def comment(c: Zone) -> None:
            c.texte(
                "1. **Appuis** : le tableau Appuis donne leur position et leur type "
                "(la légende dessous dit ce que chacun bloque).\n"
                "2. **Chargement** : les tableaux Forces et Charges réparties donnent le chargement. "
                "Une force vers le bas est négative. « Charge rapide » aide à saisir une charge répartie.\n"
                "3. **Calcul** : lancez le calcul, regardez le schéma, puis les diagrammes de T et de Mf : "
                "le moment est maximal où T change de signe.\n"
                "4. **Rapport** : lisez le rapport. Sa première ligne est le verdict : "
                "la poutre résiste-t-elle, avec quelle marge ?\n"
                "5. **Flambage** : une poutre comprimée doit aussi être vérifiée au flambage (page Flambage)."
            )

        z.repliable("Comment faire : une poutre de A à Z (5 étapes)", ouvert=True, rendu=comment)

        z.sousTitre("Projet")
        dossier.project_bar(z)

        z.sousTitre("À retenir avant de saisir")
        z.texte(
            "**Unités de saisie** : sections en mm, longueurs de poutre en m, forces en kN, moments en kN·m, "
            "charges réparties en kN/m, E et G en GPa, contraintes en MPa."
        )
        z.texte(
            "**Signes** : une force vers le bas est négative (Fy < 0). N > 0 : traction. "
            "Mfz > 0 : fibres du haut comprimées, fibres du bas tendues. "
            "Torseur de cohésion : actions à droite de la coupe."
        )
        z.texte(
            "Un tableau (appuis, forces…) se remplit avec « Ajouter une ligne » ; "
            "« Supprimer la sélection » retire la ligne choisie. "
            "Le bloc « Formulaire rapide », en haut de chaque page de calcul, affiche la fiche de formules de la page."
        )

        z.repliable(
            "Limites connues de l'application",
            rendu=lambda c: c.texte(
                "- **Poutre hyperstatique avec Iyz ≠ 0** (section sans axes principaux, par exemple une cornière) : "
                "les réactions sont calculées plan par plan, le couplage y–z est ignoré. "
                "Saisir la section dans ses axes principaux (Iyz = 0). "
                "En isostatique, Iyz ≠ 0 est traité exactement.\n"
                "- **Dossier de validation, contrainte au point le plus sollicité** : non recalculée à la main "
                "pour une section dissymétrique ni pour Iyz ≠ 0 ; le dossier le dit.\n"
                "- **Normes** : seules les vérifications Eurocode 3 de la documentation sont normatives ; "
                "l'interaction N + M (annexe B) est à vérifier dans le texte de l'EN 1993-1-1.\n"
                "- **Formules** : dessinées par l'application, sans connexion Internet ; une syntaxe non reconnue "
                "reste écrite en LaTeX brut."
            ),
        )
        z.repliable(
            "Auteur et sources",
            rendu=lambda c: c.texte(
                "Application de **Théo Brun**, basée sur son cours de Résistance des Matériaux.\n\n"
                "- Cours de RDM de l'auteur : formules, conventions de signe, arbre de décision du flambage, "
                "matériaux, pressions de matage.\n"
                "- Cours de l'Université de Bordeaux (IUT GMP, Master Génie mécanique) : roulements, engrenages, "
                "trains épicycloïdaux, freins et embrayages, frettage, fatigue, milieux continus. La liste complète, "
                "avec auteurs et années, est dans la page **Références**.\n"
                "- Théorie classique de la RDM : Fanchon (*Guide du calcul en mécanique*), *Mémotech*, "
                "cours de RDM des IUT GMP "
                "(Navier, Huygens, Jourawski, Euler, Castigliano, Ménabréa, cercles de Mohr, Tresca, Von Mises, "
                "Hooke).\n"
                "- Pilkey, *Peterson's Stress Concentration Factors* : ajustements des abaques Kt.\n"
                "- Tables de profilés Eurocode 3 et fabricants : dimensions et caractéristiques des profilés."
            ),
        )
        z.legende(
            "Outil pédagogique et d'aide au pré-dimensionnement. Les résultats ne remplacent ni une note de calcul "
            "certifiée ni les normes en vigueur et doivent être vérifiés avant tout usage réel."
        )
        z.lien("apropos", "À propos")

"""Page d'Accueil : la même que sur le site (titre, deux façons de l'utiliser, une carte par famille), puis les repères.

Sous les cartes : « Comment faire », le projet, les unités et conventions de signe, les limites et les sources.
"""

from mecastruct.bureau import dossier, state
from mecastruct.bureau.widgets import Page, Zone
from mecastruct.services.pages_texte import FAMILLES, INTROS


class PageAccueil(Page):
    def rendre(self, z: Zone) -> None:
        state.init()
        z.titre("Calculs de résistance des matériaux et d'éléments de machines")
        z.intro(
            "Chaque calcul donne un verdict, un diagramme des modes de ruine avec les coefficients de sécurité, les "
            "formules remplies avec vos valeurs et la démarche pas à pas. Il s'exporte en dossier de validation, en "
            "bloc-notes ou en Excel à formules. Plus de 1 300 tests vérifient les calculs."
        )
        z.lien("ajustements", "Commencer par un ajustement ISO 286")
        z.lien("limites", "Ce qui est vérifié")

        z.sousTitre("Deux façons de l'utiliser")
        z.texte(
            "**Sur le bureau Windows** (vous y êtes) : démarrage immédiat, hors ligne, dossiers de validation PDF et "
            "Word. Vos saisies restent sur cet ordinateur.\n\n"
            "**Dans le navigateur** : aucune installation, toutes les pages, mêmes calculs. Le bouton « Version en "
            "ligne », en haut de la fenêtre, l'ouvre."
        )
        for famille, pages in self.fenetre.familles.items():
            z.sousTitre(famille)
            z.legende(FAMILLES.get(famille, ""))
            for ident, libelle in pages:
                if ident == "apropos":
                    continue  # sur le site, « À propos » est en pied de page
                z.lien(ident, libelle)
                if libelle in INTROS:
                    z.legende(INTROS[libelle])

        z.texte(
            "Chaque page est déjà remplie avec un exemple d'école : cliquez sur « Calculer » pour voir un résultat, "
            "puis changez les valeurs."
        )

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
                "avec établissements et années, est dans la page **Références**.\n"
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

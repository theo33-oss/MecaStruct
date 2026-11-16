"""Phrase sous le titre de chaque page : la même sur le site (docs/app.js, PAGES) et dans l'application de bureau."""

INTROS = {
    "Poutres": "Poutre 2D isostatique ou hyperstatique, ou ossature 3D : réactions, efforts, flèche, contraintes, Eurocode 3 (2D).",
    "Treillis": "Efforts dans les barres, déplacements des nœuds, contrainte et flambage des barres.",
    "Flambage": "Charge critique d'Euler, élancement, conditions aux limites.",
    "Sections": "Aire, centre de gravité, inerties et modules de sections simples, composées ou profilées.",
    "Sollicitations": "Traction, cisaillement (clavette, goupille), torsion, flexion.",
    "Tenseurs et critères": "Contraintes principales, cercle de Mohr, Von Mises et Tresca.",
    "Hooke et jauges": "Loi de Hooke généralisée et rosettes de jauges.",
    "Ajustements ISO 286": "Écarts, cotes limites, jeu ou serrage d'un ajustement.",
    "Frettage": "Serrage nécessaire, ajustement normalisé, contraintes, température de chauffe.",
    "Paliers lisses": "Pression, vitesse et produit PV face aux limites du matériau.",
    "Roulements": "Durée de vie, ensemble de roulements, règles de montage.",
    "Engrenages": "Engrènement et train d'engrenages.",
    "Trains épicycloïdaux": "Raison basique, vitesse de sortie et conditions de montage d'un train épicycloïdal.",
    "Freins et embrayages": "Couple de freinage d'un disque, synchronisation d'un embrayage.",
    "Dimensionnement moteur": "Couple thermique équivalent, couple de pointe, inertie ramenée.",
    "Matériaux et profilés": "Base de matériaux et de profilés normalisés.",
    "Convertisseur": "Conversion entre unités de toutes les grandeurs.",
    "Références": "Normes, cours et documents cités par l'application.",
    "Limites et vérifications": "Ce qui est vérifié, contre quoi, et ce qui ne l'est pas.",
}

# une phrase par famille du menu : la même que sur le site (docs/app.js, FAMILLES)
FAMILLES = {
    "Structures": "Une structure chargée : efforts, flèches, stabilité.",
    "Sections et contraintes": "Une section ou un état de contrainte en un point.",
    "Liaisons et guidages": "Choisir l'ajustement, vérifier le frettage, puis le guidage.",
    "Transmission": "La chaîne du moteur au récepteur.",
    "Données et aide": "Unités, matériaux, références et limites de l'outil.",
}

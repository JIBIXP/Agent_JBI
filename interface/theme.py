"""Thème visuel centralisé de l'interface JIBI — palette « Charbon & Jade ».

Nouvelle identité 2026 : fond charbon profond (jamais bleu nuit), accent
jade/turquoise, touches ambre pour les alertes. Aucun emoji n'est utilisé
comme icône : les boutons vectoriels sont dessinés sur Canvas par l'interface.
"""
from __future__ import annotations

FOND = "#0c0f0e"            # charbon légèrement vert, plus doux qu'un noir pur
FOND_RGB = (12, 15, 14)
PANNEAU = "#141a18"         # panneaux latéraux et cartes
PANNEAU_CLAIR = "#1d2623"   # survols et fonds alternés
CHAMP = "#1f2a26"           # champs de saisie
CHAMP_BORD = "#31463e"
BOUTON_CLAIR = "#e6ecea"
BORD = "#263229"            # séparateurs discrets
TEXTE = "#eef2f0"           # corps des messages : blanc cassé très lisible
TEXTE_PUR = "#ffffff"       # titres et emphases
GRIS = "#9aa8a2"            # informations secondaires, jamais plus sombres
ACCENT = "#2fd6a3"          # jade — couleur signature
ACCENT_CLAIR = "#7cf0cc"    # état « Prêt » et accents de statut
BLEU = "#5cc8e8"            # liens / information (cyan froid, plus secondaire)
VERT = "#7cf0cc"
ROUGE = "#ff8080"
ORANGE = "#ffc46b"          # alertes et avertissements

# Barre de saisie capitulaire : fond légèrement détaché du canvas,
# bordure discrète et placeholder lisible sans briller.
CAPSULE_FOND = "#161d1a"
CAPSULE_FOND_SURVOL = "#1d2724"
CAPSULE_BORD = "#2c3a34"
CAPSULE_TEXTE = "#e8efec"
CAPSULE_AIDE = "#8ba099"
CAPSULE_RAYON = 24
BARRE_ICONE = 36
BARRE_MARGE = 18
TRANSITION_MS = 150

POLICE = "Segoe UI"
POLICE_REPLI = "Arial"
POLICE_CODE = "Consolas"    # sorties système et blocs de commande uniquement
TAILLE_TITRE = 22
TAILLE_BASE = 13
TAILLE_PETIT = 11
TAILLE_CHAT = 14
TAILLE_CODE = 12

ESPACEMENT = 8
ESPACEMENT_GRAND = 16
RAYON_ARRONDI = 14
RAYON_ORBE = 100
FACTEUR_ORBE_PAROLE = 1.4
LISSAGE_ORBE = 0.12
HAUTEUR_LUMIERE_BAS = 46

COULEURS_ORBE = {
    #           (halo, cœur) — jade au repos, cyan à l'écoute,
    #           ambre à la réflexion, vert lumineux à la parole.
    "repos": ("#0d3a2e", "#2fd6a3"),
    "ecoute": ("#0a3d4a", "#5cc8e8"),
    "reflexion": ("#4a3614", "#ffc46b"),
    "parole": ("#0d4d33", "#7cf0cc"),
}
RYTHMES = {"repos": 1.1, "ecoute": 4.2, "reflexion": 6.5, "parole": 2.6}

"""Thème visuel centralisé de l'interface JIBI.

Palette sombre, accents néon et métriques communes au bureau et à la
console. Aucun emoji n'est utilisé comme icône : les boutons vectoriels sont
dessinés sur Canvas par l'interface.
"""
from __future__ import annotations

FOND = "#0a0d16"
FOND_RGB = (10, 13, 22)
PANNEAU = "#111827"
PANNEAU_CLAIR = "#1b2340"
CHAMP = "#202b45"
CHAMP_BORD = "#3a496b"
BOUTON_CLAIR = "#d9dced"
BORD = "#29345c"
TEXTE = "#f2f2f2"          # corps des messages : blanc cassé très lisible
TEXTE_PUR = "#ffffff"      # titres et emphases
GRIS = "#a0a0a0"           # informations secondaires, jamais plus sombres
ACCENT = "#8b6cff"
ACCENT_CLAIR = "#b39cff"   # état « Prêt » et accents de statut
BLEU = "#54b9ff"
VERT = "#63e6b5"
ROUGE = "#ff7f9e"
ORANGE = "#ffbe72"

# Barre de saisie capitulaire : fond légèrement détaché du canvas,
# bordure discrète et placeholder lisible sans brilliant.
CAPSULE_FOND = "#182238"
CAPSULE_FOND_SURVOL = "#202d49"
CAPSULE_BORD = "#354665"
CAPSULE_TEXTE = "#ececec"
CAPSULE_AIDE = "#929db4"
CAPSULE_RAYON = 24
BARRE_ICONE = 36
BARRE_MARGE = 18
TRANSITION_MS = 150

POLICE = "Segoe UI"
POLICE_REPLI = "Arial"
POLICE_CODE = "Consolas"   # sorties système et blocs de commande uniquement
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
    "repos": ("#1c3a72", "#7db2ff"),
    "ecoute": ("#123f70", "#54b9ff"),
    "reflexion": ("#3b2470", "#9b7bff"),
    "parole": ("#0d4d33", "#63e6b5"),
}
RYTHMES = {"repos": 1.1, "ecoute": 4.2, "reflexion": 6.5, "parole": 2.6}

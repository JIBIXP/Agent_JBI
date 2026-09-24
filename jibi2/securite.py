"""Sécurité de JIBI 2.

Principe : les outils sont étiquetés par risque (faible / moyen / élevé).
`CONFIRMER_RISQUES=1` (défaut) impose une confirmation humaine avant tout
outil à risque ÉLEVÉ (commande système, extinction du PC...). Si
`JIBI_MODIFICATION_AUTO=1` active le mode de modification et de restauration
du noyau, mais `JIBI_AUTONOMIE_NOYAU` reste par défaut à 0 : une
modification du noyau demande toujours une confirmation explicite. Les
écritures restent confinées au projet, les tests et le retour arrière sont
obligatoires. Les écritures utilisateur restent confinées dans
donnees/fichiers/ (voir outils/fichiers.py).
"""
from __future__ import annotations

from collections.abc import Callable

from . import config

Confirmer = Callable[[str, str], bool]

# Le noyau peut être autorisé automatiquement seulement si
# JIBI_AUTONOMIE_NOYAU=1 est explicitement choisi. Par défaut, ces deux
# actions restent soumises à la confirmation humaine.
OUTILS_MODIFICATION_AUTO = frozenset({"modifier_noyau", "restaurer_noyau"})


class Garde:
    def __init__(self, confirmer: Confirmer | None = None) -> None:
        # confirmer(titre, detail) -> bool ; remplacable par chaque interface
        # (console = input, fenêtre = boîte de dialogue).
        self.confirmer: Confirmer = confirmer or (lambda titre, detail: True)

    def autoriser(self, nom_outil: str, risque: str, detail: str) -> bool:
        # Si l'auto-amélioration du noyau est activée, autoriser les modifications de code.
        if (risque == "eleve"
                and nom_outil in OUTILS_MODIFICATION_AUTO
                and config.valeur_bool("JIBI_MODIFICATION_AUTO")
                and config.valeur_bool("JIBI_AUTONOMIE_NOYAU")):
            return True
        # Si CONFIRMER_DEPLACEMENT=0, les déplacements/copies de fichiers
        # ne demandent pas de confirmation.
        if (nom_outil in ("deplacer_document", "copier_document")
                and not config.valeur_bool("CONFIRMER_DEPLACEMENT")):
            return True
        if risque == "eleve" and config.valeur_bool("CONFIRMER_RISQUES"):
            return bool(self.confirmer(nom_outil, detail))
        return True

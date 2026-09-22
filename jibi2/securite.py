"""Sécurité de JIBI 2.

Principe : les outils sont étiquetés par risque (faible / moyen / élevé).
`CONFIRMER_RISQUES=1` (défaut) impose une confirmation humaine avant tout
outil à risque ÉLEVÉ (commande système, extinction du PC...). Les écritures
de fichiers restent confinées dans donnees/fichiers/ (voir outils/fichiers.py).
"""
from __future__ import annotations

from collections.abc import Callable

from . import config

Confirmer = Callable[[str, str], bool]


class Garde:
    def __init__(self, confirmer: Confirmer | None = None) -> None:
        # confirmer(titre, detail) -> bool ; remplacable par chaque interface
        # (console = input, fenêtre = boîte de dialogue).
        self.confirmer: Confirmer = confirmer or (lambda titre, detail: True)

    def autoriser(self, nom_outil: str, risque: str, detail: str) -> bool:
        if risque == "eleve" and config.valeur_bool("CONFIRMER_RISQUES"):
            return bool(self.confirmer(nom_outil, detail))
        return True

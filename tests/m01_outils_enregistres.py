# -*- coding: utf-8 -*-
"""Section 1 — outils enregistrés — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 1. Outils enregistrés
verif("au moins 30 outils enregistrés", len(OUTILS) >= 30, f"({len(OUTILS)})")
categories = {o.categorie for o in OUTILS.values()}
verif("au moins 8 catégories", len(categories) >= 8, str(sorted(categories)))
verif("outils à risque élevé bien étiquetés",
      {"executer_commande", "eteindre_pc"} <= {o.nom for o in OUTILS.values() if o.risque == "eleve"})

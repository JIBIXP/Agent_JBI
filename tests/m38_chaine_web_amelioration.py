# -*- coding: utf-8 -*-
"""Section 33 — chaîne web→amélioration — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 33. Chaîne « apprendre sur le web → s'améliorer » complète et enseignée
import outils as _module_outils33  # noqa: E402
from jibi2.assistant import SYSTEME as _SYSTEME33  # noqa: E402

verif("web→amélioration : comportement enseigné au modèle",
      "t'instruire sur le WEB" in _SYSTEME33
      and "proposer_nouvel_outil" in _SYSTEME33)
verif("web→amélioration : toute la chaîne d'outils enregistrée",
      {"rechercher_web", "lire_page_web", "proposer_nouvel_outil",
       "tester_proposition", "activer_proposition", "lire_code_noyau",
       "modifier_noyau", "ameliorer_autonomement", "ouvrir_compte_chrome",
        "chercher_dans_chrome", "visiter_site", "creer_excel", "analyser_excel",
        "analyser_documents", "localisation_approchee", "rechercher_pres",
        "rechercher_images_web", "images_page_web", "telecharger_image_web",
        "lire_site_browser", "naviguer_browser_use", "chercher_video",
        "chercher_music", "chercher_site", "statut_browser_use"}
      <= set(_module_outils33.lister_noms()))

from jibi2 import autonomie as _autonomie33  # noqa: E402

verif("autonomie : horaire HH:MM validé", _autonomie33._normaliser_heure("4:05") == "04:05")
try:
    _autonomie33._normaliser_heure("25:99")
    _horaire_invalide = False
except ValueError:
    _horaire_invalide = True
verif("autonomie : horaire invalide refusé", _horaire_invalide)

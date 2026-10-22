# -*- coding: utf-8 -*-
"""Section 14 — workflows programmés — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 14. Workflows programmés (horaire)
from jibi2 import planificateur  # noqa: E402

workflows.creer("routine_horo", "test horaire",
                _json.dumps([{"outil": "heure_actuelle", "parametres": {}}]), "07:41")
programmes = planificateur.workflows_programmes()
verif("workflow programmé listé", ("routine_horo", "07:41") in programmes, str(programmes))
retour = workflows.creer("routine_horo2", "x",
                         _json.dumps([{"outil": "heure_actuelle", "parametres": {}}]), "7h99")
verif("horaire invalide refusé", "invalide" in retour, retour)
workflows.supprimer("routine_horo")

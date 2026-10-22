# -*- coding: utf-8 -*-
"""Section 10 — workflows (routines) — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 10. Workflows (routines)
from outils import regler_services, workflows  # noqa: E402

regler_services(garde=Garde(lambda n, d: False))
retour = workflows.creer("test_wf", "essai", "pas du json")
verif("workflow JSON invalide refusé", "JSON" in retour, retour)
retour = workflows.creer("test_wf", "essai", _json.dumps([{"outil": "outil_inconnu"}]))
verif("workflow outil inconnu refusé", "n'existe pas" in retour, retour)
retour = workflows.creer("test_wf", "essai",
                         _json.dumps([{"outil": "calculer",
                                       "parametres": {"expression": "6*7"}},
                                      {"message": "bonjour"}]))
verif("workflow créé", "créé" in retour, retour)
_rwf = executer("creer_workflow", {
    "nom": "test_wf_horaire", "description": "essai horaire",
    "etapes": _json.dumps([{"outil": "heure_actuelle", "parametres": {}}]),
    "horaire": "07:42"}, Garde(lambda n, d: False))
verif("outil workflow transmet l'horaire", _rwf["ok"] and "créé" in _rwf["texte"], _rwf["texte"])
workflows.supprimer("test_wf_horaire")
retour = workflows.executer("test_wf")
verif("workflow exécuté (outil ok, message passé)", "1 ok" in retour and "42" in retour
      and "passée" in retour, retour)
verif("liste des workflows", "test_wf" in workflows.lister())
verif("workflow supprimé", "supprimé" in workflows.supprimer("test_wf"))

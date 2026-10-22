# -*- coding: utf-8 -*-
"""Section 29 — design + autonomie du noyau — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 29. Autonomie du code : outils sûrs et noyau modifiables sans confirmation
from interface.panneau import _page_html  # noqa: E402
from outils.design import personnaliser_design, style_panneau  # noqa: E402

verif("design : couleur appliquée",
      "Appliqué" in personnaliser_design("panneau.accent", "#12aa55"))
verif("design : injecté dans la page du panneau", "#12aa55" in _page_html().decode())
verif("design : valeur invalide refusée",
      "hex" in personnaliser_design("panneau.accent", "rouge"))
verif("design : clé inconnue refusée",
      "inconnu" in personnaliser_design("orbe.nuit", "#111111, #222222, #333333"))
verif("design : reset", "origine" in personnaliser_design("reset", "") and style_panneau() == "")

from jibi2 import evolution as _evo29  # noqa: E402
from jibi2.labo import tester_proposition as _tester29  # noqa: E402

_CODE29 = '''"""Outil posé par JIBI lui-même (test autonomie)."""
from outils import outil


@outil("outil_auto29", "Outil de test posé par JIBI seul.",
       {"texte": {"type": "str", "obligatoire": True,
                  "description": "texte à renvoyer"}},
       categorie="calcul", risque="faible", exemple="")
def outil_auto29(texte: str) -> str:
    return "écho29:" + texte
'''
_evo29.proposer_outil("outil_auto29", _CODE29)
tester_ok = _tester29("outil_auto29")
from jibi2.securite import Garde as _Garde29  # noqa: E402
from outils import executer as _exec29  # noqa: E402

_g29 = _Garde29()
_g29.confirmer = lambda nom, detail: False      # par défaut : TOUT refuser
_activation = _exec29("activer_proposition", {"nom": "outil_auto29"}, _g29)
verif("autonomie : JIBI active sa proposition seul",
      _activation["ok"] and "outil_auto29" in _activation["texte"])
_echo = _exec29("outil_auto29", {"texte": "ça marche"}, _g29)
verif("autonomie : l'outil auto-activé fonctionne", _echo["ok"] and "écho29" in _echo["texte"])
_evo29.retirer("outil_auto29")

# noyau : l'auto-amélioration peut proposer, mais l'écriture reste confirmée
verif("noyau : confirmation humaine obligatoire",
      _g29.autoriser("modifier_noyau", "eleve", "test") is False)
_g29.confirmer = lambda nom, detail: True      # les tests simulent ton accord
_lire_noyau = _exec29("lire_code_noyau", {"fichier": "VERSION", "lignes": 2}, _g29)
verif("noyau : lecture d'un fichier autorisée", _lire_noyau["ok"] and "ADD" in _lire_noyau["texte"])
# Le contenu invalide est refusé avant toute écriture.
_casse = _exec29("modifier_noyau", {
    "fichier": "tests/verification.py", "contenu": "def casse(:\n", "raison": "test syntaxe",
    "verifier": False}, _g29)
verif("noyau : syntaxe cassée refusée avant écriture",
      not _casse["ok"] and "SYNTAXE" in _casse["texte"])
_paire = _exec29("modifier_noyau", {
    "fichier": "VERSION", "avant": "ADD 31", "raison": "test paire"}, _g29)
verif("noyau : paire avant/après incomplète refusée",
      not _paire["ok"] and "obligatoire" in _paire["texte"])
_verrou = _exec29("modifier_noyau", {"fichier": ".env", "contenu": "x",
                                      "raison": "test protection", "verifier": False}, _g29)
_travers = _exec29("modifier_noyau", {"fichier": "../.env", "contenu": "x",
                                      "raison": "test protection", "verifier": False}, _g29)
verif("noyau : .env et traversée interdits",
      "jamais modifiable" in _verrou["texte"] and "refusé" in _travers["texte"])

# -*- coding: utf-8 -*-
"""Section 6 — protocole JSON du cerveau — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 6. Protocole JSON du cerveau
verif("JSON simple", _extraire_json('{"reponse": "coucou"}') == {"reponse": "coucou"})
verif("JSON avec balises code", _extraire_json('```json\n{"outil": "calculer"}\n```') == {"outil": "calculer"})
verif("JSON avec du texte autour", _extraire_json('Voici : {"reponse": "ok"} voilà.') == {"reponse": "ok"})
verif("non-JSON → None", _extraire_json("je ne sais pas") is None)
verif("nettoyer_think", llm.nettoyer_think("<think>hm</think>bonjour") == "bonjour")

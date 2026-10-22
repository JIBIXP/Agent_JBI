# -*- coding: utf-8 -*-
"""Section 28 — version et mises à jour — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 28. Version & mises à jour (code improved, installation complete guarded)
from outils.systeme import _version_locale, verifier_mise_a_jour  # noqa: E402

_ver = _version_locale()
verif("fichier VERSION lisible", _ver != "inconnue" and "ADD" in _ver, _ver)
_message = verifier_mise_a_jour()
verif("mise à jour : position honnête annoncée",
      _ver in _message and "améliorer son code source" in _message
      and "installation complète" in _message)
verif("mise à jour : procédure de sauvegarde rappelée",
      "donnees/" in _message and "modeles/voix" in _message)

# -*- coding: utf-8 -*-
"""Section 26 — web : SSRF bloqué — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 26. Web :SSRF bloqué pour l'apprentissage autonome
from outils.web import _valider_url_publique  # noqa: E402

_verrou_web, _raison_web = _valider_url_publique("http://127.0.0.1/")
verif("web : loopback refusé", _verrou_web is None and "privé" in _raison_web, _raison_web)

# -*- coding: utf-8 -*-
"""Section 27bis — voie rapide — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 27. Voie rapide : réponses instantanées sans passer par le modèle
import time as _time27  # noqa: E402

import outils.jeux as _jeux27  # noqa: E402
from jibi2.assistant import _voie_rapide  # noqa: E402
from jibi2.securite import Garde as _Garde27  # noqa: E402

_garde27 = _Garde27()
_voie_rapide("pile ou face", _garde27)          # échauffement (premiers imports)
_t0 = _time27.perf_counter()
_r = _voie_rapide("Quelle heure est-il ?", _garde27)
_duree = _time27.perf_counter() - _t0
verif("voie rapide : heure instantanée", _r is not None and _r["ok"] and _duree < 0.5,
      f"{_duree * 1000:.0f} ms")
verif("voie rapide : jour capté", _voie_rapide("quel jour est-on ?", _garde27) is not None)
_de = _voie_rapide("lance un dé à 20 faces", _garde27)
verif("voie rapide : dé à 20 faces", _de is not None and "20 faces" in _de["reponse"])
_pf = _voie_rapide("pile ou face", _garde27)
verif("voie rapide : pile ou face", _pf is not None and ("Pile" in _pf["reponse"] or "Face" in _pf["reponse"]))
verif("voie rapide : chifoumi",
      _voie_rapide("on joue à pierre feuille ciseaux, je joue feuille", _garde27) is not None)
_jeux27._MYSTERE["cible"] = 50
_jeux27._MYSTERE["essais"] = 0
_m = _voie_rapide("c'est 50 ?", _garde27)
verif("voie rapide : essai du nombre mystère", _m is not None and "Bravo" in _m["reponse"])
verif("voie rapide : calcul direct",
      "408" in (_voie_rapide("calcule 12*34", _garde27)["reponse"]))
verif("voie rapide : le passé passe par le modèle",
      _voie_rapide("quelle heure était-il hier ?", _garde27) is None)
verif("voie rapide : pas de faux positif",
      _voie_rapide("mets une alarme dans une heure", _garde27) is None
      and _voie_rapide("rappelle-moi dans 2 minutes", _garde27) is None)

# -*- coding: utf-8 -*-
"""Suite des jeux + souris (après §35) — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

_de = lancer_un_de()
_faces = int(_de.split("faces donne")[1].strip().rstrip("."))
verif("jeu : dé dans les bornes", 1 <= _faces <= 6, _de)
verif("jeu : pile ou face", pile_ou_face().split()[1].rstrip("!") in ("Pile", "Face"))
_verdicts = [pierre_feuille_ciseaux("pierre") for _ in range(3)]   # 3 essais : test relançable
verif("jeu : chifoumi répond un verdict",
      any(m in _v for _v in _verdicts for m in ("égalité", "gagnes", "gagne")),
      _verdicts[0][:40])
nombre_mystere("commencer")
module_jeux_etat = nombre_mystere
import outils.jeux as _module_jeux  # noqa: E402

_module_jeux._MYSTERE["cible"] = 50
_module_jeux._MYSTERE["essais"] = 0
verif("jeu : mystère trop grand", "PLUS PETIT" in nombre_mystere("deviner", 60))
verif("jeu : mystère gagné", "Bravo" in nombre_mystere("deviner", 50)
      and not _module_jeux._MYSTERE)

verif("souris : réponse adaptée à la plateforme",
      (deplacer_souris(50, 50).startswith("Curseur")
       and cliquer_souris().startswith("Clic")) if os.name == "nt"
      else ("Windows" in deplacer_souris(50, 50) and "Windows" in cliquer_souris()))
verif("souris : pourcentages bornés", _bornes(-5) == 0 and _bornes(150) == 100)

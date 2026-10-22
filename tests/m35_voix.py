# -*- coding: utf-8 -*-
"""Section 30 — voix (catalogue Piper, phrases en flux) — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 30. Voix au choix (dont masculine) + parole au fil de l'eau
from audio import parole as _parole30  # noqa: E402
from outils.voix import _ecrire_env, changer_voix  # noqa: E402

verif("voix : catalogue avec voix masculine",
      "tom" in _parole30.CATALOGUE_VOIX
      and _parole30.CATALOGUE_VOIX["tom"]["sexe"] == "homme")
_onnx, _json = _parole30.url_modele("tom")
verif("voix : URL officielle Piper", _onnx.endswith("fr_FR-tom-medium.onnx")
      and "rhasspy/piper-voices" in _onnx)
_liste = changer_voix("")
verif("voix : listage avec sexe", "tom (homme" in _liste and "siwis (femme" in _liste)
verif("voix : nom inconnu refusé", "inconnue" in changer_voix("skynet"))
verif("voix : découpage en phrases",
      _parole30.extraire_phrases("Salut ! Je parle") == (["Salut !"], "Je parle"))
verif("voix : phrase inachevée gardée en tampon",
      _parole30.extraire_phrases("une phrase sans point") == ([], "une phrase sans point"))

_dit30: list[str] = []
_orig30 = _parole30.parler
_parole30.parler = lambda t, attendre=False: _dit30.append(t) or True
try:
    _lec = _parole30.LecteurPhrases()
    _lec.alimenter("Bonjour ! Je parle")
    _lec.alimenter(" dès que la phrase est prête.")
    _lec.terminer()
    _lec.attendre()
    verif("voix : phrases dites au fil de l'eau, dans l'ordre",
          _dit30 == ["Bonjour !", "Je parle dès que la phrase est prête."], str(_dit30))
    _dit30.clear()
    _lec2 = _parole30.LecteurPhrases()
    _lec2.alimenter("Une phrase complète. Le reste ne sera jamais dit.")
    _lec2.couper()
    _lec2.attendre()
    verif("voix : couper stoppe la file", _dit30 == ["Une phrase complète."], str(_dit30))
finally:
    _parole30.parler = _orig30

# le .env peut ne pas exister sur une installation fraîche (CI) : on repart
# d'un tampon neutre à l'identique du répertoire réel, retiré à la fin.
_env_absent = not Path(".env").exists()
if _env_absent:
    Path(".env").write_text("PIPER_MODELE=\n", encoding="utf-8")

_env_avant = (Path(".env").read_text(encoding="utf-8"), Path(".env").stat().st_size)
_ecrire_env("PIPER_MODELE", "essai")
_ecrire_env("PIPER_MODELE", "")
_apres = Path(".env").read_text(encoding="utf-8")
verif("voix : .env réécrit proprement (rien de perdu)",
      _apres == _env_avant[0] and Path(".env").stat().st_size == _env_avant[1])
if _env_absent:
    Path(".env").unlink(missing_ok=True)   # CI sans .env : tampon retiré

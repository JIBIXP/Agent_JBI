# -*- coding: utf-8 -*-
"""Section 32 — bench & editeur .env du docteur — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 32. Bench & adoption de modèle (l'éditeur .env du docteur)
from docteur import _ecrire_env  # noqa: E402

# le .env peut ne pas exister sur une installation fraîche (CI) : tampon
# neutre avec la ligne de référence, retiré à la fin — rien d'autre change.
_env_absent = not Path(".env").exists()
if _env_absent:
    Path(".env").write_text("JIBI_HISTOIRE=6\n", encoding="utf-8")

_avant32 = Path(".env").read_text(encoding="utf-8")
try:
    _ecrire_env("JIBI_TEST_BENCH", "v1")
    _ecrire_env("JIBI_TEST_BENCH", "v2")
    _entre = Path(".env").read_text(encoding="utf-8")
    verif("docteur : .env édité proprement (1 ligne, rien de perdu)",
          "JIBI_TEST_BENCH=v2" in _entre and _entre.count("JIBI_TEST_BENCH") == 1
          and "JIBI_HISTOIRE=6" in _entre)
finally:
    if _env_absent:
        Path(".env").unlink(missing_ok=True)
    else:
        Path(".env").write_text(_avant32, encoding="utf-8")
verif("docteur : .env restauré à l'identique",
      Path(".env").exists() is not _env_absent
      and (not Path(".env").exists()
           or Path(".env").read_text(encoding="utf-8") == _avant32))
verif("docteur : bench importable", callable(_ecrire_env))

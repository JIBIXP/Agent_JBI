# -*- coding: utf-8 -*-
"""Section 31 — vitesse CPU (plafonds, historique) — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# pont : récupère l'assistant de test publié par m09 (section 7)
assistant = _moteur.assistant

# 31. Vitesse CPU : plafonds de génération + historique compressé (prefill)
from docteur import bench_vitesse  # noqa: E402, F401  (importable sans Ollama)
from jibi2 import llm as module_llm  # noqa: E402

_orig_valeur = module_llm.config.valeur
module_llm.config.valeur = lambda cle, defaut="": {
    "JIBI_LLM_MAX": "77", "JIBI_LLM_CTX": "2048"}.get(cle, defaut)
try:
    verif("llm : plafond et contexte lus du réglage",
          module_llm._plafond() == 77 and module_llm._contexte() == 2048)
finally:
    module_llm.config.valeur = _orig_valeur
verif("llm : défauts bornés", module_llm._plafond() == 600 and module_llm._contexte() == 4096)
_corps = module_llm.ClientLLM(url="http://127.0.0.1:1")._corps(
    [{"role": "user", "content": "x"}], 0.4, stream=False)
verif("llm : requête plafonnée (num_predict, num_ctx, keep_alive)",
      _corps["options"]["num_predict"] == 600 and _corps["options"]["num_ctx"] == 4096
      and "keep_alive" in _corps)

_grosse = "[Résultat de l'outil lire_page_web] " + "page " * 500
assistant.histoire = [
    {"role": "user", "content": "résume la page"},
    {"role": "user", "content": _grosse},
    {"role": "assistant", "content": "Résumé."},
    {"role": "user", "content": "et celle-ci ?"},
    {"role": "user", "content": _grosse},
    {"role": "assistant", "content": "Résumé 2."},
    {"role": "user", "content": "merci"},
]
_messages31 = assistant._messages()
vieux = [m for m in _messages31[1:-2] if m["content"].startswith("[Résultat")]
verif("vitesse : vieux résultats d'outils compressés",
      all(len(m["content"]) <= 230 for m in vieux) and len(vieux) >= 1)
verif("vitesse : /no_think en fin de prompt système",
      _messages31[0]["content"].rstrip().endswith("/no_think"))
assistant.histoire = []
assistant._ajouter("user", "x" * 4000)
verif("vitesse : aucun message d'historique > 1 500 car.",
      all(len(m["content"]) <= 1500 for m in assistant.histoire))
assistant.histoire = []

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

# 31bis. Cerveau distant : FERMÉ par défaut (règle n° 1), Anthropic en stdlib
# (clé, entêtes, extraction du message « system », corps, flux SSE, erreurs).
dict_cloud: dict[str, str] = {}
import urllib.error  # noqa: E402
_orig_valeur_cloud = module_llm.config.valeur
module_llm.config.valeur = lambda cle, defaut="": dict_cloud.get(cle, defaut)
try:
    verif("cloud : désactivé par défaut (aucune donnée vers un serveur)",
          module_llm.fabrique_cloud() is None and module_llm.cloud_actif() is False)
    # Avec une clé mais sans JIBI_CLOUD=1 : la porte reste close.
    dict_cloud["ANTHROPIC_API_KEY"] = "cle-essai"
    verif("cloud : clé seule ne suffit pas, JIBI_CLOUD=1 requis",
          module_llm.fabrique_cloud() is None)
    dict_cloud["JIBI_CLOUD"] = "1"
    dict_cloud["JIBI_CLOUD_MARQUE"] = "anthropic"
    dict_cloud["JIBI_CLOUD_MODEL_ANTHROPIC"] = "claude-essai"
    dict_cloud["JIBI_CLOUD_MAX"] = "50"
    _anthro = module_llm.fabrique_cloud()
    verif("cloud : JIBI_CLOUD=1 + marque anthropic → ClientAnthropic",
          isinstance(_anthro, module_llm.ClientAnthropic) and module_llm.cloud_actif())
    _corps_a = _anthro._corps(
        [{"role": "system", "content": "tu es JIBI /no_think"},
         {"role": "user", "content": "bonjour"},
         {"role": "assistant", "content": "salut"},
         {"role": "user", "content": "encore"}], 0.4, stream=False)
    verif("anthropic : message système hors de la liste",
          _corps_a["system"] == "tu es JIBI /no_think"
          and len(_corps_a["messages"]) == 3
          and all(m["role"] in ("user", "assistant") for m in _corps_a["messages"]))
    verif("anthropic : max_tokens obligatoire, modèle lu du réglage",
          _corps_a["max_tokens"] == 50 and _corps_a["model"] == "claude-essai"
          and _corps_a["stream"] is False)
    _entetes_a = _anthro._entetes()
    verif("anthropic : entêtes x-api-key + anthropic-version",
          _entetes_a.get("x-api-key") == "cle-essai"
          and _entetes_a.get("anthropic-version") == module_llm.ClientAnthropic.VERSION)
    _requete_a = _anthro._requete({"model": "x"})
    verif("anthropic : requête POST URL_API, corps JSON",
          _requete_a.full_url == module_llm.ClientAnthropic.URL_API
          and _requete_a.get_method() == "POST"
          and b'"model"' in _requete_a.data)
    _faux_flux = [b'event: content_block_delta\r\n',
                  b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"salut"}}\r\n\r\n',
                  b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":" !"}}\r\n\r\n',
                  b'data: {"type":"message_stop"}\r\n\r\n']
    verif("anthropic : flux SSE lu au fil de l'eau (deltas + stop)",
          _anthro._lire_flux_sse(_faux_flux, None) == "salut !")
    try:
        _anthro._lever_erreur_http(urllib.error.HTTPError(
            module_llm.ClientAnthropic.URL_API, 401, "unauthorized", {}, None))
        verif("anthropic : 401 levé en français", False)
    except module_llm.ErreurLLM as e:
        verif("anthropic : 401 levé en français",
              "ANTHROPIC_API_KEY" in str(e) and "invalide" in str(e))
    # Repli OpenRouter : marque par défaut, clé dédiée.
    dict_cloud["JIBI_CLOUD_MARQUE"] = "openrouter"
    dict_cloud["OPENROUTER_API_KEY"] = "cle-or"
    _or = module_llm.fabrique_cloud()
    verif("cloud : marque openrouter (défaut) reste disponible",
          isinstance(_or, module_llm.ClientCloud))
    dict_cloud["JIBI_CLOUD_MARQUE"] = "anthropic"
    dict_cloud["ANTHROPIC_API_KEY"] = ""
    verif("cloud : marque anthropic sans clé → fermé proprement",
          module_llm.fabrique_cloud() is None and module_llm.cloud_actif() is False)
finally:
    module_llm.config.valeur = _orig_valeur_cloud

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

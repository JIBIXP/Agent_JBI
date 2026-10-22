# -*- coding: utf-8 -*-
"""Section 7 — assistant : repli local sans Ollama — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 7. Assistant : repli local sans Ollama
class ClientMort:
    def disponible(self): return False
    def discuter(self, m, temperature=0.4): raise llm.ErreurLLM("hors ligne")
bd2 = memoire.Memoire(Path(tempfile.gettempdir()) / "jibi_test_memoire2.db")
assistant = Assistant(bd2, Garde(lambda n, d: False))
assistant.client = ClientMort()
rep = assistant.repondre("quelle heure est-il ?")
verif("repli local heure", rep["ok"] and "Il est" in rep["reponse"], rep["reponse"])
rep = assistant.repondre("calcule 6*7")
verif("repli local calcul", "42" in rep["reponse"], rep["reponse"])
rep = assistant.repondre("explique-moi la vie")
verif("repli local message d'aide", not rep["ok"] and "Ollama" in rep["reponse"])

# pont : l'assistant de test est réutilisé par m14 (section 12)
# et m36 (section 31)
_moteur.assistant = assistant

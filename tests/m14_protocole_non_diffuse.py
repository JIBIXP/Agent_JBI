# -*- coding: utf-8 -*-
"""Section 12 — le JSON de protocole jamais diffusé — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# pont : récupère l'assistant de test publié par m09 (section 7)
assistant = _moteur.assistant

# 12. Le JSON de protocole ne doit jamais être diffusé à l'affichage
class ClientFluxJSON:
    def disponible(self):
        return True

    def discuter(self, messages, temperature=0.4):
        return '{"reponse": "texte final"}'

    def discuter_stream(self, messages, temperature=0.4, on_chunk=None):
        for morceau in ('{"re', 'ponse"', ': "voil\u00e0"}'):
            if on_chunk:
                on_chunk(morceau)
        return '{"reponse": "voil\u00e0"}'

assistant.client = ClientFluxJSON()
fuites: list[str] = []
rep = assistant.repondre("coucou", on_chunk=fuites.append)
verif("JSON de protocole tu (pas de fuite dans le flux)", fuites == [] and rep["reponse"] == "voilà",
      repr((fuites, rep["reponse"])))

class ClientFluxTexte:
    """1er appel : texte brut (hors protocole) → relance ; 2e : JSON muet."""

    def __init__(self):
        self.appel = 0

    def disponible(self):
        return True

    def discuter(self, messages, temperature=0.4):
        return '{"reponse": "bien reçu !"}'

    def discuter_stream(self, messages, temperature=0.4, on_chunk=None):
        self.appel += 1
        morceaux = ("Réponse ", "finale ", "claire.") if self.appel == 1 \
            else ('{"reponse": "bien reçu !"}',)
        for morceau in morceaux:
            if on_chunk:
                on_chunk(morceau)
        return "".join(morceaux)

assistant.client = ClientFluxTexte()
fuites.clear()
rep = assistant.repondre("coucou", on_chunk=fuites.append)
verif("texte diffusé au fil de l'eau, relance muette",
      "".join(fuites) == "Réponse finale claire." and rep["reponse"] == "bien reçu !",
      repr((fuites, rep["reponse"])))

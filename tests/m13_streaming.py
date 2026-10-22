# -*- coding: utf-8 -*-
"""Section 11 — streaming sur un faux serveur Ollama — extrait verbatim de l'ancien tests/verification.py."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# 11. Streaming : assemblage + filtre <think> sur un faux serveur Ollama
import threading as _threading  # noqa: E402
from http.server import BaseHTTPRequestHandler as _H  # noqa: E402
from http.server import HTTPServer as _Srv

SCENARIOS = [[
    {"message": {"content": "Bon"}},
    {"message": {"content": "jour"}},
    {"message": {"content": " le monde"}, "done": True},
], [
    {"message": {"content": "<think>"}},
    {"message": {"content": "réflexion secrète"}},
    {"message": {"content": "</think>Salut !"}, "done": True},
]]
_reponses = {"boîte": 0}

class _FauxOllama(_H):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"models": [{"name": "qwen3.5:4b"}], "version": "0.12.3"}')

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.end_headers()
        for ligne in SCENARIOS[_reponses["boîte"]]:
            self.wfile.write((_json.dumps(ligne) + "\n").encode())
        _reponses["boîte"] += 1

_serveur = _Srv(("127.0.0.1", 11521), _FauxOllama)
_threading.Thread(target=_serveur.serve_forever, daemon=True).start()
client = llm.ClientLLM(url="http://127.0.0.1:11521", modele="qwen3.5:4b")
morceaux: list[str] = []
texte = client.discuter_stream([{"role": "user", "content": "x"}], on_chunk=morceaux.append)
verif("streaming assemblé", texte == "Bonjour le monde", repr(texte))
verif("streaming diffusé au fil de l'eau", "".join(morceaux) == "Bonjour le monde",
      repr(morceaux))
morceaux.clear()
texte = client.discuter_stream([{"role": "user", "content": "x"}], on_chunk=morceaux.append)
verif("bloc <think> filtré dans le flux", texte == "Salut !" and "".join(morceaux) == "Salut !",
      repr((texte, morceaux)))
_serveur.shutdown()

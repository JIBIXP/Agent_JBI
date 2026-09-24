#!/usr/bin/env python3
"""JIBI 2 — point d'entrée unique.

  python run.py                 → fenêtre de bureau (Tkinter)
  python run.py --console       → console
  python run.py --console --voix          → console + JIBI parle
  python run.py --mains-libres            → « jibi, … » au micro
  python run.py --sans-confirmation       → ne jamais demander confirmation (dangereux)
"""
from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jibi2 import config


def lancer_mcp() -> None:
    """Lance le serveur MCP de JIBI en arrière-plan.

    Le serveur écoute sur 127.0.0.1:8080.
    Tout agent compatible MCP (Hermes, etc.) peut s'y connecter.
    Zéro accès internet requis.
    """
    try:
        from mcp_server import MCPServer
        import json
        import asyncio

        port = 8080
        import http.server

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/tools"):
                    s = MCPServer(port)
                    tools = s.get_tools()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tools": tools}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                request = json.loads(body)
                s = MCPServer(port)
                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(s.handle_request(request))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            def log_message(self, format, *args):
                pass

        httpd = http.server.HTTPServer(("127.0.0.1", port), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        print(f"🔌 MCP JIBI actif sur http://127.0.0.1:{port}")
    except Exception as e:
        print(f"(MCP serveur non démarré : {e})")


def principal() -> int:
    parseur = argparse.ArgumentParser(description="JIBI 2 — assistant local (Ollama + voix).")
    parseur.add_argument("--console", action="store_true", help="console au lieu de la fenêtre")
    parseur.add_argument("--voix", action="store_true", help="JIBI parle ses réponses")
    parseur.add_argument("--mains-libres", action="store_true", help="boucle micro « jibi, … »")
    parseur.add_argument("--sans-confirmation", action="store_true",
                          help="exécute les actions risquées sans demander (déconseillé)")
    arguments = parseur.parse_args()

    config.preparer_dossiers()
    lancer_mcp()

    from jibi2.assistant import Assistant
    from jibi2.memoire import Memoire
    from jibi2.securite import Garde
    from outils import charger_perso

    charger_perso()
    memoire = Memoire()
    garde = Garde()
    if arguments.sans_confirmation:
        print("Avertissement : --sans-confirmation exécute les commandes risquées sans demander.")
        garde.confirmer = lambda nom, detail: True

    assistant = Assistant(memoire, garde)
    import queue as module_file
    from outils import regler_services
    annonces = module_file.Queue()
    regler_services(assistant=assistant, garde=garde, annonces=annonces)

    # panneau web local (page HTML discutée au clavier, 127.0.0.1 uniquement)
    try:
        from interface import panneau as module_panneau
        numero = module_panneau.demarrer(assistant)
        print(f"Panneau local : http://127.0.0.1:{numero}")
    except Exception as echec:
        print(f"(panneau web indisponible : {echec})")
    from jibi2.planificateur import demarrer as demarrer_planificateur
    demarrer_planificateur()
    # Boucle continue (vérification périodique tant que JIBI est ouvert)
    from jibi2 import autonomie
    if config.valeur_bool("JIBI_AUTONOMIE_CONTINU"):
        thread = threading.Thread(
            target=autonomie.boucle_continue,
            args=(assistant,),
            daemon=True,
        )
        thread.start()
    voix_on = arguments.voix or config.valeur_bool("JIBI_VOIX_ACTIVE")

    if arguments.mains_libres:
        from interface.terminal import lancer
        lancer(assistant, garde, memoire, voix_on=voix_on, mains_libres=True,
               annonces=annonces)
    elif arguments.console:
        from interface.terminal import lancer
        lancer(assistant, garde, memoire, voix_on=voix_on, annonces=annonces)
    else:
        try:
            from interface.bureau import lancer as lancer_fenetre
            lancer_fenetre(assistant, garde, voix_on=voix_on, annonces=annonces)
        except Exception as e:  # pas d'écran / Tkinter cassé → repli console
            print(f"(fenêtre indisponible : {e} — passage en console)")
            from interface.terminal import lancer
            lancer(assistant, garde, memoire, voix_on=voix_on, annonces=annonces)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())

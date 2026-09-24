"""Serveur MCP pour JIBI 2.

Permet à tout agent compatible MCP (Hermes, Claude, etc.)
de découvrir et utiliser les outils JIBI localement.

Usage : python mcp_server.py
   ou    python mcp_server.py --port 8080

Le serveur écoute sur localhost:8080 par défaut.
Aucun accès internet requis.
"""
from __future__ import annotations

import sys
import json
import asyncio
import argparse
from pathlib import Path

# Ajoute le répertoire parent au path pour importer les outils
sys.path.insert(0, str(Path(__file__).resolve().parent))

from outils import outil, charger_integres, OUTILS, NOYAU
from jibi2 import config

# Charger les outils JIBI
charger_integres()


class MCPServer:
    """Serveur MCP minimal pour JIBI."""

    def __init__(self, port: int = 8080) -> None:
        self.port = port
        self.tools = self._lister_outils()

    def _lister_outils(self) -> list[dict]:
        """Retourne la liste des outils disponibles."""
        outils_list = []
        for nom in sorted(OUTILS):
            o = OUTILS[nom]
            outils_list.append({
                "name": nom,
                "description": o.description,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        p: {
                            "type": i.get("type", "string"),
                            "description": i.get("description", ""),
                            "required": i.get("obligatoire", False),
                        }
                        for p, i in o.parametres.items()
                    },
                },
            })
        return outils_list

    def get_tools(self) -> list[dict]:
        """Retourne tous les outils (pour la découverte)."""
        return self.tools

    def call_tool(self, name: str, params: dict) -> str:
        """Exécute un outil JIBI et retourne le résultat."""
        if name not in OUTILS:
            return json.dumps({"error": f"Outil inconnu : {name}"})

        o = OUTILS[name]
        # Vérifier les paramètres obligatoires
        for p, i in o.parametres.items():
            if i.get("obligatoire") and p not in params:
                return json.dumps({"error": f"Paramètre manquant : {p}"})

        try:
            result = o.fonction(**params)
            if isinstance(result, str):
                return json.dumps({"result": result})
            return json.dumps({"result": str(result)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def handle_request(self, request: dict) -> dict:
        """Gère une requête MCP."""
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "tools/list":
            return {"jsonrpc": "2.0", "result": {"tools": self.tools}, "id": 1}
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            result = self.call_tool(name, args)
            return {"jsonrpc": "2.0", "result": json.loads(result), "id": 2}
        elif method == "initialize":
            return {"jsonrpc": "2.0", "result": {
                "serverInfo": {"name": "JIBI", "version": "2.0"},
                "capabilities": {"tools": {"listChanged": True}},
            }, "id": 1}
        else:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Méthode inconnue"}, "id": None}


async def main():
    parser = argparse.ArgumentParser(description="Serveur MCP pour JIBI")
    parser.add_argument("--port", type=int, default=8080, help="Port d'écoute")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Adresse d'écoute")
    args = parser.parse_args()

    server = MCPServer(port=args.port)
    print(f"🔌 Serveur MCP JIBI démarré sur {args.host}:{args.port}")
    print(f"   {len(server.tools)} outils disponibles")
    print(f"   NOYAU : {len(NOYAU)} outils essentiels")
    print(f"   Connexion locale uniquement (pas d'internet nécessaire)")
    print(f"   Appuie Ctrl+C pour arrêter")
    print()

    # Simple HTTP server pour les clients MCP
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                request = json.loads(body)

                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(server.handle_request(request))
                loop.close()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            def do_Get(self):
                if self.path == "/":
                    tools = server.get_tools()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tools": tools}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Silence les logs HTTP

        httpd = HTTPServer((args.host, args.port), Handler)
        print(f"   📡 Écoute sur http://{args.host}:{args.port}")
        httpd.serve_forever()
    except ImportError:
        print("Erreur: http.server non disponible")
        print("Essaie: pip install hermes-agents")


if __name__ == "__main__":
    asyncio.run(main())

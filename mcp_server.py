"""Serveur MCP de JIBI 2 — exposition STRICTEMENT contrôlée de quelques outils.

Deux transports :

    python mcp_server.py --stdio        → pipeline stdin/stdout (recommandé :
        aucun port ouvert, recommandé pour Claude Desktop et tout client desktop) ;
    python mcp_server.py --port 8080    → HTTP local sur 127.0.0.1, avec jeton
        obligatoire X-JIBI-Token et contrôles jibi2/http_local.

Trois verrous, dans l'ordre :

1. Liste blanche (MCP_EXPOSES) — un outil n'est PAS exposé par défaut.
   Seules des lectures sûres le sont : ni executer_commande, ni
   eteindre_pc, ni modifier_noyau, ni écriture de fichier, ni domotique,
   ni micro, ni capture d'écran, ni Chrome.
2. Double contrôle défensif — même inscrit dans la liste blanche, un
   outil à risque="eleve" fait refuser le démarrage (ValueError), et un
   risque moyen est refusé à l'appel.
3. Passage par la Garde — les appels passent par outils.executer(...),
   comme la console et la fenêtre, jamais par outil.fonction(...) en
   direct. La Garde d'un serveur sans interface refuse toute action à
   risque élevé : un client MCP ne peut pas confirmer à la place
   de l'utilisateur.

En transport HTTP, en plus : le jeton (généré une fois dans
donnees/mcp_token, hors dépôt ; comparé en temps constant) et les
quatre contrôles de jibi2/http_local (socket, Host, X-Forwarded-*,
Origin). Tout appel est journalisé dans donnees/journal/mcp.log.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jibi2 import config, http_local                      # noqa: E402
from outils import OUTILS, NOYAU, charger_integres, executer  # noqa: E402

charger_integres()


# --------------------------------------------------------------- liste blanche
# Lectures sûres uniquement : aucune écriture, aucune commande système,
# aucune extensa de domotique/micro/écran/Chrome.
MCP_EXPOSES = {
    "heure_actuelle", "calculer", "lancer_un_de", "batterie",
    "espace_disque", "info_systeme", "lister_notes", "chercher_notes",
    "lister_rappels", "lister_workflows", "langues_disponibles",
    "statut_autonomie", "lire_progression",
    "consulter_audit",
}


def outils_exposes() -> list:
    """Otools actuellement publiés : liste blanche ∩ registre ∩ risque faible.

    Lève une ValueError si la liste blanche contient un outil à risque
    élevé : le jour où quelqu'un (ou JIBI lui-même) y ajoute
    `executer_commande`, le serveur refuse de démarrer au lieu de
    l'exposer silencieusement.
    """
    publics = []
    for nom in sorted(MCP_EXPOSES):
        o = OUTILS.get(nom)
        if o is None:
            continue                       # absent de cette installation
        if o.risque == "eleve":
            raise ValueError(
                f"{nom} est à risque élevé : jamais exposé au MCP. "
                "Un client MCP ne peut pas demander une confirmation à "
                "l'utilisateur à la place.")
        if o.risque != "faible":
            continue                       # lecture sûre non garantie
        publics.append(o)
    return publics


# ----------------------------------------------------------------------- jeton
_VERROU_JETON = threading.Lock()


def chemin_jeton() -> Path:
    return config.DOSSIER_DONNEES / "mcp_token"


def jeton(creer: bool = True) -> str:
    """Le jeton d'accès du MCP. Généré une fois, stocké hors dépôt
    (donnees/ est dans .gitignore), de droits 0600."""
    chemin = chemin_jeton()
    with _VERROU_JETON:
        if chemin.exists():
            value = chemin.read_text(encoding="utf-8").strip()
            if value:
                return value
        if not creer:
            return ""
        value = secrets.token_urlsafe(32)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(value + "\n", encoding="utf-8")
        try:
            chemin.chmod(0o600)
        except OSError:
            pass                            # Windows : ACL différentes
        return value


def jeton_valide(presente: str) -> bool:
    """Comparaison à temps constant ; un jeton vide n'est JAMAIS valide."""
    attendu = jeton(creer=False)
    if not attendu or not presente:
        return False
    return secrets.compare_digest(attendu, str(presente))


# ---------------------------------------------------------------- serveur
class MCPServer:
    """Serveur MCP minimal de JIBI, verrouillé par liste blanche."""

    def __init__(self) -> None:
        self.principal()                    # lève ValueError si la liste est corrompue
        self.tools = self._lister_outils()

    def principal(self) -> list:
        """Otools actuellement publiés : la même liste blanche ∩ registre."""
        return outils_exposes()

    def _lister_outils(self) -> list[dict]:
        outils_liste = []
        for o in outils_exposes():
            outils_liste.append({
                "name": o.nom,
                "description": " ".join(o.description.split()),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        p: {
                            "type": i.get("type", "string"),
                            "description": i.get("description", ""),
                        }
                        for p, i in o.parametres.items()
                    },
                    "required": [p for p, i in o.parametres.items()
                                 if i.get("obligatoire", False)],
                },
            })
        return outils_liste

    def get_tools(self) -> list[dict]:
        return self.tools

    def _journaliser(self, texte: str) -> None:
        try:
            from jibi2 import audit
            audit.journaliser("mcp", texte[:200], acteur="client_mcp",
                              resultat="hors-outils")
        except Exception:                   # noqa: BLE001
            pass                            # ne casse jamais l'appel
        try:
            config.DOSSIER_JOURNAL.mkdir(parents=True, exist_ok=True)
            with (config.DOSSIER_JOURNAL / "mcp.log").open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {texte[:400]}\n")
        except OSError:
            pass


    def call_tool(self, name: str, params: dict) -> str:
        """Exécuter un outil EXPOSÉ, via la Garde, et ombr du texte JSON."""
        params = params if isinstance(params, dict) else {}
        if name not in MCP_EXPOSES:
            self._journaliser(f"REFUS outil hors liste blanche : {name}")
            return json.dumps({"error": f"Outil non exposé au MCP : {name}"},
                              ensure_ascii=False)
        o = OUTILS.get(name)
        if o is None:
            return json.dumps({"error": f"Outil inconnu : {name}"},
                              ensure_ascii=False)
        if o.risque != "faible":
            self._journaliser(f"REFUS outil à risque {o.risque} : {name}")
            return json.dumps(
                {"error": f"{name} n'est pas une lecture sûre : refusé via MCP."},
                ensure_ascii=False)
        # Garde SANS interface : refuse tout risque élevé sans confirmer.
        from jibi2.securite import Garde
        resultat = executer(name, params, Garde())
        self._journaliser(
            f"appel {name} args={json.dumps(params, ensure_ascii=False)[:160]}"
            f" -> ok={resultat.get('ok')} {str(resultat.get('texte'))[:120]}")
        return json.dumps({"result": resultat.get("texte", "")},
                          ensure_ascii=False)

    async def handle_request(self, request: dict) -> dict:
        if not isinstance(request, dict):
            return {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32600, "message": "Requête invalide"}}
        identifiant = request.get("id")
        methode = request.get("method", "")
        params = request.get("params") or {}
        if methode == "initialize":
            return {"jsonrpc": "2.0", "id": identifiant, "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "JIBI", "version": "2.0"},
                "capabilities": {"tools": {"listChanged": False}},
            }}
        if methode == "tools/list":
            return {"jsonrpc": "2.0", "id": identifiant,
                    "result": {"tools": self.tools}}
        if methode == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            brut = self.call_tool(name, args)
            contenu = json.loads(brut)
            if "error" in contenu:
                return {"jsonrpc": "2.0", "id": identifiant,
                        "error": {"code": -32602, "message": contenu["error"]}}
            return {"jsonrpc": "2.0", "id": identifiant,
                    "result": {"content": [{"type": "text",
                                            "text": contenu["result"]}],
                               "isError": False}}
        return {"jsonrpc": "2.0", "id": identifiant,
                "error": {"code": -32601, "message": f"Méthode inconnue : {methode}"}}


# ------------------------------------------------------------- transport HTTP
def servir_http(server: MCPServer, hote: str, port: int) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def _refuser(self, code: int, message: str) -> None:
            server._journaliser(f"REFUS HTTP {code} : {message}"
                                f" (hôte={self.headers.get('host')},"
                                f" origin={self.headers.get('Origin')})")
            try:
                corps = message.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                self.wfile.write(corps)
            except OSError:
                pass

        def _autorise(self) -> bool:
            locale, raison = http_local.requete_locale(
                self.client_address[0], self.headers)
            if not locale:
                self._refuser(403, raison)
                return False
            if self.command == "POST" and http_local.origin_interdite(self.headers):
                self._refuser(403, "Origin non locale : CSRF refusé.")
                return False
            if not jeton_valide(self.headers.get("X-JIBI-Token", "")):
                self._refuser(401, "jeton X-JIBI-Token manquant ou invalide")
                return False
            return True

        def do_GET(self) -> None:       # noqa: N802 (imsposé par http.server)
            if not self._autorise():
                return
            if urlsplit(self.path).path in ("/", "/tools"):
                self._repondre({"tools": server.get_tools()})
            else:
                self._refuser(404, "route inconnue")

        def do_POST(self) -> None:      # noqa: N802
            if not self._autorise():
                return
            try:
                taille = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                taille = 0
            if taille <= 0 or taille > 1024 * 1024:
                self._refuser(413, "corps absent ou supérieur à 1 Mo")
                return
            try:
                requete = json.loads(self.rfile.read(taille) or b"{}")
            except json.JSONDecodeError:
                self._refuser(400, "JSON invalide")
                return
            boucle = asyncio.new_event_loop()
            try:
                self._repondre(boucle.run_until_complete(
                    server.handle_request(requete)))
            finally:
                boucle.close()

        def _repondre(self, objet: dict, code: int = 200) -> None:
            corps = json.dumps(objet, ensure_ascii=False).encode("utf-8")
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                self.wfile.write(corps)
            except OSError:
                pass

    httpd = ThreadingHTTPServer((hote, port), Handler)
    print(f"📡 MCP JIBI sur http://{hote}:{port}"
          f" — jeton : {chemin_jeton()}")
    print("   En-tête obligatoire : X-JIBI-Token")
    print("   HTTPS NON utilisé : liaison 127.0.0.1 avec jeton.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


# ------------------------------------------------------------- transport stdio
def servir_stdio(server: MCPServer) -> None:
    """JSON-RPC sur stdin/stdout, un message par ligne (style LSP).

    Aucun port ouvert : le client MCP lance lui-même le processus.
    C'est le transport recommandé — il n'y a rien à protéger du navigateur.
    """
    print("🔌 MCP JIBI en stdio — aucun port ouvert.", file=sys.stderr)
    for ligne in sys.stdin:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            requete = json.loads(ligne)
        except json.JSONDecodeError:
            reponse = {"jsonrpc": "2.0", "id": None,
                       "error": {"code": -32700, "message": "JSON invalide"}}
        else:
            reponse = asyncio.run(server.handle_request(requete))
        sys.stdout.write(json.dumps(reponse, ensure_ascii=False) + "\n")
        sys.stdout.flush()


# ------------------------------------------------------------------ principal
def principal() -> int:
    parseur = argparse.ArgumentParser(description="Serveur MCP de JIBI (liste blanche).")
    parseur.add_argument("--port", type=int,
                         default=config.entier("JIBI_MCP_PORT", 8080),
                         help="port d'écoute (par défaut JIBI_MCP_PORT)")
    parseur.add_argument("--host", default="127.0.0.1",
                         help="adresse d'écoute (laisser 127.0.0.1)")
    parseur.add_argument("--stdio", action="store_true",
                         help="transport stdin/stdout (recommandé, aucun port)")
    attributs = parseur.parse_args()

    config.preparer_dossiers()
    try:
        server = MCPServer()
    except ValueError as erreur:
        print(f"❌ {erreur}", file=sys.stderr)
        return 2

    print(f"🔌 Serveur MCP JIBI — {len(server.tools)} outils exposés"
          f" (sur {len(OUTILS)} enregistrés, {len(NOYAU)} noyau)", file=sys.stderr)
    print("   Liste blanche : "
          + ", ".join(t["name"] for t in server.tools), file=sys.stderr)
    if attributs.stdio:
        servir_stdio(server)
    else:
        if attributs.host.strip().lower() not in ("127.0.0.1", "localhost", "[::1]", "::1"):
            print("❌ Le MCP HTTP ne peut lier que la boucle locale.",
                  file=sys.stderr)
            return 2
        servir_http(server, attributs.host, attributs.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())

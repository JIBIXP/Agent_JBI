"""Panneau web local de JIBI — inspiré du panneau de Jarvis.

Un petit serveur HTTP qui tourne sur le PC (127.0.0.1 UNIQUEMENT — comme
chez Jarvis : jamais accessible depuis le réseau) et sert une page web
pour discuter avec JIBI au clavier, voir son état, avec des raccourcis.
C'est le fichier panneau.html qui est servi : aucun CDN, aucun appel
extérieur, ça marche hors ligne.

Démarré automatiquement par run.py ; « ouvre le panneau » lance le
navigateur dessus. Port réglable : JIBI_PANNEAU_PORT dans le .env.
"""
from __future__ import annotations

import json
import mimetypes
from email.parser import BytesParser
from email.policy import default as email_default
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).parent / "panneau.html"

SERVEUR: ThreadingHTTPServer | None = None
_ASSISTANT = None
_VERROU = threading.Lock()          # un message à la fois (histoire partagée)


def _normaliser_texte(texte) -> str:
    """Normalise les caractères de sortie console avant l'envoi au navigateur."""
    valeur = str(texte or "")
    valeur = valeur.replace("\u00a0", " ").replace("\u202f", " ")
    import re
    valeur = re.sub(r"(?<=\d)\ufffd(?=\d)", " ", valeur)
    return valeur.replace("\ufffd", "").replace("\x00", "")


def _texte_sans_boucle(texte: str) -> str:
    """Évite d'afficher plusieurs fois un même sous-titre Amara."""
    lignes: list[str] = []
    vus: dict[str, int] = {}
    for brute in str(texte or "").splitlines():
        ligne = brute.strip()
        if not ligne:
            if lignes and lignes[-1] != "":
                lignes.append("")
            continue
        if ligne == "Sous-titres réalisés par la communauté d'Amara.org":
            if vus.get(ligne, 0) >= 1:
                continue
        elif vus.get(ligne, 0) >= 2:
            continue
        vus[ligne] = vus.get(ligne, 0) + 1
        lignes.append(ligne)
    return "\n".join(lignes).strip()


def definir_assistant(assistant) -> None:
    global _ASSISTANT
    _ASSISTANT = assistant


def _assurer_assistant():
    global _ASSISTANT
    if _ASSISTANT is None:
        from jibi2.assistant import Assistant
        from jibi2.memoire import Memoire
        from jibi2.securite import Garde
        _ASSISTANT = Assistant(Memoire(), Garde())
    return _ASSISTANT


def demarrer(assistant=None, port: int | None = None) -> int:
    """Démarre le serveur local (idempotent). Renvoie le port effectif."""
    global SERVEUR
    if assistant is not None:
        definir_assistant(assistant)
    if SERVEUR is not None:
        return SERVEUR.server_address[1]
    if port is None:
        from jibi2 import config
        try:
            port = int(str(config.valeur("JIBI_PANNEAU_PORT", "8756")).strip() or 8756)
        except ValueError:
            port = 8756
    _assurer_assistant()
    SERVEUR = ThreadingHTTPServer(("127.0.0.1", port), _Gestionnaire)
    threading.Thread(target=SERVEUR.serve_forever, daemon=True).start()
    return SERVEUR.server_address[1]


def arreter() -> None:
    global SERVEUR
    if SERVEUR is not None:
        SERVEUR.shutdown()
        SERVEUR.server_close()
        SERVEUR = None


def port() -> int:
    return SERVEUR.server_address[1] if SERVEUR is not None else 0


def _page_html() -> bytes:
    """Page du panneau, avec la surcharge de design si l'utilisateur (ou
    JIBI lui-même) a personnalisé les couleurs (donnees/design.json)."""
    try:
        page = PAGE.read_text(encoding="utf-8")
    except OSError:
        return (b"<html><body><h1>JIBI</h1><p>panneau.html introuvable</p>"
                b"</body></html>")
    from outils.design import style_panneau
    surcharge = style_panneau()
    if surcharge:
        page = page.replace("</head>", surcharge + "</head>", 1)
    return page.encode("utf-8")


def _documents() -> list[dict]:
    """Liste uniquement les fichiers de l'espace de travail, sans exposition du PC."""
    from outils.fichiers import _racine
    racine = _racine()
    resultats: list[dict] = []
    try:
        chemins = sorted((p for p in racine.rglob("*") if p.is_file()),
                         key=lambda p: p.stat().st_mtime if p.exists() else 0,
                         reverse=True)
    except OSError:
        chemins = []
    for chemin in chemins[:100]:
        try:
            stat = chemin.stat()
            resultats.append({"nom": chemin.name, "taille": stat.st_size,
                              "type": mimetypes.guess_type(chemin.name)[0] or "application/octet-stream",
                              "url": "/telecharger/" + urllib.parse.quote(chemin.name),
                              "modifie": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))})
        except OSError:
            continue
    return resultats


def _connexion_abandonnee(erreur: BaseException | None) -> bool:
    """True quand le navigateur a fermé la requête HTTP (cas normal)."""
    if isinstance(erreur, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
        return True
    return getattr(erreur, "winerror", None) in (10053, 10054)


def _chemin_telechargement(nom: str) -> Path | None:
    from outils.fichiers import _chemin_espace
    nom = urllib.parse.unquote(nom or "")
    if not nom or Path(nom).name != nom or "/" in nom or "\\" in nom:
        return None
    try:
        chemin = _chemin_espace(nom)
    except ValueError:
        return None
    return chemin if chemin.is_file() else None


class _Gestionnaire(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _json(self, objet: dict, code: int = 200) -> None:
        brut = json.dumps(objet, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)
        except OSError as e:
            if _connexion_abandonnee(e):
                return
            raise

    def _telecharger(self, chemin: Path) -> None:
        try:
            brut = chemin.read_bytes()
        except OSError:
            self._json({"erreur": "document introuvable"}, 404)
            return
        if len(brut) > 100 * 1024 * 1024:
            self._json({"erreur": "document trop volumineux pour le panneau"}, 413)
            return
        nom = urllib.parse.quote(chemin.name)
        try:
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(chemin.name)[0] or "application/octet-stream")
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{nom}")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)
        except OSError as e:
            if not _connexion_abandonnee(e):
                raise

    def handle_error(self, request, client_address) -> None:
        erreur = sys.exc_info()[1]
        if _connexion_abandonnee(erreur):
            return
        super().handle_error(request, client_address)

    def do_GET(self) -> None:
        route = urllib.parse.urlsplit(self.path).path
        if route in ("/", "/panneau"):
            brut = _page_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)
        elif route == "/api/etat":
            a = _ASSISTANT
            import datetime
            etat = {
                "heure": datetime.datetime.now().strftime("%H:%M"),
                "outils": 0, "modele": "?", "ollama": False, "session": 0,
            }
            if a is not None:
                import contextlib
                with contextlib.suppress(Exception):
                    etat.update({
                        "outils": len(_lister_outils()),
                        "modele": getattr(a.client, "modele", "?"),
                        "ollama": bool(a.client.disponible()),
                        "session": a.memoire.session_courante() or 0,
                    })
            self._json(etat)
        elif route == "/api/progression":
            from jibi2 import progression
            self._json(progression.lire())
        elif route == "/api/documents":
            self._json({"documents": _documents()})
        elif route == "/api/audit":
            from jibi2 import audit
            self._json({"evenements": audit.lire(20)})
        elif route == "/api/signaux":
            try:
                from outils import signaux
                donnees = signaux.collecter()
                self._json({k: (_normaliser_texte(v) if isinstance(v, str) else v)
                            for k, v in donnees.items()})
            except Exception as e:
                if _connexion_abandonnee(e):
                    return
                self._json({"erreur": str(e)[:200]}, 503)
        elif route.startswith("/telecharger/"):
            chemin = _chemin_telechargement(route[len("/telecharger/"):])
            if chemin is None:
                self._json({"erreur": "document introuvable"}, 404)
            else:
                self._telecharger(chemin)
        else:
            self._json({"erreur": "introuvable"}, 404)

    def do_POST(self) -> None:
        route = urllib.parse.urlsplit(self.path).path
        if route == "/api/import":
            try:
                taille = int(self.headers.get("Content-Length", "0") or 0)
                if taille <= 0 or taille > 52 * 1024 * 1024:
                    self._json({"ok": False, "message": "Fichier vide ou supérieur à 50 Mo."}, 413)
                    return
                type_front = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in type_front.lower():
                    self._json({"ok": False, "message": "Import multipart attendu."}, 400)
                    return
                corps = self.rfile.read(taille)
                message = BytesParser(policy=email_default).parsebytes(
                    b"Content-Type: " + type_front.encode("latin-1", "replace")
                    + b"\r\nMIME-Version: 1.0\r\n\r\n" + corps)
                resultats = []
                for partie in message.iter_parts():
                    nom = partie.get_filename()
                    donnees = partie.get_payload(decode=True) or b""
                    if nom:
                        from outils.imports import importer_buffer
                        resultats.append(importer_buffer(nom, donnees))
                if not resultats:
                    self._json({"ok": False, "message": "Aucun fichier reçu."}, 400)
                else:
                    self._json({"ok": all(x.startswith("Import réussi") for x in resultats),
                                "messages": resultats})
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "message": f"Import impossible : {str(exc)[:180]}"}, 400)
            return
        if route == "/api/ecoute":
            try:
                from audio import ecoute
                texte = ecoute.ecouter_phrase(timeout=8, silence=1.2, limite=15)
                self._json({"texte": texte, "erreur": ecoute.ERREUR_DERNIERE})
            except Exception as e:
                if _connexion_abandonnee(e):
                    return
                self._json({"texte": "", "erreur": str(e)[:200]}, 503)
            return
        if route != "/api/message":
            self._json({"erreur": "introuvable"}, 404)
            return
        try:
            taille = min(int(self.headers.get("Content-Length", 0) or 0), 2 * 1024 * 1024)
            if taille <= 0:
                raise ValueError("requête vide")
            donnees = json.loads(self.rfile.read(taille) or b"{}")
            texte = str(donnees.get("texte", "")).strip()
            if not texte:
                self._json({"reponse": "Dis-moi quelque chose d'abord.", "actions": []})
                return
            with _VERROU:                      # un échange à la fois
                resultat = _assurer_assistant().repondre(texte)
            self._json({"reponse": _normaliser_texte(_texte_sans_boucle(resultat.get("reponse", ""))),
                        "actions": resultat.get("actions", [])})
        except Exception as e:  # noqa: BLE001
            if _connexion_abandonnee(e):
                return
            try:
                self._json({"reponse": f"Oups, j'ai échoué : {str(e)[:120]}", "actions": []}, 500)
            except OSError as envoi:
                if not _connexion_abandonnee(envoi):
                    raise


def _lister_outils() -> list[str]:
    from outils import lister_noms
    return lister_noms()

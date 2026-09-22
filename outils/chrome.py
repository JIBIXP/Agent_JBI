"""Assistance Chrome : onglets et lecture de la page active, en local.

Comme Jarvis : depuis Chrome 136, Google interdit le débogage à distance
sur le profil par défaut (sécurité). On discute donc avec un profil
Chrome DÉDIÉ « ChromeJIBI », lancé avec --remote-debugging-port
(double-clic sur CHROME_JIBI.bat, ou lancement automatique au premier
outil si Chrome est trouvé). Connecte-toi une fois aux sites où tu veux
de l'aide : c'est mémorisé dans ce profil.

Technique : uniquement les endpoints HTTP du protocole CDP (/json/...)
— pas une bibliothèque de plus, aucune donnée ne sort du PC.
JIBI ne fait que lister, ouvrir, afficher, lire ou fermer des onglets :
jamais de saisie de mot de passe, jamais de clic à ta place.
(L'interaction complète — clic, scroll, remplir un champ — exige le
protocole WebSocket CDP ; chez Jarvis c'est un usage cloud. Hors sujet
pour du 100 % local : on s'en passe.)
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from outils import outil

VERROU = threading.Lock()


def _base() -> str:
    from jibi2 import config
    port = str(config.valeur("JIBI_CDP_PORT", "9222")).strip() or "9222"
    return "http://127.0.0.1:" + port


def _requete(route: str, methode: str = "GET", timeout: float = 2.0):
    requete = urllib.request.Request(_base() + route, method=methode)
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        brut = reponse.read().decode("utf-8", "replace").strip()
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        return brut                       # « Target activated », etc.


def _port_vivant() -> bool:
    try:
        return bool(_requete("/json/version"))
    except Exception:  # noqa: BLE001
        return False


def _onglets() -> list[dict]:
    liste = _requete("/json/list")
    if not isinstance(liste, list):
        return []
    return [c for c in liste
            if c.get("type") == "page"
            and not str(c.get("url", "")).startswith(("devtools://", "chrome-extension://"))]


def _reveiller() -> bool:
    """Lance le profil dédié « ChromeJIBI » si le port ne répond pas."""
    if _port_vivant():
        return True
    with VERROU:
        if _port_vivant():
            return True
        try:
            from outils.applications import _trouver_chrome
            chrome = _trouver_chrome()
            if not chrome:
                return False
            local = os.environ.get("LOCALAPPDATA")
            racine = Path(local) / "JIBI2" if local else Path.home() / "JIBI2"
            profil = racine / "ChromeJIBI"
            drapeaux = [chrome,
                        "--remote-debugging-port=" + _base().rsplit(":", 1)[1],
                        "--user-data-dir=" + str(profil),
                        "--no-first-run", "--no-default-browser-check",
                        "about:blank"]
            kwargs: dict = {}
            if os.name == "nt":
                kwargs["creationflags"] = 0x00000008        # DETACHED_PROCESS
            subprocess.Popen(drapeaux, **kwargs)
            for _ in range(12):                             # ~6 s max
                time.sleep(0.5)
                if _port_vivant():
                    return True
        except Exception:  # noqa: BLE001
            return False
    return _port_vivant()


def _message_port() -> str:
    return ("Chrome ne répond pas sur le port de débogage. "
            "Double-clique sur CHROME_JIBI.bat (profil dédié « ChromeJIBI ») "
            "puis redemande-moi.")


def _choisir(cible: str, onglets: list[dict]) -> dict | None:
    """Retrouve un onglet par numéro (1, 2…) ou par morceau de titre/URL."""
    c = cible.strip()
    if c.isdigit():
        i = int(c) - 1
        return onglets[i] if 0 <= i < len(onglets) else None
    c = c.lower()
    for o in onglets:
        if c in str(o.get("title", "")).lower() or c in str(o.get("url", "")).lower():
            return o
    return None


@outil("lister_onglets",
       "Liste les onglets ouverts dans Chrome (profil connecté à JIBI).",
       categorie="applications", risque="faible",
       exemple="quels onglets sont ouverts ?")
def lister_onglets() -> str:
    if not _reveiller():
        return _message_port()
    onglets = _onglets()
    if not onglets:
        return "Aucun onglet ordinaire ouvert."
    lignes = [f"{i + 1}. {o.get('title', '?')[:70]} — {o.get('url', '?')[:90]}"
              for i, o in enumerate(onglets)]
    return f"{len(onglets)} onglet(s) :\n" + "\n".join(lignes)


@outil("ouvrir_onglet",
       "Ouvre une URL dans un NOUVEL onglet de la fenêtre Chrome connectée "
       "à JIBI (comme ouvrir_chrome, mais dans la fenêtre de débogage).",
       parametres={"url": {"type": "str", "obligatoire": True,
                           "description": "adresse du site (youtube.com…)"}},
       categorie="applications", risque="faible",
       exemple="ouvre YouTube dans un onglet → url=youtube.com")
def ouvrir_onglet(url: str) -> str:
    if not _reveiller():
        return _message_port()
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    cible = _requete("/json/new?url=" + urllib.parse.quote(url, safe=""), methode="PUT")
    titre = cible.get("title", url) if isinstance(cible, dict) else url
    return f"Onglet ouvert : {titre}"


@outil("activer_onglet",
       "Passe sur un onglet Chrome (par numéro dans la liste ou par mot du titre).",
       parametres={"cible": {"type": "str", "obligatoire": True,
                             "description": "numéro (2) ou morceau de titre/URL (youtube)"}},
       categorie="applications", risque="faible",
       exemple="passe sur l'onglet YouTube → cible=youtube")
def activer_onglet(cible: str) -> str:
    if not _reveiller():
        return _message_port()
    onglets = _onglets()
    o = _choisir(cible, onglets)
    if o is None:
        return f"Onglet « {cible} » introuvable. Utilise lister_onglets pour voir les numéros."
    _requete("/json/activate/" + str(o.get("id", "")))
    return f"Onglet affiché : {o.get('title', '?')[:70]}"


@outil("fermer_onglet",
       "Ferme un onglet Chrome (par numéro ou mot du titre). Action définitive : "
       "JIBI demandera confirmation à l'utilisateur.",
       parametres={"cible": {"type": "str", "obligatoire": True,
                             "description": "numéro (3) ou morceau de titre/URL"}},
       categorie="applications", risque="eleve",
       exemple="ferme l'onglet YouTube → cible=youtube")
def fermer_onglet(cible: str) -> str:
    if not _reveiller():
        return _message_port()
    onglets = _onglets()
    o = _choisir(cible, onglets)
    if o is None:
        return f"Onglet « {cible} » introuvable. Utilise lister_onglets pour voir les numéros."
    _requete("/json/close/" + str(o.get("id", "")))
    return f"Onglet fermé : {o.get('title', '?')[:70]}"


@outil("lire_onglet_actif",
       "Lit le TEXTE de l'onglet Chrome actif (premier de la liste) pour le "
       "résumer, le traduire ou en tirer des notes. Renvoie titre, URL et contenu.",
       categorie="applications", risque="faible",
       exemple="résume cette page")
def lire_onglet_actif() -> str:
    if not _reveiller():
        return _message_port()
    onglets = _onglets()
    if not onglets:
        return "Aucun onglet à lire."
    o = onglets[0]
    titre, url = str(o.get("title", "?")), str(o.get("url", ""))
    if url.startswith(("chrome://", "about:")):
        return f"L'onglet actif est une page interne ({url}) : rien à résumer."
    from outils.web import lire_page_web
    texte = lire_page_web(url)
    if texte.startswith("Impossible de lire la page") or texte.startswith("La page ne contient pas"):
        texte = "(contenu non lisible directement — c'est souvent le cas des pages très animées)"
    return f"Onglet actif : {titre}\nURL : {url}\n\n{texte[:3500]}"

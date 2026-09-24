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
jamais de saisie de mot de passe, jamais de clic à ta place. Pour un compte,
il ouvre simplement le site dans le profil ChromeJIBI : l'utilisateur se
connecte lui-même une fois ; ensuite JIBI peut retrouver et afficher l'onglet
de session sans lire ses cookies ni ses identifiants.
(L'interaction complète — clic, scroll, remplir un champ — exige le
protocole WebSocket CDP ; chez Jarvis c'est un usage cloud. Hors sujet
pour du 100 % local : on s'en passe.)
"""
from __future__ import annotations

import ctypes
import html as module_html
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from outils import outil

VERROU = threading.Lock()


def _base() -> str:
    from jibi2 import config
    port = str(config.valeur("JIBI_CDP_PORT", "9333")).strip() or "9333"
    return "http://127.0.0.1:" + port


def _requete(route: str, methode: str = "GET", timeout: float = 2.0):
    requete = urllib.request.Request(_base() + route, method=methode)
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        brut = reponse.read().decode("utf-8", "replace").strip()
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        return brut                       # « Target activated », etc.


def _recherche_en_arriere_plan() -> bool:
    from jibi2 import config
    return config.valeur_bool("JIBI_CHROME_SEARCH_BACKGROUND")


def _fenetre_precedente() -> int:
    if os.name != "nt":
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def _eviter_le_premier_plan(avant: int) -> None:
    """Réduit la fenêtre Chrome si le CDP l'a malgré tout activée."""
    if os.name != "nt" or not avant:
        return
    try:
        user32 = ctypes.windll.user32
        apres = int(user32.GetForegroundWindow() or 0)
        if not apres or apres == avant:
            return
        longueur = user32.GetWindowTextLengthW(apres)
        titre = ""
        if longueur:
            tampon = ctypes.create_unicode_buffer(longueur + 1)
            user32.GetWindowTextW(apres, tampon, longueur + 1)
            titre = tampon.value
        if "chrome" in titre.casefold() or "google chrome" in titre.casefold():
            user32.ShowWindowAsync(apres, 6)  # SW_MINIMIZE, sans activation
    except Exception:
        pass


def _nouvel_onglet(url: str, background: bool = False):
    """Crée un onglet Chrome, en demandant une création hors premier plan."""
    avant = _fenetre_precedente() if background else 0
    route = "/json/new?url=" + urllib.parse.quote(url, safe="")
    if background:
        route += "&background=true"
    try:
        cible = _requete(route, methode="PUT", timeout=5.0)
    except Exception:
        if not background:
            raise
        # Certains Chromium ignorent background=true : on conserve le mode
        # silencieux en activant puis en réduisant la fenêtre côté Windows.
        cible = _requete("/json/new?url=" + urllib.parse.quote(url, safe=""),
                          methode="PUT", timeout=5.0)
    if background:
        _eviter_le_premier_plan(avant)
    return cible


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


def _reveiller(background: bool = False) -> bool:
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
                        "--no-first-run", "--no-default-browser-check"]
            if background:
                drapeaux.append("--start-minimized")
            drapeaux.append("about:blank")
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
    from jibi2 import config
    port = config.valeur("JIBI_CDP_PORT", "9333")
    return (f"Chrome ne répond pas sur le port de débogage {port}. "
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


SITES_COMPTE = {
    "google": "https://myaccount.google.com/",
    "gmail": "https://mail.google.com/",
    "youtube": "https://www.youtube.com/",
    "github": "https://github.com/settings/profile",
    "chatgpt": "https://chatgpt.com/",
    "openrouter": "https://openrouter.ai/settings",
}


@outil("visiter_site",
       "Ouvre directement un site dans ChromeJIBI et peut ensuite en lire le "
       "texte public. Ne clique pas et ne remplit aucun formulaire.",
       {"url": {"type": "str", "obligatoire": True, "description": "adresse http(s)"},
        "lire": {"type": "bool", "obligatoire": False,
                  "description": "renvoyer aussi le texte de la page"}},
       categorie="applications", risque="faible",
       exemple='{"outil": "visiter_site", "parametres": {"url": "https://fr.wikipedia.org", "lire": true}}')
def visiter_site(url: str, lire: bool = False) -> str:
    ouverture = ouvrir_onglet(url)
    if "Impossible" in ouverture or "n'existe pas" in ouverture:
        return ouverture
    if not lire:
        return ouverture
    from outils.web import lire_page_web
    return ouverture + "\n\n" + lire_page_web(url)


def _google_bloque(page: str) -> bool:
    """Détecte une vérification Google visible sans confondre un script innocent."""
    visible = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page,
                     flags=re.DOTALL | re.IGNORECASE).casefold()
    return any(marqueur in visible for marqueur in (
        "trafic exceptionnel", "unusual traffic", "activez javascript",
        "avant d'accéder à google", "nos systèmes ont détecté",
        "g-recaptcha", "captcha-form"))


def _google_resultats(page: str, nombre: int) -> list[tuple[str, str, str]]:
    """Extrait les résultats Google sans exécuter le contenu de la page."""
    if _google_bloque(page):
        return []
    resultats: list[tuple[str, str, str]] = []
    for correspondance in re.finditer(r"<h3\b[^>]*>(.*?)</h3>", page,
                                      re.DOTALL | re.IGNORECASE):
        titre = re.sub(r"\s+", " ",
                       module_html.unescape(re.sub(r"<[^>]+>", "",
                                                   correspondance.group(1)))).strip()
        debut = max(0, correspondance.start() - 1800)
        ancres = list(re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>',
                                  page[debut:correspondance.start()],
                                  re.DOTALL | re.IGNORECASE))
        if not titre or not ancres:
            continue
        lien = module_html.unescape(ancres[-1].group(1))
        try:
            parties = urllib.parse.urlsplit(lien)
            if parties.path == "/url":
                lien = (urllib.parse.parse_qs(parties.query).get("q") or [lien])[0]
        except ValueError:
            pass
        if not lien.startswith(("http://", "https://")):
            continue
        if any(x in urllib.parse.urlsplit(lien).netloc for x in (
                "accounts.google.com", "consent.google.com", "policies.google.com")):
            continue
        extrait_brut = page[correspondance.end():correspondance.end() + 1400]
        extrait = re.sub(r"\s+", " ", module_html.unescape(
            re.sub(r"<[^>]+>", " ", extrait_brut))).strip()[:240]
        resultats.append((titre, lien, extrait))
        if len(resultats) >= max(1, min(int(nombre), 8)):
            break
    return resultats


def _google_requete(requete: str, nombre: int) -> str:
    from outils.applications import _trouver_chrome
    from jibi2 import config
    chrome = _trouver_chrome()
    if not chrome:
        return ("Chrome local est introuvable. Installe Chrome ou configure "
                "JIBI_BROWSER_CHROME dans le .env.")
    if not config.valeur_bool("JIBI_BROWSER_USE"):
        return "Browser Use local est désactivé. Active JIBI_BROWSER_USE=1 dans le .env."
    profil = Path(tempfile.mkdtemp(prefix="jibi-google-headless-"))
    url = ("https://www.google.com/search?hl=fr&gl=fr&num="
           + str(max(1, min(int(nombre), 8))) + "&gbv=1&q="
           + urllib.parse.quote_plus(requete))
    commande = [str(chrome), "--headless=new", "--disable-gpu",
                "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-sync",
                "--disable-background-networking", "--window-size=1280,900",
                "--virtual-time-budget=8000", "--user-data-dir=" + str(profil),
                "--dump-dom", url]
    try:
        fait = subprocess.run(commande, capture_output=True,
                              timeout=max(10, min(int(config.valeur(
                                  "JIBI_BROWSER_TIMEOUT", "45")), 90)))
        page = fait.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "La recherche Google headless a dépassé le délai autorisé."
    except Exception as exc:  # noqa: BLE001
        return f"Chrome headless n'a pas pu démarrer : {str(exc)[:180]}"
    finally:
        shutil.rmtree(profil, ignore_errors=True)
    if any(marqueur in page.casefold() for marqueur in (
            "captcha", "trafic exceptionnel", "activez javascript",
            "avant d'accéder à google", "unusual traffic")):
        return ("Google a demandé une vérification dans Chrome headless. "
                "JIBI ne contourne jamais un CAPTCHA ou un contrôle anti-robot ; "
                "demande simplement d'afficher la page pour la traiter manuellement.")
    resultats = _google_resultats(page, nombre)
    if not resultats:
        return ("Google n'a renvoyé aucun résultat exploitable en mode headless. "
                "La page peut être soumise à une vérification anti-robot.")
    lignes = []
    for index, (titre, lien, extrait) in enumerate(resultats, 1):
        lignes.append(f"{index}. {titre}\n   {lien}" + (f"\n   {extrait}" if extrait else ""))
    return "Recherche Google headless terminée :\n" + "\n".join(lignes)


@outil("chercher_google_headless",
       "Fait une recherche Google dans un vrai Chrome local headless, sans "
       "fenêtre, cookies ni profil persistant. Ne contourne aucun CAPTCHA.",
       {"requete": {"type": "str", "obligatoire": True,
                   "description": "texte à rechercher sur Google"},
        "nombre": {"type": "int", "obligatoire": False,
                   "description": "nombre de résultats (défaut 5)"}},
       categorie="web", risque="faible",
       exemple='{"outil": "chercher_google_headless", "parametres": {"requete": "Claude IA"}}')
def chercher_google_headless(requete: str, nombre: int = 5) -> str:
    requete = (requete or "").strip()
    if not requete:
        return "Dis-moi quoi rechercher sur Google."
    return _google_requete(requete, nombre)


@outil("chercher_dans_chrome",
       "Ouvre une recherche Google dans le profil ChromeJIBI. Par défaut elle "
       "reste en arrière-plan et ne prend pas le focus ; mets afficher=true "
       "seulement si l'utilisateur demande de voir la page. JIBI ne saisit "
       "aucun mot de passe.",
       {"requete": {"type": "str", "obligatoire": True,
                   "description": "texte à rechercher dans Google"},
        "afficher": {"type": "bool", "obligatoire": False,
                     "description": "ouvrir et afficher la page (défaut false)"}},
       categorie="applications", risque="faible",
       exemple='{"outil": "chercher_dans_chrome", "parametres": {"requete": "recettes de pasta"}}')
def chercher_dans_chrome(requete: str, afficher: bool = False) -> str:
    requete = (requete or "").strip()
    if not requete:
        return "Dis-moi ce que je dois rechercher dans Chrome."
    background = _recherche_en_arriere_plan() and not afficher
    if not _reveiller(background=background):
        return _message_port()
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(requete)
    try:
        cible = _nouvel_onglet(url, background=background)
    except Exception:
        return _message_port()
    if background:
        return ("Recherche ChromeJIBI lancée en arrière-plan avec Google, "
                f"sans afficher la page : {requete}")
    titre = cible.get("title", "Recherche Google") if isinstance(cible, dict) else "Recherche Google"
    return f"Recherche ChromeJIBI ouverte : {titre} — {requete}"


@outil("ouvrir_compte_chrome",
       "Ouvre un site de compte dans le profil ChromeJIBI. Si la session existe, "
       "la réutilise et affiche l'onglet. Sinon l'utilisateur se connecte lui-même "
       "une fois : JIBI ne lit jamais le mot de passe, les cookies ou le code 2FA.",
       {"site": {"type": "str", "obligatoire": False,
                 "description": "google, gmail, youtube, github, chatgpt, openrouter ou URL"},
        "nom": {"type": "str", "obligatoire": False,
                "description": "nom de l'onglet déjà ouvert à afficher"}},
       categorie="applications", risque="moyen",
       exemple='{"outil": "ouvrir_compte_chrome", "parametres": {"site": "google"}}')
def ouvrir_compte_chrome(site: str = "google", nom: str = "") -> str:
    if not _reveiller():
        return _message_port()
    onglets = _onglets()
    if nom.strip():
        cible = _choisir(nom, onglets)
        if cible is not None:
            _requete("/json/activate/" + str(cible.get("id", "")))
            return f"Session ChromeJIBI affichée : {cible.get('title', '?')[:80]}"
    demande = (site or "google").strip().lower()
    url = SITES_COMPTE.get(demande)
    if url is None:
        if not demande.startswith(("http://", "https://")):
            demande = "https://" + demande
        url = demande
    try:
        parties = urllib.parse.urlsplit(url)
        if parties.scheme not in ("http", "https") or not parties.hostname:
            return "Site de compte refusé : utilise une adresse http(s) valide."
    except ValueError:
        return "Site de compte refusé : adresse invalide."
    cible = _requete("/json/new?url=" + urllib.parse.quote(url, safe=""), methode="PUT")
    titre = cible.get("title", url) if isinstance(cible, dict) else url
    return (f"Compte ouvert dans ChromeJIBI : {titre}. "
            "Si une connexion est demandée, connecte-toi toi-même une fois ; "
            "JIBI ne récupère jamais tes identifiants.")


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
    from outils.web import _lire_page_web_texte
    texte = _lire_page_web_texte(url, allow_local=True)
    if texte.startswith("Impossible de lire la page") or texte.startswith("La page ne contient pas"):
        texte = "(contenu non lisible directement — c'est souvent le cas des pages très animées)"
    return f"Onglet actif : {titre}\nURL : {url}\n\n{texte[:3500]}"

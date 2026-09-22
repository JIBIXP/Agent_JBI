"""Outils applications de JIBI 2 : ouvrir des programmes et des sites."""
from __future__ import annotations

import subprocess
import sys
import webbrowser

from outils import outil


@outil("ouvrir_application", "Ouvre une application installée ou un fichier avec son programme par défaut.",
       {"cible": {"type": "str", "obligatoire": True,
                  "description": "nom de l'application ('notepad', 'calc', 'mspaint', 'spotify'...) "
                                 "ou chemin d'un fichier/dossier à ouvrir"}},
       categorie="applications", risque="moyen",
       exemple='{"outil": "ouvrir_application", "parametres": {"cible": "notepad"}}')
def ouvrir_application(cible: str) -> str:
    cible = cible.strip().strip('"')
    try:
        if sys.platform == "win32":
            import os
            os.startfile(cible)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", cible])
        else:
            subprocess.Popen(["xdg-open", cible])
        return f"J'ai ouvert « {cible} »."
    except FileNotFoundError:
        return f"« {cible} » n'est pas trouvé. Vérifie le nom (ex. notepad, calc, mspaint)."
    except Exception as e:
        return f"Impossible d'ouvrir « {cible} » : {e}"


CHEMINS_CHROME = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",   # Edge en secours
)


def _trouver_chrome() -> str | None:
    import os
    from pathlib import Path
    for chemin in CHEMINS_CHROME:
        if Path(chemin).exists():
            return chemin
    local = os.environ.get("LOCALAPPDATA")
    if local:
        chemin = Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe"
        if chemin.exists():
            return str(chemin)
    import shutil
    return shutil.which("chrome") or shutil.which("chrome.exe")


@outil("ouvrir_chrome", "Ouvre CHROME (ou Edge en secours) sur une page. C'est le moyen le plus fiable d'ouvrir un site.",
       {"url": {"type": "str", "obligatoire": False,
                "description": "adresse à ouvrir ; vide = nouvel onglet Google"}},
       categorie="applications", risque="moyen",
       exemple='{"outil": "ouvrir_chrome", "parametres": {"url": "https://www.google.com"}}')
def ouvrir_chrome(url: str = "") -> str:
    import subprocess
    navigateur = _trouver_chrome()
    if not navigateur:
        # repli : navigateur par défaut du système
        if ouvrir_site_web(url or "https://www.google.com"):
            return "Navigateur par défaut ouvert (Chrome introuvable)."
        return "Ni Chrome ni navigateur par défaut trouvés."
    commande = [navigateur]
    if url.strip():
        commande.append(url if url.startswith("http") else "https://" + url)
    else:
        commande.append("https://www.google.com")
    subprocess.Popen(commande)
    return f"Chrome ouvert sur {commande[-1] if len(commande) > 1 else 'un nouvel onglet'}."


@outil("ouvrir_site_web", "Ouvre un site web dans le navigateur par défaut.",
       {"url": {"type": "str", "obligatoire": True, "description": "adresse du site (https://...)"}},
       categorie="applications", risque="moyen")
def ouvrir_site_web(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    ok = webbrowser.open(url)
    return f"J'ai ouvert {url} dans le navigateur." if ok else "Le navigateur n'a pas pu être lancé."


@outil("ouvrir_panneau",
       "Ouvre le panneau web local de JIBI dans le navigateur : discussion au "
       "clavier, état, raccourcis. Tout reste sur ce PC (127.0.0.1).",
       categorie="applications", risque="faible",
       exemple="ouvre le panneau")
def ouvrir_panneau() -> str:
    import webbrowser

    from interface import panneau as module_panneau
    try:
        numero = module_panneau.demarrer()
    except Exception as e:  # noqa: BLE001
        return f"Impossible de démarrer le panneau : {str(e)[:100]}"
    if webbrowser.open(f"http://127.0.0.1:{numero}"):
        return f"Panneau ouvert dans ton navigateur (http://127.0.0.1:{numero})."
    return f"Le panneau tourne ici : http://127.0.0.1:{numero} (ouvre-le dans ton navigateur)."

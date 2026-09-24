"""Signaux locaux et mises à jour du PC.

Ce module donne à JIBI une vue de santé : batterie, mémoire, disque,
processus, réseau, erreurs JIBI, documents disponibles et version de JIBI.
La vérification winget est en lecture seule ; l'installation reste une action
à risque élevé et passe par la confirmation habituelle.
"""
from __future__ import annotations

import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from outils import outil

_CACHE: dict = {}
_VERROU = threading.Lock()
DERNIER_SIGNAL: dict = {}


def _batterie() -> str:
    from outils.systeme import batterie
    return batterie()


def _disque() -> str:
    from outils.systeme import espace_disque
    return espace_disque()


def _systeme() -> str:
    from outils.systeme import info_systeme
    return info_systeme()


def _processus() -> str:
    from outils.systeme import processus
    return processus(5)


def _reseau() -> str:
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=2):
            return "en ligne"
    except OSError:
        return "hors ligne ou pare-feu"


def _documents() -> tuple[int, list[str]]:
    from outils.fichiers import _racine
    racine = _racine()
    documents = []
    for chemin in racine.rglob("*"):
        if chemin.is_file() and chemin.suffix.lower() in (".pdf", ".docx", ".txt", ".md", ".csv"):
            documents.append(chemin.name)
    return len(documents), documents[:12]


def collecter(force: bool = False) -> dict:
    global _CACHE, DERNIER_SIGNAL
    with _VERROU:
        if not force and _CACHE and time.time() - _CACHE.get("quand_epoch", 0) < 30:
            return dict(_CACHE)
        from outils import systeme
        from jibi2 import evolution
        erreurs = 0
        journal = Path(evolution.JOURNAL)
        if journal.exists():
            erreurs = sum(1 for _ in journal.open(encoding="utf-8", errors="replace"))
        nombre_docs, docs = _documents()
        signaux = {
            "quand": time.strftime("%Y-%m-%d %H:%M:%S"),
            "quand_epoch": time.time(),
            "batterie": _batterie(), "disque": _disque(), "systeme": _systeme(),
            "processus": _processus(), "reseau": _reseau(),
            "erreurs_jibi": erreurs, "documents": nombre_docs,
            "derniers_documents": docs, "version": systeme._version_locale(),
        }
        _CACHE = signaux
        DERNIER_SIGNAL = signaux
        return dict(signaux)


@outil("tableau_signaux",
       "Analyse la santé du PC et affiche les signaux utile : batterie, mémoire, "
       "disque, réseau, processus, erreurs JIBI et documents prêts.",
       {}, categorie="systeme", exemple='{"outil": "tableau_signaux", "parametres": {}}')
def tableau_signaux() -> str:
    s = collecter()
    from outils.systeme import _normaliser_sortie
    return _normaliser_sortie(
        f"Signaux du PC — {s['quand']}\n"
        f"• {s['batterie']}\n• {s['disque']}\n• Réseau : {s['reseau']}\n"
        f"• {s['processus']}\n• Erreurs JIBI récentes : {s['erreurs_jibi']}\n"
        f"• Documents prêts : {s['documents']} ({', '.join(s['derniers_documents']) or 'aucun'})\n"
        f"• Version JIBI : {s['version']}")


def _alertes(s: dict) -> list[str]:
    alertes: list[str] = []
    batterie = str(s.get("batterie", ""))
    match = re.search(r"(\d+)\s*%", batterie)
    if match and int(match.group(1)) <= 20 and "sur secteur" not in batterie:
        alertes.append(f"Batterie faible : {batterie}")
    disque = str(s.get("disque", ""))
    match = re.search(r"(\d+)\s*Go libres", disque)
    if match and int(match.group(1)) <= 10:
        alertes.append(f"Espace disque faible : {disque}")
    if s.get("reseau") != "en ligne":
        alertes.append("Le réseau est hors ligne ou bloque.")
    return alertes


def surveiller(force: bool = False) -> str:
    signaux = collecter(force)
    alertes = _alertes(signaux)
    if not alertes:
        return "Signaux PC : aucun seuil d'alerte franchi."
    from outils.notifications import notifier_systeme
    for alerte in alertes:
        notifier_systeme("JIBI — signal PC", alerte)
    return "Signaux PC :\n" + "\n".join("• " + alerte for alerte in alertes)


@outil("surveiller_signaux",
       "Vérifie immédiatement les seuils du PC et envoie les alertes importantes "
       "(batterie, disque, réseau).", {}, categorie="systeme",
       exemple='{"outil": "surveiller_signaux", "parametres": {}}')
def surveiller_signaux() -> str:
    return surveiller()


@outil("verifier_mises_a_jour_pc",
       "Vérifie les mises à jour Windows disponibles avec winget, sans installer "
       "rien. Utilise le catalogue winget de cette machine.",
       {}, categorie="systeme", risque="moyen",
       exemple='{"outil": "verifier_mises_a_jour_pc", "parametres": {}}')
def verifier_mises_a_jour_pc() -> str:
    from jibi2 import progression
    progression.demarrer("Vérification des mises à jour PC", "Consultation winget")
    if not shutil.which("winget"):
        progression.terminer("winget indisponible", succes=False)
        return "winget n'est pas installé ou n'est pas dans le PATH."
    progression.mettre(35, "Analyse du catalogue winget")
    try:
        fait = subprocess.run(["winget", "upgrade", "--include-unknown", "--accept-source-agreements"],
                              capture_output=True, timeout=45)
        from outils.systeme import _decoder_sortie
        texte = _decoder_sortie(fait.stdout or fait.stderr).strip()
        if fait.returncode not in (0, -1978335189):  # winget parfois retourne ce code sans mise à jour
            resultat = f"winget n'a pas pu terminer la vérification : {texte[:300] or fait.returncode}"
            succes = False
        elif not texte:
            resultat = "Aucune mise à jour signalée par winget."
            succes = True
        else:
            resultat = "Mises à jour potentielles :\n" + texte[:3500]
            succes = True
    except (OSError, subprocess.TimeoutExpired) as e:
        resultat = f"Vérification winget impossible : {str(e)[:140]}"
        succes = False
    progression.terminer(resultat[:200], succes=succes)
    return resultat


@outil("installer_mise_a_jour",
       "Installe une mise à jour winget précise. Action externe : confirmation "
       "obligatoire, aucune installation automatique par l'assistant.",
       {"paquet": {"type": "str", "obligatoire": True,
                    "description": "identifiant winget, par exemple Microsoft.PowerShell"}},
       categorie="systeme", risque="eleve",
       exemple='{"outil": "installer_mise_a_jour", "parametres": {"paquet": "Microsoft.PowerShell"}}')
def installer_mise_a_jour(paquet: str) -> str:
    from jibi2 import progression
    progression.demarrer("Mise à jour PC", f"winget {paquet}")
    if not shutil.which("winget"):
        progression.terminer("winget indisponible", succes=False)
        return "winget n'est pas installé."
    if not re_plage(paquet):
        progression.terminer("Identifiant invalide", succes=False)
        return "Identifiant winget invalide."
    progression.mettre(20, "Lancement de winget")
    try:
        fait = subprocess.run(["winget", "upgrade", "--id", paquet, "--exact",
                               "--accept-package-agreements", "--accept-source-agreements"],
                              capture_output=True, timeout=300)
        from outils.systeme import _decoder_sortie
        resultat = (_decoder_sortie(fait.stdout or fait.stderr)
                    or f"winget terminé (code {fait.returncode})")[:3000]
        succes = fait.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as e:
        resultat = f"Installation impossible : {str(e)[:140]}"
        succes = False
    progression.mettre(90, "Finalisation de la mise à jour")
    progression.terminer(resultat[:200], succes=succes)
    return resultat


def re_plage(paquet: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{2,120}", (paquet or "").strip()))

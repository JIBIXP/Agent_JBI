"""Journal d'audit append-only pour les actions d'auto-amélioration.

Le CHANGELOG reste lisible par l'utilisateur, mais n'est pas une preuve :
le journal ci-dessous conserve l'ordre, l'auteur, la cible et une chaîne de
hachage. Aucun secret ni contenu de page n'y est écrit.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from typing import Any

from . import config

JOURNAL = config.DOSSIER_JOURNAL / "audit.jsonl"
_VERROU = threading.Lock()
_SECRET = re.compile(
    r"(?i)(sk-[A-Za-z0-9_-]{12,}|tvly-[A-Za-z0-9_-]{12,}|"
    r"bearer\s+[A-Za-z0-9._-]{12,}|api[_-]?key\s*[:=]\s*\S+)")


def _texte(valeur: Any, maximum: int = 600) -> str:
    texte = str(valeur or "").replace("\r", " ").replace("\n", " ")
    return _SECRET.sub("[SECRET RÉDIGÉ]", texte)[:maximum]


def _dernier_hash() -> str:
    if not JOURNAL.exists():
        return "0" * 64
    try:
        with JOURNAL.open("rb") as f:
            for ligne in reversed(f.read().splitlines()):
                if not ligne:
                    continue
                return str(json.loads(ligne.decode("utf-8")).get("hash", ""))
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return "0" * 64


def journaliser(action: str, cible: str = "", *, acteur: str = "jibi",
                details: str = "", resultat: str = "ok",
                empreinte: str = "") -> dict:
    """Ajoute une entrée et renvoie son enregistrement (jamais une exception)."""
    evenement: dict[str, Any] = {
        "quand": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "acteur": _texte(acteur, 40),
        "action": _texte(action, 100),
        "cible": _texte(cible, 300),
        "details": _texte(details),
        "resultat": _texte(resultat, 100),
        "empreinte": _texte(empreinte, 128),
        "precedent": "",
    }
    with _VERROU:
        evenement["precedent"] = _dernier_hash()
        brut = json.dumps(evenement, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        evenement["hash"] = hashlib.sha256(brut.encode("utf-8")).hexdigest()
        try:
            JOURNAL.parent.mkdir(parents=True, exist_ok=True)
            with JOURNAL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evenement, ensure_ascii=False, separators=(",", ":")) + "\n")
                f.flush()
        except OSError:
            pass
    return evenement


def lire(limit: int = 20) -> list[dict]:
    """Lit les derniers événements, sans les exposer à un outil réseau."""
    if not JOURNAL.exists():
        return []
    resultats: list[dict] = []
    try:
        lignes = JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for ligne in lignes[-max(1, min(int(limit), 200)):]:
        try:
            valeur = json.loads(ligne)
            if isinstance(valeur, dict):
                resultats.append(valeur)
        except json.JSONDecodeError:
            continue
    return list(reversed(resultats))


def verifier_chaine() -> tuple[bool, str]:
    """Vérifie que chaque hash d'audit correspond au contenu précédent."""
    if not JOURNAL.exists():
        return True, "journal vide"
    precedent = "0" * 64
    try:
        lignes = JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return False, str(e)
    for numero, ligne in enumerate(lignes, 1):
        try:
            evenement = json.loads(ligne)
            hash_enregistre = str(evenement.pop("hash", ""))
            if evenement.get("precedent") != precedent:
                return False, f"chaîne rompue à la ligne {numero}"
            brut = json.dumps(evenement, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
            if hashlib.sha256(brut.encode("utf-8")).hexdigest() != hash_enregistre:
                return False, f"empreinte invalide à la ligne {numero}"
            precedent = hash_enregistre
        except (json.JSONDecodeError, AttributeError, TypeError):
            return False, f"entrée illisible à la ligne {numero}"
    return True, f"{len(lignes)} entrée(s) vérifiée(s)"

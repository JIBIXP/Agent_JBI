"""Configuration de JIBI 2.

Lit le fichier .env à la racine du projet (aucune dépendance externe :
petit analyseur intégré). Les variables d'environnement système ont la
priorité sur le .env. Le code ne dépend JAMAIS du nom du dossier : tout
dérive de l'emplacement réel de ce fichier.
"""
from __future__ import annotations

import os
from pathlib import Path

# Racine = parent du paquet jibi2 (renommage du dossier sans conséquence).
RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DONNEES = RACINE / "donnees"
DOSSIER_FICHIERS = DOSSIER_DONNEES / "fichiers"
DOSSIER_CORBEILLE = DOSSIER_DONNEES / "corbeille"
DOSSIER_PROPOSITIONS = DOSSIER_DONNEES / "propositions"
DOSSIER_JOURNAL = DOSSIER_DONNEES / "journal"
DOSSIER_MODELES = RACINE / "modeles"
DOSSIER_VOIX = DOSSIER_MODELES / "voix"
FICHIER_BD = DOSSIER_DONNEES / "memoire.db"
FICHIER_ENV = RACINE / ".env"

DEFAUTS = {
    # --- Cerveau (Ollama, sur CPU) ----------------------------------------
    # CPU : 4b si ≥ 16 Go de RAM, sinon 2b — python docteur.py --modele
    "JIBI_LLM_MODEL": "qwen3.5:4b",
    "JIBI_LLM_URL": "http://127.0.0.1:11434",
    "JIBI_LLM_THINK": "0",                # 0 = <think> désactivé (rapide)
    "JIBI_HISTOIRE": "12",                # tours de conversation gardés
    "JIBI_NOM": "JIBI",
    # --- Voix sortante (TTS) ----------------------------------------------
    "TTS_ENGINE": "piper",                # piper | pyttsx3 | aucun
    "PIPER_MODELE": "",                   # vide = 1re voix .onnx de modeles/voix/
    # --- Voix entrante (STT) ----------------------------------------------
    "STT_ENGINE": "faster_whisper",       # faster_whisper | google | aucun
    "WHISPER_MODELE": "small",            # CPU : small = bon compromis (medium = lent)
    "WHISPER_DEVICE": "cpu",              # pas de GPU : cpu direct ("auto" essaie cuda d'abord)
    "WHISPER_COMPUTE": "int8",            # int8 = le plus rapide sur CPU
    # --- Mains-libres ------------------------------------------------------
    "JIBI_VOIX_ACTIVE": "0",              # 1 = JIBI parle ses réponses
    "JIBI_MOT_ACTIVATION": "jibi",
    "JIBI_FENETRE_SUIVI": "60",           # secondes sans redire « jibi » après une réponse
    # --- Confort -----------------------------------------------------------
    "JIBI_FLUX": "1",                     # 1 = réponse affichée mot à mot (streaming)
    "JIBI_HORAIRE_ACTIF": "1",            # 1 = workflows programmés actifs
    # --- Vision (CPU) ------------------------------------------------------
    "JIBI_VISION_MODEL": "moondream",     # léger (~1,4 Go), pensé pour le CPU
    # --- Sécurité -----------------------------------------------------------
    "CONFIRMER_RISQUES": "1",             # demander confirmation (o/n) si risque élevé
}

_cache: dict[str, str] | None = None


def _lire_env() -> dict[str, str]:
    """Fusionne : défauts < .env < variables d'environnement système."""
    global _cache
    if _cache is not None:
        return _cache
    valeurs = dict(DEFAUTS)
    if FICHIER_ENV.exists():
        for ligne in FICHIER_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, val = ligne.partition("=")
            valeurs[cle.strip()] = val.split("  #")[0].strip().strip('"').strip("'")
    for cle in valeurs:
        if cle in os.environ:
            valeurs[cle] = os.environ[cle]
    _cache = valeurs
    return valeurs


def valeur(cle: str, defaut: str = "") -> str:
    return _lire_env().get(cle, defaut)


def valeur_bool(cle: str) -> bool:
    return valeur(cle, "0").strip().lower() in ("1", "vrai", "true", "oui", "yes", "on")


def entier(cle: str, defaut: int) -> int:
    try:
        return int(valeur(cle, str(defaut)))
    except ValueError:
        return defaut


def preparer_dossiers() -> None:
    """Crée l'arborescence de données au premier lancement."""
    for dossier in (DOSSIER_DONNEES, DOSSIER_FICHIERS, DOSSIER_CORBEILLE,
                    DOSSIER_PROPOSITIONS, DOSSIER_JOURNAL, DOSSIER_VOIX):
        dossier.mkdir(parents=True, exist_ok=True)

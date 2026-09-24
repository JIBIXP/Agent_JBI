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
    # --- Autonomie d'amélioration ------------------------------------------
    # 1 = active le mode de modification ; une confirmation noyau reste
    # obligatoire tant que JIBI_AUTONOMIE_NOYAU n'est pas explicitement mis à 1.
    # La protection des secrets/données, les tests et le retour arrière restent actifs.
    "JIBI_MODIFICATION_AUTO": "0",
    # 0 = le noyau reste modifiable seulement après une confirmation explicite.
    "JIBI_AUTONOMIE_NOYAU": "0",
    # Cycle autonome facultatif, une fois par jour à l'heure indiquée.
    "JIBI_AUTONOMIE_ACTIVE": "0",
    "JIBI_AUTONOMIE_HEURE": "04:00",
    # Délai minimal entre deux activations d'outils pendant un cycle automatique.
    "JIBI_AUTONOMIE_DELAI": "21600",      # secondes (6 h)
    # Mode continu : JIBI vérifie périodiquement s'il y a une nouvelle tâche
    # "continuer" pendant que run.py est ouvert. Laissez à "0" pour le mode
    # quotidien uniquement, ou mettez "1" pour activer la boucle en arrière-plan.
    "JIBI_AUTONOMIE_CONTINU": "0",
    # Intervalle en secondes entre deux vérifications en mode continu.
    "JIBI_AUTONOMIE_INTERVALLE": "1800",   # 30 minutes
    "JIBI_AUTONOMIE_LOCAL": "1",           # code/sources envoyés au modèle local
    "JIBI_SIGNAL_ACTIF": "0",               # alertes PC quotidiennes
    "JIBI_SIGNAL_HEURE": "08:00",
    "JIBI_GEOLOCATION": "1",             # estimation réseau à la demande
    # --- Browser Use local (Chrome + Ollama, jamais le cloud) ---------------
    "JIBI_BROWSER_USE": "0",              # 1 = navigation locale activée
    "JIBI_BROWSER_MODEL": "",              # vide = JIBI_LLM_MODEL
    "JIBI_BROWSER_CHROME": "",             # vide = détection Chrome/Edge locale
    "JIBI_BROWSER_HEADLESS": "0",          # 0 = fenêtre visible
    "JIBI_BROWSER_VISION": "0",            # 1 = captures vers Ollama local
    "JIBI_BROWSER_MAX_STEPS": "12",
    "JIBI_BROWSER_TIMEOUT": "120",
    "JIBI_BROWSER_WAIT": "1.5",
    "JIBI_BROWSER_DOMAINS": "",             # vide = domaine demandé uniquement
    "JIBI_CHROME_SEARCH_BACKGROUND": "1",  # recherche Google sans focus ni fenêtre
    # --- Sécurité -----------------------------------------------------------
    "CONFIRMER_RISQUES": "1",             # demander confirmation (o/n) si risque élevé
    "CONFIRMER_DEPLACEMENT": "1",             # confirmation pour les deplacements de fichiers
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


def basculer_noyau() -> str:
    """Bascule JIBI_AUTONOMIE_NOYAU entre 0 (verrouillé) et 1 (déverrouillé).
    Retourne la nouvelle valeur sous forme de chaîne ('0' ou '1')."""
    valeur_actuelle = valeur_bool("JIBI_AUTONOMIE_NOYAU")
    nouvelle_valeur = "0" if valeur_actuelle else "1"
    env_path = FICHIER_ENV
    if env_path.exists():
        contenu = env_path.read_text(encoding="utf-8", errors="replace")
        lignes = contenu.splitlines()
        trouve = False
        nouvelles_lignes: list[str] = []
        for ligne in lignes:
            if ligne.strip().startswith("JIBI_AUTONOMIE_NOYAU"):
                nouvelles_lignes.append(
                    f"JIBI_AUTONOMIE_NOYAU={nouvelle_valeur}")
                trouve = True
            else:
                nouvelles_lignes.append(ligne)
        if not trouve:
            nouvelles_lignes.append(
                f"JIBI_AUTONOMIE_NOYAU={nouvelle_valeur}")
        env_path.write_text("\n".join(nouvelles_lignes) + "\n",
                             encoding="utf-8")
    else:
        env_path.write_text(f"JIBI_AUTONOMIE_NOYAU={nouvelle_valeur}\n",
                             encoding="utf-8")
    global _cache
    _cache = None
    return nouvelle_valeur


def statut_noyau() -> str:
    """Retourne une phrase lisible du verrouillage du noyau."""
    if valeur_bool("JIBI_AUTONOMIE_NOYAU"):
        return ("[NOYAU DÉVERROUILLÉ] Les modifications du code sont "
                "autorisées quand tu les demandes explicitement.")
    return ("[NOYAU VERROUILLÉ] Toute modification du code demande "
            "une confirmation explicite.")


def basculer_deplacement() -> str:
    """Bascule CONFIRMER_DEPLACEMENT entre 0 (auto) et 1 (confirmation)."""
    valeur_actuelle = valeur_bool("CONFIRMER_DEPLACEMENT")
    nouvelle_valeur = "0" if valeur_actuelle else "1"
    env_path = FICHIER_ENV
    if env_path.exists():
        contenu = env_path.read_text(encoding="utf-8", errors="replace")
        lignes = contenu.splitlines()
        trouve = False
        nouvelles = []
        for ligne in lignes:
            if ligne.strip().startswith("CONFIRMER_DEPLACEMENT"):
                nouvelles.append(f"CONFIRMER_DEPLACEMENT={nouvelle_valeur}")
                trouve = True
            else:
                nouvelles.append(ligne)
        if not trouve:
            nouvelles.append(f"CONFIRMER_DEPLACEMENT={nouvelle_valeur}")
        env_path.write_text("\n".join(nouvelles) + "\n", encoding="utf-8")
    global _cache
    _cache = None
    return nouvelle_valeur


def statut_deplacement() -> str:
    """Retourne le statut de la confirmation deplacement."""
    if valeur_bool("CONFIRMER_DEPLACEMENT"):
        return "[CONFIRMATION REQUISE] Deplacement avec confirmation"
    return "[AUTOMATIQUE] Deplacement sans confirmation"

"""Sortie audio (TTS) de JIBI 2 : Piper en local d'abord, pyttsx3 en repli.

- Piper : modèle .onnx + .onnx.json dans modeles/voix/ (voir docteur.py
  --installer-voix), cache WAV dans donnees/cache_voix/.
- pyttsx3 (voix Windows SAPI) : repli automatique si Piper est absent.
"""
from __future__ import annotations

import contextlib
import hashlib
import queue
import re
import threading
import urllib.request
import wave
from pathlib import Path

from jibi2 import config

_voix_piper = None           # instance PiperVoice (chargée une fois)
ERREUR_DERNIERE = ""         # dernier problème, affichable par l'interface


def voix_disponible() -> Path | None:
    """Trouve le modèle Piper à utiliser (PIPER_MODELE ou 1re voix du dossier)."""
    impose = config.valeur("PIPER_MODELE", "").strip()
    if impose:
        chemin = Path(impose)
        return chemin if chemin.exists() else None
    config.DOSSIER_VOIX.mkdir(parents=True, exist_ok=True)
    for onnx in sorted(config.DOSSIER_VOIX.glob("*.onnx")):
        if onnx.with_suffix(".onnx.json").exists():
            return onnx
    return None


def generer_wav(texte: str) -> Path:
    """Synthétise le texte en WAV (cache par empreinte). Lève en cas d'échec."""
    global _voix_piper, ERREUR_DERNIERE
    modele = voix_disponible()
    if modele is None:
        raise RuntimeError("Aucune voix Piper dans modeles/voix/ "
                           "(installe-la : python docteur.py --installer-voix)")
    cache = config.DOSSIER_DONNEES / "cache_voix"
    cache.mkdir(parents=True, exist_ok=True)
    empreinte = hashlib.md5((str(modele.name) + "|" + texte).encode("utf-8"),
                            usedforsecurity=False).hexdigest()
    chemin = cache / f"jibi_{empreinte}.wav"
    if chemin.exists() and chemin.stat().st_size > 100:
        return chemin
    try:
        from piper import PiperVoice
    except ImportError as e:
        ERREUR_DERNIERE = "Le paquet piper-tts n'est pas installé (pip install piper-tts)."
        raise RuntimeError(ERREUR_DERNIERE) from e
    if _voix_piper is None:
        _voix_piper = PiperVoice.load(str(modele))
    with wave.open(str(chemin), "wb") as f:
        _voix_piper.synthesize_wav(texte, f)
    return chemin


def jouer_wav(chemin: Path, attendre: bool = True) -> bool:
    """Joue un WAV : winsound (Windows) puis sounddevice (autres)."""
    import sys
    if sys.platform == "win32":
        try:
            import winsound
            drapeaux = winsound.SND_FILENAME | (winsound.SND_SYNC if attendre else winsound.SND_ASYNC)
            winsound.PlaySound(str(chemin), drapeaux)
            return True
        except Exception:
            pass
    try:
        import numpy as np
        import sounddevice as sd
        with wave.open(str(chemin), "rb") as f:
            donnees = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
            frequence = f.getframerate()
        sd.play(donnees, frequence)
        if attendre:
            sd.wait()
        return True
    except Exception as e:
        global ERREUR_DERNIERE
        ERREUR_DERNIERE = f"Lecture audio impossible : {e}"
        return False


def arreter() -> None:
    """ Coupe la lecture en cours (au mieux)."""
    import sys
    if sys.platform == "win32":
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass


def parler(texte: str, attendre: bool = False) -> bool:
    """Fait parler JIBI. Renvoie True si un moteur a fonctionné."""
    global ERREUR_DERNIERE
    moteur = config.valeur("TTS_ENGINE", "piper").lower()
    if moteur == "aucun" or not texte.strip():
        return False
    if moteur == "piper":
        try:
            return jouer_wav(generer_wav(texte), attendre=attendre)
        except Exception as e:
            ERREUR_DERNIERE = str(e)
    if moteur in ("pyttsx3", "piper"):          # repli pyttsx3 pour piper aussi
        try:
            import pyttsx3
            moteur_voix = pyttsx3.init()
            moteur_voix.say(texte)
            moteur_voix.runAndWait()
            return True
        except Exception as e:
            ERREUR_DERNIERE = f"pyttsx3 indisponible : {e}"
    return False


# ─────────────────────────────────────────────── catalogue de voix (Piper) ──
# Voix françaises officielles du dépôt rhasspy/piper-voices. « tom » = homme.
CATALOGUE_VOIX: dict[str, dict] = {
    "siwis":  {"sexe": "femme", "qualite": "medium", "fichier": "fr_FR-siwis-medium"},
    "tom":    {"sexe": "homme", "qualite": "medium", "fichier": "fr_FR-tom-medium"},
    "upmc":   {"sexe": "homme", "qualite": "medium", "fichier": "fr_FR-upmc-medium"},
    "gilles": {"sexe": "homme", "qualite": "low",    "fichier": "fr_FR-gilles-low"},
}
_BASE_PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR"


def url_modele(nom: str) -> tuple[str, str]:
    """(url_onnx, url_json) d'une voix du catalogue."""
    v = CATALOGUE_VOIX[nom]
    dossier = f"{_BASE_PIPER}/{nom}/{v['qualite']}"
    return (f"{dossier}/{v['fichier']}.onnx", f"{dossier}/{v['fichier']}.onnx.json")


def voix_installees() -> list[str]:
    """Noms des voix présentes dans modeles/voix/ (avec leur .json)."""
    if not config.DOSSIER_VOIX.exists():
        return []
    return sorted(p.name.removesuffix(".onnx")
                  for p in config.DOSSIER_VOIX.glob("*.onnx")
                  if p.with_suffix(".onnx.json").exists())


def voix_actuelle() -> str:
    modele = voix_disponible()
    return modele.name.removesuffix(".onnx") if modele else "aucune"


def recharger() -> None:
    """Force le rechargement du modèle Piper au prochain parler (changement de voix)."""
    global _voix_piper
    _voix_piper = None


def telecharger_voix(nom: str) -> Path:
    """Télécharge une voix du catalogue dans modeles/voix/. Lève si échec."""
    if nom not in CATALOGUE_VOIX:
        raise ValueError(f"voix inconnue : {nom}")
    url_onnx, url_json = url_modele(nom)
    config.DOSSIER_VOIX.mkdir(parents=True, exist_ok=True)
    v = CATALOGUE_VOIX[nom]
    cible = config.DOSSIER_VOIX / f"{v['fichier']}.onnx"
    for url, destination in ((url_json, cible.with_suffix(".onnx.json")),
                             (url_onnx, cible)):
        if destination.exists() and destination.stat().st_size > 1000:
            continue
        temporaire = destination.with_suffix(destination.suffix + ".en_cours")
        with urllib.request.urlopen(url, timeout=60) as reponse,                 temporaire.open("wb") as sortie:
            while True:
                morceau = reponse.read(1 << 20)
                if not morceau:
                    break
                sortie.write(morceau)
        temporaire.rename(destination)
    if cible.stat().st_size < 1_000_000:
        raise RuntimeError("fichier voix trop petit, téléchargement suspect")
    return cible


# ──────────────────────────────────────────────── parole au fil de l'eau ──
_RE_PHRASE = re.compile(r"(.+?[.!?…])\s+", re.DOTALL)


def extraire_phrases(tampon: str) -> tuple[list[str], str]:
    """Découpe un tampon en phrases complètes. Renvoie (phrases, reste)."""
    phrases: list[str] = []
    texte = tampon.strip()
    while True:
        m = _RE_PHRASE.match(texte)
        if m is None:
            break
        phrases.append(m.group(1))
        texte = texte[m.end():]
    if "\n" in texte:                       # retour à la ligne = fin de phrase
        morceaux = [x.strip() for x in texte.split("\n") if x.strip()]
        if len(morceaux) > 1:
            phrases.extend(morceaux[:-1])
            texte = morceaux[-1]
    return phrases, texte


class LecteurPhrases:
    """Fait parler les phrases AU FIL DE L'EAU, pendant que le modèle écrit.

    On alimente avec les morceaux du flux (alimenter), on clôt (terminer) :
    chaque phrase complète est synthétisée puis dite immédiatement, dans
    l'ordre (un seul worker). Premier mot audible en ~2 s au lieu d'attendre
    la réponse entière + sa synthèse.
    """

    def __init__(self, sur_debut=None) -> None:
        self._file: queue.Queue = queue.Queue()
        self._tampon = ""
        self._thread: threading.Thread | None = None
        self._sur_debut = sur_debut
        self._annonce = False

    def _demarrer(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._boucle, daemon=True)
            self._thread.start()

    def alimenter(self, morceau: str) -> None:
        self._tampon += morceau
        phrases, self._tampon = extraire_phrases(self._tampon)
        for phrase in phrases:
            self._file.put(phrase)
            self._demarrer()

    def terminer(self) -> None:
        """Clôt le flux : dit ce qui reste puis s'arrête proprement."""
        reste = self._tampon.strip()
        self._tampon = ""
        if reste:
            self._file.put(reste)
        self._file.put(None)
        self._demarrer()

    def couper(self) -> None:
        """Silence immédiat (réponse corrigée, arrêt demandé…)."""
        while True:
            try:
                self._file.get_nowait()
            except queue.Empty:
                break
        self._file.put(None)
        arreter()

    def attendre(self) -> None:
        if self._thread is not None:
            self._thread.join(timeout=300)

    def _boucle(self) -> None:
        while True:
            phrase = self._file.get()
            if phrase is None:
                break
            if not self._annonce:
                self._annonce = True
                if self._sur_debut:
                    with contextlib.suppress(Exception):
                        self._sur_debut()
            with contextlib.suppress(Exception):
                parler(phrase, attendre=True)


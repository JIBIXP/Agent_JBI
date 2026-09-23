"""Entrée audio (STT) de JIBI 2 : faster-whisper en local, Google en repli.

La transcription est en français. Le modèle Whisper est chargé une seule
fois ; « auto » essaie le GPU (cuda/float16) puis retombe sur CPU (int8).
"""
from __future__ import annotations

import tempfile
import time
import wave
from pathlib import Path

from jibi2 import config

_modele_whisper = None
ERREUR_DERNIERE = ""


def micro_disponible() -> bool:
    try:
        import sounddevice as sd  # type: ignore[import-not-found]
        entree = sd.default.device[0] if sd.default.device else None
        if entree is None:
            entree = sd.query_devices(kind="input")  # type: ignore[call-arg]
        return entree is not None
    except Exception:
        return False


def _charger_whisper():
    """Charge (une fois) le modèle Whisper selon WHISPER_* du .env."""
    global _modele_whisper, ERREUR_DERNIERE
    if _modele_whisper is not None:
        return _modele_whisper
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    except ImportError:
        ERREUR_DERNIERE = "Le paquet faster-whisper n'est pas installé (pip install faster-whisper)."
        return None
    nom = config.valeur("WHISPER_MODELE", "small")
    device = config.valeur("WHISPER_DEVICE", "auto")
    compute = config.valeur("WHISPER_COMPUTE", "auto")
    if device == "auto":
        try:
            _modele_whisper = WhisperModel(nom, device="cuda",
                                           compute_type="float16" if compute == "auto" else compute)
        except Exception:
            _modele_whisper = WhisperModel(nom, device="cpu",
                                           compute_type="int8" if compute == "auto" else compute)
    else:
        _modele_whisper = WhisperModel(nom, device=device,
                                       compute_type=compute if compute != "auto" else "int8")
    return _modele_whisper


def transcrire(chemin_audio: str | Path) -> str:
    """Transforme un fichier audio en texte (français)."""
    global ERREUR_DERNIERE
    chemin_audio = str(chemin_audio)
    moteur = config.valeur("STT_ENGINE", "faster_whisper").lower()
    if moteur == "aucun":
        ERREUR_DERNIERE = "STT désactivé (STT_ENGINE=aucun)."
        return ""
    if moteur != "google":
        modele = _charger_whisper()
        if modele is not None:
            try:
                segments, _ = modele.transcribe(chemin_audio, language="fr")
                return " ".join(s.text.strip() for s in segments).strip()
            except Exception as e:
                ERREUR_DERNIERE = f"Whisper a échoué : {e}"
    # Repli (ou choix) : reconnaissance Google via SpeechRecognition si dispo.
    try:
        import speech_recognition as sr  # type: ignore[import-not-found]
        with sr.AudioFile(chemin_audio) as source:
            audio = sr.Recognizer().record(source)
        return sr.Recognizer().recognize_google(audio, language="fr-FR")
    except Exception as e:
        ERREUR_DERNIERE = ERREUR_DERNIERE or f"Repli Google indisponible : {e}"
        return ""


def ecouter_phrase(timeout: float = 8.0, silence: float = 1.2, limite: float = 15.0) -> str:
    """Enregistre au micro jusqu'au silence et renvoie la phrase transcrite.

    Renvoie "" si rien n'a été dit ou si le micro/STT est indisponible.
    """
    global ERREUR_DERNIERE
    try:
        import numpy as np
        import sounddevice as sd  # type: ignore[import-not-found]
    except ImportError:
        ERREUR_DERNIERE = "sounddevice/numpy requis pour le micro (pip install sounddevice numpy)."
        return ""
    frequence = 16000
    morceaux: list[bytes] = []
    a_parle = False
    dernier_bruit = time.time()
    debut = time.time()
    SEUIL = 350  # niveau RMS considéré comme de la parole
    try:
        with sd.InputStream(samplerate=frequence, channels=1, dtype="int16", blocksize=800) as flux:
            while True:
                donnees, _ = flux.read(800)
                morceaux.append(bytes(donnees))
                rms = float(np.sqrt(np.mean(np.square(donnees.astype(float)))))
                if rms > SEUIL:
                    a_parle = True
                    dernier_bruit = time.time()
                maintenant = time.time()
                if a_parle and maintenant - dernier_bruit > silence:
                    break
                if not a_parle and maintenant - debut > timeout:
                    return ""
                if maintenant - debut > limite:
                    break
    except Exception as e:
        ERREUR_DERNIERE = f"Micro indisponible : {e}"
        return ""
    if not a_parle:
        return ""
    brut = b"".join(morceaux)
    temporaire = Path(tempfile.gettempdir()) / f"jibi_ecoute_{int(time.time())}.wav"
    with wave.open(str(temporaire), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(frequence)
        f.writeframes(brut)
    try:
        return transcrire(temporaire)
    finally:
        temporaire.unlink(missing_ok=True)


def dicter(mot_fin: str = "envoie", max_secondes: float = 180.0, on_partiel=None) -> str:
    """Dictée en continu : accumule des phrases jusqu'au mot « envoie ».

    Entre chaque segment, une pause de 1,2 s est tolérée (le temps de
    respirer). Dis « envoie » (mot_fin) pour terminer — ce mot est retiré
    du texte. on_partiel(texte_cumulé) est appelé après chaque segment
    (pour l'afficher dans la zone de saisie).
    """
    global ERREUR_DERNIERE
    morceaux: list[str] = []
    debut = time.time()
    while time.time() - debut < max_secondes:
        reste = max(5.0, max_secondes - (time.time() - debut))
        segment = ecouter_phrase(timeout=9.0, silence=1.3, limite=min(reste, 60.0))
        if not segment:
            continue
        bas = segment.lower().strip(" ,.!?")
        if bas == mot_fin or bas.endswith(" " + mot_fin) or bas == mot_fin + " jibi":
            break
        morceaux.append(segment)
        if on_partiel is not None:
            on_partiel(" ".join(morceaux))
    return " ".join(morceaux).strip()
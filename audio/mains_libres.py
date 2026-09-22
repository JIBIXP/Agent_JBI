"""Boucle mains-libres de JIBI 2 : « jibi, … » → commande → réponse parlée.

Fonctionnement :
- JIBI écoute par courtes fenêtres et transcrit (faster-whisper local) ;
- la phrase doit contenir le mot d'activation (JIBI_MOT_ACTIVATION) ;
- après chaque réponse, une FENÊTRE DE SUIVI (JIBI_FENETRE_SUIVI secondes,
  défaut 60) permet d'enchaîner sans redire « jibi » — comme une
  conversation. Passé ce délai, il faut rappeler JIBI.
- « stop » / « au revoir » pendant la fenêtre termine la session.

(V1 sans wake-word neuronal : la détection se fait sur la transcription.
 Un modèle openWakeWord dédié pourrait remplacer ça plus tard.)
"""
from __future__ import annotations

import threading
import time

from audio import ecoute, parole, wake
from jibi2 import config

MOTS_SORTIE = ("stop", "au revoir", "arrête-toi", "c'est tout", "merci c'est tout")


def _traiter_commande(assistant, commande: str) -> bool:
    """Répond à une commande vocale. Renvoie False si JIBI doit s'arrêter."""
    print(f"   🗣️  toi : {commande}")
    debut = time.time()
    reponse = assistant.repondre(commande)
    print(f"   🤖 JIBI : {reponse['reponse']}   ({time.time() - debut:.1f} s)")
    parole.parler(reponse["reponse"])
    return True


def _boucle_neuronale(assistant, mot: str, stop: threading.Event) -> None:
    """Wake-word neuronal : openWakeWord détecte « jibi », puis dictée."""
    while not stop.is_set():
        if not wake.ecouter_mot():
            continue
        commande = ecoute.ecouter_phrase(timeout=7.0, silence=1.4).strip().lower()
        if not commande:
            parole.parler("Oui ?")
            continue
        if commande in MOTS_SORTIE:
            parole.parler("À bientôt !")
            return
        _traiter_commande(assistant, commande)


def _boucle_transcription(assistant, mot: str, fenetre: int, stop: threading.Event) -> None:
    """Détection par transcription : « jibi » lance une fenêtre de suivi."""
    actif_jusqua = 0.0
    while not stop.is_set():
        phrase = ecoute.ecouter_phrase(timeout=10.0, silence=1.4)
        if not phrase:
            continue
        bas = phrase.lower()
        if mot in bas:
            commande = bas.split(mot, 1)[1].strip(" ,.!?")
            actif_jusqua = time.time() + fenetre
        elif time.time() < actif_jusqua:
            commande = bas.strip(" ,.!?")
        else:
            continue                                  # parlé sans « jibi », hors fenêtre
        if not commande:
            parole.parler("Oui ?")
            commande = ecoute.ecouter_phrase(timeout=6.0, silence=1.2).strip().lower()
            if not commande:
                continue
        if commande in MOTS_SORTIE:
            parole.parler("À bientôt !")
            return
        if _traiter_commande(assistant, commande):
            actif_jusqua = time.time() + fenetre


def boucle(assistant, stop: threading.Event | None = None) -> None:
    """Tourne jusqu'au stop (Ctrl+C). Nécessite micro + STT + (TTS conseillé)."""
    stop = stop or threading.Event()
    mot = config.valeur("JIBI_MOT_ACTIVATION", "jibi").lower()
    fenetre = max(10, config.entier("JIBI_FENETRE_SUIVI", 60))
    if not ecoute.micro_disponible():
        print("❌ Aucun micro détecté — mode mains-libres impossible.")
        return
    if wake.disponible():
        print(f"🎧 Mains-libres ACTIVÉS (wake-word neuronal « {mot} »). (Ctrl+C pour sortir)")
        if not parole.parler("Mains libres activés. Dis " + mot + " pour m'appeler."):
            print("   (voix indisponible : " + (parole.ERREUR_DERNIERE or "aucun moteur") + ")")
        _boucle_neuronale(assistant, mot, stop)
        return
    print(f"🎧 Mains-libres actifs (détection par transcription — installe openwakeword "
          f"+ un modèle dans modeles/wake/ pour la détection neuronale). "
          f"Dis « {mot} » suivi de ta demande ; tu peux ensuite enchaîner sans le "
          f"répéter pendant {fenetre} s. (Ctrl+C pour sortir)")
    if not parole.parler(f"Mains libres activés. Dis {mot} suivi de ta demande."):
        print("   (voix indisponible : " + (parole.ERREUR_DERNIERE or "aucun moteur") + ")")
    _boucle_transcription(assistant, mot, fenetre, stop)

    actif_jusqua = 0.0
    while not stop.is_set():
        phrase = ecoute.ecouter_phrase(timeout=10.0, silence=1.4)
        if not phrase:
            continue
        bas = phrase.lower()
        if mot in bas:
            commande = bas.split(mot, 1)[1].strip(" ,.!?")
            actif_jusqua = time.time() + fenetre
        elif time.time() < actif_jusqua:
            commande = bas.strip(" ,.!?")
        else:
            continue                                  # parlé sans « jibi », hors fenêtre
        if not commande:
            parole.parler("Oui ?")
            commande = ecoute.ecouter_phrase(timeout=6.0, silence=1.2).strip().lower()
            if not commande:
                continue
        if commande in MOTS_SORTIE:
            parole.parler("À bientôt !")
            print("👋 Session mains-libres terminée.")
            break
        print(f"   🗣️  toi : {commande}")
        debut = time.time()
        reponse = assistant.repondre(commande)
        print(f"   🤖 JIBI : {reponse['reponse']}   ({time.time() - debut:.1f} s)")
        parole.parler(reponse["reponse"])
        actif_jusqua = time.time() + fenetre

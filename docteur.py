#!/usr/bin/env python3
"""Docteur de JIBI 2 — vérifie tout et dit quoi corriger, en français.

  python docteur.py                     → bilan complet (✅/⚠️/❌)
  python docteur.py --modele            → quel modèle choisir selon ta machine
  python docteur.py --installer-voix    → télécharge la voix Piper (fr_FR-siwis, ~63 Mo)
  python docteur.py --installer-voix tom / upmc / mls / siwis-low
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jibi2 import config

VOIX = {                      # nom → qualité dans rhasspy/piper-voices
    "siwis": "medium",        # défaut : voix féminine, naturelle
    "siwis-low": "low",
    "tom": "medium",
    "upmc": "medium",
    "mls": "medium",
}
BASE_VOIX = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR"

problemes: list[str] = []


def ligne(statut: str, message: str) -> None:
    icone = {"ok": "✅", "avert": "⚠️ ", "erreur": "❌", "info": "  "}[statut]
    print(f" {icone} {message}")
    if statut == "erreur":
        problemes.append(message)


def vram_go() -> int:
    """Mémoire vidéo de la carte NVIDIA, 0 si aucune."""
    if shutil.which("nvidia-smi"):
        try:
            sortie = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10).stdout.strip()
            return int(int(sortie.splitlines()[0]) / 1024)
        except Exception:
            pass
    return 0


def ram_go() -> int:
    if sys.platform == "win32":
        try:
            import ctypes
            class _M(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _M()
            m.dwLength = ctypes.sizeof(_M)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int(m.ullTotalPhys / 2**30)
        except Exception:
            return 0
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            return int(int(f.readline().split()[1]) / 2**20)
    except Exception:
        return 0


def conseiller_modele() -> str:
    v = vram_go()
    r = ram_go()
    if v >= 10:
        return ("GPU 10 Go+ → qwen3.5:9b conseillé (qualité supérieure, ~6,6 Go). "
                "ollama pull qwen3.5:9b puis JIBI_LLM_MODEL=qwen3.5:9b dans .env")
    if v >= 6:
        return ("GPU 6-10 Go → qwen3.5:4b (rapide, ~3,4 Go). C'est déjà le réglage par défaut.")
    if v >= 1:
        return ("Petit GPU → qwen3.5:4b sur CPU ; garde WHISPER_MODELE=small.")
    if r >= 16:
        return ("Pas de GPU mais 16 Go+ de RAM → qwen3.5:4b tournera sur CPU "
                "(réponses plus lentes qu'en GPU, ça reste correct).")
    return ("Machine modeste → qwen3.5:2b conseillé (~2,7 Go) : "
            "ollama pull qwen3.5:2b puis JIBI_LLM_MODEL=qwen3.5:2b dans .env")


def installer_voix(nom: str) -> int:
    qualite = VOIX.get(nom)
    if qualite is None:
        print(f"Voix inconnue « {nom} ». Choix : {', '.join(VOIX)}")
        return 2
    base = f"{BASE_VOIX}/{nom}/{qualite}/fr_FR-{nom}-{qualite}"
    config.DOSSIER_VOIX.mkdir(parents=True, exist_ok=True)
    for extension in (".onnx", ".onnx.json"):
        url = base + extension
        destination = config.DOSSIER_VOIX / f"fr_FR-{nom}-{qualite}{extension}"
        if destination.exists() and destination.stat().st_size > 1000:
            print(f" ✅ déjà là : {destination.name}")
            continue
        print(f" ⏳ téléchargement {url} …")
        try:
            urllib.request.urlretrieve(url, destination)
            taille = destination.stat().st_size / 2**20
            print(f" ✅ {destination.name} ({taille:.1f} Mo)")
        except Exception as e:
            print(f" ❌ échec : {e}")
            return 1
    print("\nVoix prête. TTS_ENGINE=piper dans le .env, et c'est parti.")
    return 0


def bilan() -> int:
    print("── JIBI 2, visite médicale ──────────────────────────────")
    print(f"  Python {platform.python_version()} sur {platform.system()} {platform.release()}")
    if sys.version_info < (3, 10):
        ligne("erreur", f"Python 3.10+ requis (tu as {platform.python_version()}).")
    else:
        ligne("ok", f"Python {platform.python_version()}")

    # Dépendances
    REQUIS = {"piper-tts": ("piper", "voix locale (TTS_ENGINE=piper)"),
              "sounddevice": ("sounddevice", "haut-parleur + micro"),
              "numpy": ("numpy", "requis par sounddevice/whisper")}
    UTILES = {"faster-whisper": ("faster_whisper", "micro local (STT_ENGINE=faster_whisper)"),
              "pyttsx3": ("pyttsx3", "voix de secours Windows"),
              "SpeechRecognition": ("speech_recognition", "repli micro en ligne")}
    for nom_paquet, (module, role) in {**REQUIS, **UTILES}.items():
        try:
            __import__(module)
            ligne("ok", f"{nom_paquet} installé ({role})")
        except ImportError:
            ligne("erreur" if nom_paquet in REQUIS else "avert",
                  f"{nom_paquet} ABSENT ({role}) → pip install {nom_paquet}")

    # Configuration
    config.preparer_dossiers()
    if config.FICHIER_ENV.exists():
        ligne("ok", f".env lu — modèle {config.valeur('JIBI_LLM_MODEL')}, "
                    f"TTS {config.valeur('TTS_ENGINE')}, STT {config.valeur('STT_ENGINE')}, "
                    f"code autonome {'oui' if config.valeur_bool('JIBI_MODIFICATION_AUTO') else 'non'}")
    else:
        ligne("avert", "Pas de .env : les valeurs par défaut sont utilisées "
                       "(copie .env.exemple si tu veux les personnaliser).")

    # Ollama
    from jibi2.llm import ClientLLM
    client = ClientLLM()
    ok, modeles, version = client.etat(force=True)
    if not ok:
        ligne("erreur", f"Ollama ne répond pas sur {client.url} — lance Ollama (icône ou `ollama serve`).")
    else:
        if not version:
            # les Ollama récents ne donnent plus la version sur /api/tags :
            # on interroge l'endpoint dédié /api/version.
            try:
                with urllib.request.urlopen(f"{client.url}/api/version", timeout=4) as rep:
                    version = str(json.loads(rep.read().decode("utf-8")).get("version", ""))
            except Exception:
                version = ""
        majuscule = tuple(int(x) for x in (version or "0.0").split(".")[:2]) if version else (0, 0)
        ligne("ok", (f"Ollama {version}" if version else "Ollama (version non indiquée)")
              + f" joignable, {len(modeles)} modèle(s)")
        if version and majuscule < (0, 12):
            ligne("avert", "Ollama < 0.12 : mets à jour pour qwen3.5 (outil + think).")
        elif not version:
            ligne("avert", "Version d'Ollama inconnue — si elle est plus vieille que 0.12, "
                           "mets-le à jour (ollama.com) pour qwen3.5 (outil + think).")
        if client.modele_present():
            ligne("ok", f"Modèle {client.modele} présent")
        else:
            ligne("erreur", f"Modèle {client.modele} absent →  ollama pull {client.modele}")

    # Matériel / conseil
    v, r = vram_go(), ram_go()
    if v:
        ligne("info", f"GPU NVIDIA détecté : {v} Go de VRAM, {r} Go de RAM")
    else:
        ligne("info", f"Pas de GPU NVIDIA détecté — {r} Go de RAM")
    print(f" →  {conseiller_modele()}")

    # Voix
    from audio.parole import voix_disponible
    voix = voix_disponible()
    if voix:
        ligne("ok", f"Voix Piper prête : {voix.name}")
    else:
        ligne("avert", "Aucune voix Piper dans modeles/voix/ → python docteur.py --installer-voix")

    # Cohérence CPU/GPU
    if v == 0 and config.valeur("WHISPER_DEVICE", "cpu") == "cuda":
        ligne("avert", "WHISPER_DEVICE=cuda mais aucun GPU → mets WHISPER_DEVICE=cpu "
                       "et WHISPER_COMPUTE=int8 dans le .env")
    if v == 0 and config.valeur("WHISPER_MODELE", "small") == "medium":
        ligne("avert", "whisper medium est TRÈS lent sans GPU → WHISPER_MODELE=small conseillé")

    # Vision (CPU)
    try:
        import PIL  # noqa: F401
        ligne("ok", "pillow installé (vision d'écran)")
        vision_ok = any(m.startswith(config.valeur("JIBI_VISION_MODEL", "moondream"))
                        for m in modeles)
        if v == 0:
            if vision_ok:
                ligne("ok", f"Modèle de vision CPU prêt : {config.valeur('JIBI_VISION_MODEL')}")
            else:
                ligne("avert", f"Vision : « ollama pull {config.valeur('JIBI_VISION_MODEL', 'moondream')} » "
                               "conseillé (léger, prévu pour le CPU)")
        else:
            ligne("info", f"GPU détecté — vision : {config.valeur('JIBI_VISION_MODEL')} ira aussi")
    except ImportError:
        ligne("avert", "pillow ABSENT (vision d'écran) → pip install pillow")

    # Wake-word neuronal (optionnel)
    from audio import wake
    if wake.disponible():
        ligne("ok", "Wake-word neuronal prêt (openwakeword + modèle dans modeles/wake/)")
    else:
        ligne("info", "Wake neuronal non installé — détection par transcription active "
                      "(pip install openwakeword + modèle dans modeles/wake/ pour le mode neuronal)")

    # Micro
    try:
        from audio.ecoute import micro_disponible
        if micro_disponible():
            ligne("ok", "Micro détecté")
        else:
            ligne("avert", "Aucun micro détecté (dictée et mains-libres indisponibles)")
    except Exception as e:
        ligne("avert", f"Micro non testable : {e}")

    # Outils
    from outils import OUTILS
    par_risque = {}
    for o in OUTILS.values():
        par_risque[o.risque] = par_risque.get(o.risque, 0) + 1
    ligne("ok", f"{len(OUTILS)} outils chargés (" +
                ", ".join(f"{k} : {n}" for k, n in sorted(par_risque.items())) + ")")

    print("─────────────────────────────────────────────────────────")
    if problemes:
        print(f"❌ {len(problemes)} problème(s) à corriger (voir ci-dessus).")
        return 1
    print("✅ Rien de bloquant — lance :  python run.py   (ou --console, ou --mains-libres)")
    return 0


def _ecrire_env(cle: str, valeur: str) -> None:
    """Met à jour UNE ligne du .env sans toucher au reste (données sacrées)."""
    chemin = config.RACINE / ".env"
    lignes = (chemin.read_text(encoding="utf-8").splitlines()
              if chemin.exists() else [])
    nouveau = f"{cle}={valeur}"
    for i, ligne in enumerate(lignes):
        if ligne.split("=", 1)[0].strip() == cle:
            lignes[i] = nouveau
            break
    else:
        lignes.append(nouveau)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _bench_modele(modele: str) -> tuple[float, float]:
    """(secondes d'un appel chaud, tokens/s de génération) d'un modèle."""
    import json as module_json
    import time as module_temps

    from jibi2.llm import ClientLLM

    client = ClientLLM(modele=modele)
    message = [{"role": "user",
                "content": "Réponds en une seule phrase courte : que sais-tu faire ?"}]
    requete = urllib.request.Request(
        client.url + "/api/chat",
        data=module_json.dumps({"model": modele, "messages": message,
                                "stream": False, "think": False,
                                "keep_alive": -1}).encode(),
        headers={"Content-Type": "application/json"})
    debut = module_temps.perf_counter()
    with urllib.request.urlopen(requete, timeout=600) as reponse:
        donnees = module_json.loads(reponse.read().decode())
    duree = module_temps.perf_counter() - debut
    jetons = donnees.get("eval_count") or 0
    duree_gen = (donnees.get("eval_duration") or 1) / 1e9
    return duree, (jetons / duree_gen if duree_gen else 0)


def bench_vitesse(adopte: bool = False) -> int:
    """Chronomètre le cerveau RÉEL de JIBI sur cette machine.

    Mesure : le 1er appel (chargement du modèle compris), l'appel suivant
    (la vitesse vécue), la génération en tokens/s et le pré-remplissage
    (le temps à RELIRE tout le prompt — le tueur de latence sur CPU).
    """

    from jibi2.llm import ClientLLM

    client = ClientLLM()
    joignable, installes, _version = client.etat(force=True)
    if not joignable:
        print("❌ Ollama injoignable — lance Ollama puis réessaie.")
        return 1
    modele = client.modele
    message = [{"role": "user",
                "content": "Réponds en une seule phrase courte : que sais-tu faire ?"}]

    def un_tour():
        duree, _vitesse = _bench_modele(modele)
        return duree

    def un_tour_complet() -> tuple[float, dict]:
        import json as module_json2
        import time as module_temps2
        requete = urllib.request.Request(
            client.url + "/api/chat",
            data=module_json2.dumps({"model": modele, "messages": message,
                                     "stream": False, "think": False,
                                     "keep_alive": -1}).encode(),
            headers={"Content-Type": "application/json"})
        debut = module_temps2.perf_counter()
        with urllib.request.urlopen(requete, timeout=600) as reponse:
            donnees = module_json2.loads(reponse.read().decode())
        return module_temps2.perf_counter() - debut, donnees

    print(f"⏱️  Benchmark de {modele} (2 appels, le 1er charge le modèle)…")
    t_froid, _ = un_tour_complet()
    t_chaud, donnees = un_tour_complet()
    jetons = donnees.get("eval_count") or 0
    duree_gen = (donnees.get("eval_duration") or 1) / 1e9
    prefill_jetons = donnees.get("prompt_eval_count") or 0
    duree_prefill = (donnees.get("prompt_eval_duration") or 1) / 1e9
    vitesse_gen = jetons / duree_gen if duree_gen else 0
    vitesse_prefill = prefill_jetons / duree_prefill if duree_prefill else 0
    print(f"   1er appel (froid) : {t_froid:.1f} s  ← chargement du modèle compris")
    print(f"   appel suivant     : {t_chaud:.1f} s  ← la vitesse vécue au quotidien")
    print(f"   génération        : {vitesse_gen:.1f} tokens/s ({jetons} tokens)")
    print(f"   pré-remplissage   : {vitesse_prefill:.0f} tokens/s "
          f"({prefill_jetons} tokens de prompt relus)")
    print()
    print("Lecture honnête :")
    if vitesse_gen and vitesse_gen < 6:
        print("   ⚠️ Moins de 6 tokens/s : le levier n°1 est le modèle 2b (≈2× plus rapide) :")
        print("      ollama pull qwen3.5:2b   puis   JIBI_LLM_MODEL=qwen3.5:2b dans le .env")
    if vitesse_gen and 6 <= vitesse_gen < 12:
        print("   ⚠️ Vitesse moyenne : garde tes messages courts et pense au 2b si ça traîne.")
    if vitesse_gen and vitesse_gen >= 12:
        print("   ✅ Génération saine — la latence restante vient surtout du 1er son (Piper).")
    if prefill_jetons >= 1500:
        print("   ⚠️ Prompt volumineux : fais « nouvelle session » de temps en temps ;")
        print("      JIBI compresse déjà l'historique, mais une session fraîche aide toujours.")

    if not adopte:
        return 0
    # ---- mode --adopte : chronomètre tous les qwen3.5 installés, adopte le plus rapide
    candidats = [m for m in installes if m.startswith("qwen3.5")]
    if len(candidats) < 2:
        print("\n--adopte : il faut au moins 2 modèles qwen3.5 installés pour comparer.")
        print("   Commence par :  ollama pull qwen3.5:2b")
        return 0
    print(f"\n🏁 Comparaison de {', '.join(candidats)} (chaque chargement peut prendre 1-2 min)…")
    resultats = {}
    for candidat in candidats:
        print(f"   ⏱️  {candidat}…", flush=True)
        duree, vitesse = _bench_modele(candidat)
        resultats[candidat] = (duree, vitesse)
        print(f"      appel chaud : {duree:.1f} s — génération : {vitesse:.1f} tokens/s")
    vainqueur = max(resultats, key=lambda m: resultats[m][1])
    print(f"\n🏆 Le plus rapide : {vainqueur} ({resultats[vainqueur][1]:.1f} tokens/s)")
    if vainqueur == modele:
        print("   Ton .env pointe déjà sur le meilleur : rien à changer.")
        return 0
    _ecrire_env("JIBI_LLM_MODEL", vainqueur)
    print(f"   ✅ .env mis à jour : JIBI_LLM_MODEL={vainqueur} "
          "(relance JIBI pour en profiter).")
    return 0


def principal() -> int:
    parseur = argparse.ArgumentParser(description="Docteur de JIBI 2")
    parseur.add_argument("--modele", action="store_true", help="conseil de modèle seulement")
    parseur.add_argument("--vitesse", action="store_true",
                         help="chronomètre JIBI : chargement, pré-remplissage, tokens/s")
    parseur.add_argument("--adopte", action="store_true",
                         help="avec --vitesse : chronomètre TOUS les qwen3.5 installés "
                              "et écrit le plus rapide dans le .env")
    parseur.add_argument("--installer-voix", nargs="?", const="siwis", metavar="NOM",
                         help="télécharge une voix Piper (siwis, siwis-low, tom, upmc, mls)")
    parseur.add_argument("--installer-wake", action="store_true",
                         help="installe openwakeword + le modèle « hey jarvis » (wake-word neuronal)")
    arguments = parseur.parse_args()
    if arguments.modele:
        print(conseiller_modele())
        return 0
    if arguments.vitesse:
        return bench_vitesse(adopte=arguments.adopte)
    if arguments.installer_voix:
        return installer_voix(arguments.installer_voix)
    if arguments.installer_wake:
        print(" 1/2 : paquet openwakeword…")
        fait = subprocess.run([sys.executable, "-m", "pip", "install", "openwakeword"])
        if fait.returncode != 0:
            return 1
        print(" 2/2 : modèle « hey jarvis »…")
        from audio import wake
        print(" " + wake.telecharger("jarvis"))
        return 0
    return bilan()


if __name__ == "__main__":
    raise SystemExit(principal())

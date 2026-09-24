"""Outils système de JIBI 2 : heure, matériel, processus, volume, commandes."""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from outils import outil

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

VK_VOLUME_MONTER = 0xAF
VK_VOLUME_BAISSER = 0xAE
VK_SILENCE = 0xAD


def _normaliser_sortie(texte: str) -> str:
    """Uniformise les espaces des sorties Windows avant leur affichage."""
    valeur = str(texte or "")
    valeur = valeur.replace("\u00a0", " ").replace("\u202f", " ")
    # Une sortie déjà endommagée ne doit pas laisser le glyphe de
    # remplacement au milieu d'un nombre : on le rend comme une espace.
    import re
    valeur = re.sub(r"(?<=\d)\ufffd(?=\d)", " ", valeur)
    return valeur.replace("\ufffd", "").replace("\x00", "")


def _decoder_sortie(brut: bytes | str | None) -> str:
    """Décode une sortie console avec des remplacements sûrs.

    Windows mélange parfois UTF-8, CP1252 et CP850 selon la commande. On
    privilégie l'UTF-8 strict, puis les pages de codes locales usuelles.
    """
    if brut is None:
        return ""
    if isinstance(brut, str):
        return _normaliser_sortie(brut)
    donnees = bytes(brut)
    for encodage in ("utf-8", "cp437", "cp850", "cp1252"):
        try:
            texte = donnees.decode(encodage)
        except (UnicodeDecodeError, LookupError):
            continue
        if "\ufffd" not in texte:
            return _normaliser_sortie(texte)
    return _normaliser_sortie(donnees.decode("utf-8", errors="replace"))


@outil("heure_actuelle", "Donne l'heure et la date actuelles du PC.", {},
       categorie="systeme", exemple='{"outil": "heure_actuelle", "parametres": {}}')
def heure_actuelle() -> str:
    t = datetime.now()
    return (f"Il est {t.strftime('%H:%M')}, {JOURS[t.weekday()]} "
            f"{t.day} {MOIS[t.month]} {t.year}.")


@outil("info_systeme", "Donne la fiche du PC : système, processeur, mémoire, disque.", {},
       categorie="systeme")
def info_systeme() -> str:
    ram_go = "?"
    try:
        if sys.platform == "win32":
            class _Memoire(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _Memoire()
            m.dwLength = ctypes.sizeof(_Memoire)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            ram_go = f"{m.ullTotalPhys / 2**30:.1f} Go ({m.ullAvailPhys / 2**30:.1f} Go libres)"
        else:
            with open("/proc/meminfo", encoding="utf-8") as f:
                total = int(f.readline().split()[1])
            ram_go = f"{total / 2**20:.1f} Go"
    except Exception:
        pass
    disque = shutil.disk_usage(os.path.expanduser("~"))
    return (f"{platform.system()} {platform.release()} | processeur : {platform.processor() or '?'} | "
            f"mémoire : {ram_go} | disque : {disque.free / 2**30:.0f} Go libres sur "
            f"{disque.total / 2**30:.0f} Go | Python {platform.python_version()}")


@outil("batterie", "Donne le niveau de batterie et si le PC est branché.", {},
       categorie="systeme")
def batterie() -> str:
    if sys.platform != "win32":
        return "Batterie : information disponible sous Windows seulement."
    class _Etat(ctypes.Structure):
        _fields_ = [("SurSecteur", ctypes.c_ubyte), ("Drapeau", ctypes.c_ubyte),
                    ("Pourcent", ctypes.c_ubyte), ("Reserve", ctypes.c_ubyte),
                    ("VieRestante", ctypes.c_ulong), ("VieTotale", ctypes.c_ulong)]
    etat = _Etat()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(etat)):
        return "Impossible de lire l'état de la batterie."
    if etat.Pourcent > 100:
        return "Batterie : inconnue (PC fixe ?)."
    source = "sur secteur" if etat.SurSecteur == 1 else "sur batterie"
    return f"Batterie : {etat.Pourcent} % ({source})."


@outil("processus", "Liste les programmes en cours d'exécution (les plus gourmands d'abord).",
       {"limite": {"type": "int", "obligatoire": False, "description": "nombre de lignes (défaut 12)"}},
       categorie="systeme")
def processus(limite: int = 12) -> str:
    try:
        if sys.platform == "win32":
            fait = subprocess.run(["tasklist"], capture_output=True, timeout=15)
            sortie = _decoder_sortie(fait.stdout)
            lignes = [li for li in sortie.splitlines()[3:] if li.strip()]
        else:
            fait = subprocess.run(["ps", "aux", "--sort=-%cpu"], capture_output=True,
                                  timeout=15)
            sortie = _decoder_sortie(fait.stdout)
            lignes = sortie.splitlines()[1:]
        return f"{len(lignes)} processus. Principaux :\n" + "\n".join(lignes[:max(1, limite)])
    except Exception as e:
        return f"Impossible de lister les processus : {e}"


@outil("espace_disque", "Donne l'espace libre sur le disque principal.", {},
       categorie="systeme")
def espace_disque() -> str:
    d = shutil.disk_usage(os.path.expanduser("~"))
    return (f"Disque : {d.free / 2**30:.0f} Go libres sur {d.total / 2**30:.0f} Go "
            f"({100 * d.used / d.total:.0f} % utilisés).")


def _touche_volume(code: int, repetitions: int) -> str:
    if sys.platform != "win32":
        return "Le réglage du volume n'est géré que sous Windows pour l'instant."
    for _ in range(max(1, repetitions)):
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(code, 0, 2, 0)  # relâche la touche
    return "Volume ajusté."


@outil("monter_volume", "Monte le volume du son (pas de 2 %, environ).",
       {"repetitions": {"type": "int", "obligatoire": False, "description": "nombre de pas (défaut 5)"}},
       categorie="systeme")
def monter_volume(repetitions: int = 5) -> str:
    return _touche_volume(VK_VOLUME_MONTER, repetitions)


@outil("baisser_volume", "Baisse le volume du son.",
       {"repetitions": {"type": "int", "obligatoire": False, "description": "nombre de pas (défaut 5)"}},
       categorie="systeme")
def baisser_volume(repetitions: int = 5) -> str:
    return _touche_volume(VK_VOLUME_BAISSER, repetitions)


@outil("couper_son", "Active/désactive le son (mute).", {}, categorie="systeme")
def couper_son() -> str:
    return _touche_volume(VK_SILENCE, 1)


# --- Contrôle de la luminosité ---
def _get_brightness() -> int:
    """Lit la luminosité actuelle du moniteur."""
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True, timeout=5
        )
        return int(result.stdout.strip())
    except Exception:
        return -1


@outil("monter_luminosite", "Augmente la luminosité de l'écran (pas de 10 %, max 100).",
       {"pas": {"type": "int", "obligatoire": False, "description": "augmentation en pourcentage (défaut 10)"}},
       categorie="systeme", exemple='{"outil": "monter_luminosite", "parametres": {}}')
def monter_luminosite(pas: int = 10) -> str:
    """Augmente la luminosité de l'écran."""
    try:
        current = _get_brightness()
        if current < 0:
            return "Impossible de lire la luminosité actuelle."
        nouvelle = min(100, current + pas)
        subprocess.run(
            ["powershell", f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).SetBrightness(2, {nouvelle})"],
            capture_output=True, timeout=5
        )
        return f"Luminosité augmentée : {current}% → {nouvelle}%"
    except Exception as e:
        return f"Impossible de changer la luminosité : {str(e)[:80]}"


@outil("baisser_luminosite", "Baisse la luminosité de l'écran (pas de 10 %, min 0).",
       {"pas": {"type": "int", "obligatoire": False, "description": "diminution en pourcentage (défaut 10)"}},
       categorie="systeme", exemple='{"outil": "baisser_luminosite", "parametres": {}}')
def baisser_luminosite(pas: int = 10) -> str:
    """Baisse la luminosité de l'écran."""
    try:
        current = _get_brightness()
        if current < 0:
            return "Impossible de lire la luminosité actuelle."
        nouvelle = max(0, current - pas)
        subprocess.run(
            ["powershell", f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).SetBrightness(2, {nouvelle})"],
            capture_output=True, timeout=5
        )
        return f"Luminosité baissée : {current}% → {nouvelle}%"
    except Exception as e:
        return f"Impossible de changer la luminosité : {str(e)[:80]}"


@outil("luminosite_actuelle", "Donne la luminosité actuelle de l'écran.", {},
       categorie="systeme", exemple='{"outil": "luminosite_actuelle", "parametres": {}}')
def luminosite_actuelle() -> str:
    """Retourne la luminosité actuelle."""
    try:
        current = _get_brightness()
        if current < 0:
            return "Impossible de lire la luminosité."
        return f"Luminosité actuelle : {current}%"
    except Exception:
        return "Impossible de lire la luminosité."


@outil("executer_commande", "Exécute une commande système (Windows) et renvoie son résultat. Action RISQUÉE.",
       {"commande": {"type": "str", "obligatoire": True, "description": "la commande à exécuter"},
        "timeout_s": {"type": "int", "obligatoire": False, "description": "durée max en secondes (défaut 30)"}},
       categorie="systeme", risque="eleve", exemple='{"outil": "executer_commande", "parametres": {"commande": "ipconfig"}}')
def executer_commande(commande: str, timeout_s: int = 30) -> str:
    try:
        fait = subprocess.run(commande, shell=True, capture_output=True,
                              timeout=max(5, min(int(timeout_s), 120)))
        sortie = _decoder_sortie(fait.stdout).strip()
        erreurs = _decoder_sortie(fait.stderr).strip()
        texte = sortie or erreurs or f"(commande terminée, code {fait.returncode})"
        if len(texte) > 3000:
            texte = texte[:3000] + "… (tronqué)"
        return texte
    except subprocess.TimeoutExpired:
        return "La commande a dépassé le temps autorisé et a été arrêtée."


@outil("eteindre_pc", "Éteint le PC après un délai. Action RISQUÉE (annulable avec la commande « shutdown /a »).",
       {"delai_minutes": {"type": "int", "obligatoire": False, "description": "délai avant extinction (défaut 1)"}},
       categorie="systeme", risque="eleve")
def eteindre_pc(delai_minutes: int = 1) -> str:
    if sys.platform == "win32":
        subprocess.run(["shutdown", "/s", "/t", str(max(10, int(delai_minutes) * 60))], check=False)
        return (f"Extinction programmée dans {max(1, int(delai_minutes))} minute(s). "
                "Pour annuler : dis « annule l'extinction » ou `shutdown /a`.")
    subprocess.run(["shutdown", "-h", f"+{max(1, int(delai_minutes))}"], check=False)
    return f"Extinction programmée dans {max(1, int(delai_minutes))} minute(s)."


def _version_locale() -> str:
    try:
        return (Path(__file__).parent.parent / "VERSION").read_text(
            encoding="utf-8").strip() or "inconnue"
    except OSError:
        return "inconnue"


@outil("verifier_mise_a_jour",
       "Donne la version de JIBI et vérifie si une mise à jour existe "
       "(comparaison avec JIBI_VERSION_URL du .env si réglé).",
       categorie="amelioration", risque="faible",
       exemple="es-tu à jour ?")
def verifier_mise_a_jour() -> str:
    from jibi2 import config
    locale = _version_locale()
    url = config.valeur("JIBI_VERSION_URL", "").strip()
    if not url:
        return (f"Tu es en version {locale}. JIBI peut améliorer son code source "
                "automatiquement avec tests et retour arrière, mais ne remplace jamais "
                "automatiquement son installation complète (zip, dépendances ou modèle). "
                "Pour une nouvelle version de paquet, garde donnees/ et modeles/voix/.")
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=5) as reponse:
            distante = reponse.read().decode("utf-8", "replace").strip()[:60]
    except Exception as e:  # noqa: BLE001
        return f"Tu es en version {locale} ; impossible de vérifier la version distante ({str(e)[:80]})."
    if distante and distante != locale:
        return (f"⬆️ Nouvelle version disponible : {distante} (tu es en {locale}). "
                "Télécharge le nouveau zip, remplace le dossier en gardant donnees/ "
                "et modeles/voix/.")
    return f"Tu es à jour ({locale})."


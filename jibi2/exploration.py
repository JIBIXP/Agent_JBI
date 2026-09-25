"""Exploration autonome du web — JIBI navigue seul, en lecture seule.

Deux déclencheurs :
- l'utilisateur demande : « explore le web sur … », « navigue seul sur … » ;
- le mode autonome : une exploration quotidienne à heure fixe
  (configurer_exploration / JIBI_EXPLORATION_HEURE) ou lancée à la demande
  par le modèle avec l'outil explorer_autonome.

Tout passe par outils/navigateur.py (Browser Use local, Chrome local,
Ollama local) : lecture seule — aucun formulaire, aucune connexion,
aucun achat, aucun téléchargement. Les pages lues sont des données non
fiables : elles ne peuvent jamais déclencher une action. Chaque exploration
est tracée dans donnees/journal/exploration.jsonl.
"""
from __future__ import annotations

import contextlib
import json
import re
import threading
import time

from . import audit, config, progression

ETAT = config.DOSSIER_JOURNAL / "exploration.json"
JOURNAL = config.DOSSIER_JOURNAL / "exploration.jsonl"
VERROU = threading.Lock()
_MOTIF_HEURE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
_MOTIF_HOTE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")

SUJETS = (
    "les nouveautés de l'intelligence artificielle locale",
    "l'actualité sciences et espace",
    "les mises à jour Windows récentes et leurs conseils",
    "une nouvelle utile sur la productivité au quotidien",
    "les nouveautés du logiciel libre et open source",
)


def _lire_etat() -> dict:
    etat = {
        "actif": config.valeur_bool("JIBI_EXPLORATION_ACTIVE"),
        "heure": config.valeur("JIBI_EXPLORATION_HEURE", "") or "",
        "mode": config.valeur("JIBI_EXPLORATION_MODE", "seul").strip().lower() or "seul",
        "inactivite": max(10, config.entier("JIBI_EXPLORATION_INACTIVITE", 45)),
        "max_par_jour": max(1, config.entier("JIBI_EXPLORATION_MAX_JOUR", 3)),
        "sujets_vus": [],
    }
    if ETAT.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            contenu = json.loads(ETAT.read_text(encoding="utf-8"))
            if isinstance(contenu, dict):
                etat.update({k: contenu[k] for k in
                             ("actif", "heure", "mode", "inactivite",
                              "max_par_jour", "sujets_vus") if k in contenu})
    etat["actif"] = etat["actif"] is True or str(etat["actif"]).lower() in ("1", "true", "on")
    if etat["heure"] and not _MOTIF_HEURE.match(str(etat["heure"])):
        etat["heure"] = ""          # pas d'heure = mode « seul »
    if not isinstance(etat["sujets_vus"], list):
        etat["sujets_vus"] = []
    return etat


def _ecrire_etat(etat: dict) -> None:
    ETAT.parent.mkdir(parents=True, exist_ok=True)
    ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")


def configurer(actif: bool, heure: str = "") -> str:
    """Active l'exploration. SANS heure → mode « seul » : JIBI choisit lui-même
    le moment (quand tu ne lui parles pas depuis un moment, dans la limite
    quotidienne). Avec heure → mode programmé classique."""
    etat = _lire_etat()
    etat["actif"] = bool(actif)
    if heure.strip():
        h = heure.strip()
        if not _MOTIF_HEURE.match(h):
            return "Horaire invalide : utilise HH:MM, par exemple 07:30 (ou aucune heure = mode seul)."
        etat["heure"] = f"{int(h.split(':')[0]):02d}:{h.split(':')[1]}"
    else:
        etat["heure"] = ""          # vide = mode seul
    _ecrire_etat(etat)
    etat_texte = "activée" if etat["actif"] else "désactivée"
    if etat["actif"] and etat["heure"]:
        detail = f"chaque jour à {etat['heure']}"
    elif etat["actif"]:
        detail = (f"en mode SEUL : j'explore quand tu ne me parles pas depuis "
                  f"{etat['inactivite']} minutes, {etat['max_par_jour']} fois par jour maximum")
    else:
        detail = ""
    return (f"✅ Navigation autonome {etat_texte}"
            + (f" — {detail}." if detail else ".")
            + " Lecture seule garantie : je ne saisis jamais rien et n'achète rien.")


def _noter(evenement: dict) -> None:
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evenement, ensure_ascii=False) + "\n")
    except OSError:
        pass


def dernier_bilan(nombre: int = 3) -> str:
    if not JOURNAL.exists():
        return "Aucune exploration enregistrée."
    lignes = JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines()[-nombre:]
    if not lignes:
        return "Aucune exploration enregistrée."
    sorties = []
    for ligne in lignes:
        with contextlib.suppress(json.JSONDecodeError):
            e = json.loads(ligne)
            sorties.append(f"{e.get('quand', '?')} — {e.get('sujet', '?')} : "
                           f"{e.get('resume', '')[:180]}")
    return "\n".join(sorties) or "Aucune exploration enregistrée."


def _choisir_sujet(sujet: str, etat: dict) -> str:
    sujet = (sujet or "").strip()
    if sujet:
        return sujet
    # Mode seul : tourne parmi les sujets, sans répéter le dernier.
    vus = [str(s) for s in etat.get("sujets_vus", [])[-len(SUJETS):]]
    restants = [s for s in SUJETS if s not in vus]
    return (restants or list(SUJETS))[0]


def explorer(sujet: str = "", max_sites: int = 3) -> str:
    """Une exploration : recherche → lecture de 2-3 pages → résumé sourcé."""
    if not VERROU.acquire(blocking=False):
        return "Une exploration est déjà en cours."
    try:
        return _explorer(sujet, max_sites)
    finally:
        VERROU.release()


def _explorer(sujet: str, max_sites: int) -> str:
    etat = _lire_etat()
    sujet = _choisir_sujet(sujet, etat)
    max_sites = max(1, min(int(max_sites), 5))
    progression.demarrer("Exploration web autonome", sujet)
    progression.mettre(15, "Recherche des pages à lire")
    try:
        from outils.web import rechercher_web

        resultats = rechercher_web(sujet, 6)
        if not resultats.strip():
            progression.terminer("Aucun résultat", succes=False)
            return "Aucun résultat de recherche pour ce sujet."
        liens = re.findall(r"https?://[^\s)\]>]+", resultats)[:max_sites + 2]
        resume_pages: list[str] = []
        lu = 0
        for url in liens:
            if lu >= max_sites:
                break
            progression.mettre(20 + int(60 * lu / max_sites), f"Lecture : {url[:80]}")
            from outils.navigateur import lire_site_browser
            texte = lire_site_browser(url)
            if texte.startswith(("Navigation locale impossible", "Browser Use local",
                                 "Seuls les sites", "La page")):
                continue
            # Garde un extrait compact de chaque page lue.
            corps = texte.split("\n", 3)[-1]
            resume_pages.append(f"— {url}\n{corps[:900]}")
            lu += 1
        if not resume_pages:
            progression.terminer("Aucune page lisible", succes=False)
            _noter({"quand": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "sujet": sujet, "pages": 0, "resume": "aucune page lisible"})
            return "J'ai cherché mais aucune page n'a pu être lue (réseau ou sites bloquants)."
        progression.mettre(90, "Rédaction du résumé")
        resume = ("Sujet : " + sujet + "\n\n"
                  + "\n\n".join(resume_pages)
                  + "\n\n(lecture seule, sources citées ci-dessus)")
        vus = [str(s) for s in etat.get("sujets_vus", [])] + [sujet]
        etat["sujets_vus"] = vus[-8:]
        _ecrire_etat(etat)
        _noter({"quand": time.strftime("%Y-%m-%d %H:%M:%S"), "sujet": sujet,
                "pages": lu, "resume": resume[:600]})
        audit.journaliser("exploration_web", sujet, details=f"{lu} page(s) lue(s)",
                          resultat="ok")
        progression.terminer(f"Exploration terminée ({lu} page(s))", succes=True)
        return resume
    except Exception as e:  # une exploration ratée ne doit rien casser
        progression.terminer(f"échec : {str(e)[:200]}", succes=False)
        _noter({"quand": time.strftime("%Y-%m-%d %H:%M:%S"), "sujet": sujet,
                "pages": 0, "resume": f"échec : {str(e)[:180]}"})
        return f"Exploration interrompue : {str(e)[:180]}"


def echeance() -> bool:
    """Vrai quand une exploration doit partir.

    - mode programmé (heure fixée) : pendant la minute choisie ;
    - mode « seul » (pas d'heure) : quand tu n'as pas parlé à JIBI depuis
      « inactivite » minutes ET que le quota du jour n'est pas atteint.
    """
    etat = _lire_etat()
    if not etat["actif"]:
        return False
    if etat["heure"]:
        return time.strftime("%H:%M") == etat["heure"]
    # Mode seul : inactivité + quota journalier.
    if _explorations_du_jour() >= int(etat["max_par_jour"]):
        return False
    silence = _derniere_activite_secondes()
    return silence >= int(etat["inactivite"]) * 60


def _explorations_du_jour() -> int:
    aujourd_hui = time.strftime("%Y-%m-%d")
    total = 0
    if JOURNAL.exists():
        for ligne in JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]:
            with contextlib.suppress(json.JSONDecodeError):
                if str(json.loads(ligne).get("quand", "")).startswith(aujourd_hui):
                    total += 1
    return total


def _derniere_activite_secondes() -> float:
    """Secondes depuis le dernier message utilisateur (toutes interfaces).

    Les interfaces écrivent donnees/journal/activite.json à chaque message ;
    absence de fichier = JIBI vient de démarrer (considéré comme inactif
    depuis assez longtemps pour UNE seule exploration de bienvenue).
    """
    fichier = config.DOSSIER_JOURNAL / "activite.json"
    try:
        epoch = json.loads(fichier.read_text(encoding="utf-8")).get("epoch", 0)
    except (OSError, json.JSONDecodeError, AttributeError):
        return 10 * 3600
    return max(0.0, time.time() - float(epoch))


def noter_activite() -> None:
    """Appelé par les interfaces à chaque message utilisateur."""
    try:
        fichier = config.DOSSIER_JOURNAL / "activite.json"
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(json.dumps({"epoch": time.time()}), encoding="utf-8")
    except OSError:
        pass


def deja_fait_aujourdhui() -> bool:
    """Mode programmé : une seule exploration par jour."""
    etat = _lire_etat()
    if etat["heure"]:
        return _explorations_du_jour() >= 1
    # Mode seul : la limite est gérée par le quota (max_par_jour).
    return False


def lancer_si_programme() -> str:
    """Point d'entrée du planificateur : '' si rien à faire."""
    if not echeance() or deja_fait_aujourdhui():
        return ""
    return explorer("", 3)


def enregistrer_outil() -> None:
    from outils import outil

    @outil("explorer_autonome",
           "Exploration web autonome en LECTURE SEULE : JIBI cherche un sujet, "
           "lit 2-3 pages avec Browser Use local (Chrome + Ollama, aucun cloud) "
           "et résume avec les sources. Sans sujet : il en choisit un lui-même.",
           {"sujet": {"type": "str", "obligatoire": False,
                      "description": "sujet à explorer (vide = choix autonome)"},
            "max_sites": {"type": "int", "obligatoire": False,
                          "description": "1 à 5 pages (défaut 3)"}},
           categorie="web", risque="moyen",
           exemple='{"outil": "explorer_autonome", "parametres": {"sujet": "nouveautes IA locale"}}')
    def explorer_autonome(sujet: str = "", max_sites: int = 3) -> str:
        return explorer(sujet, max_sites)

    @outil("configurer_exploration",
           "Active/désactive l'exploration web autonome (lecture seule). SANS "
           "heure : mode SEUL — JIBI explore quand tu ne lui parles pas depuis un "
           "moment, avec un maximum par jour. Avec heure (HH:MM) : mode programmé. "
           "Il choisit un sujet différent à chaque fois.",
           {"actif": {"type": "bool", "obligatoire": True,
                      "description": "true pour activer, false pour désactiver"},
            "heure": {"type": "str", "obligatoire": False,
                      "description": "HH:MM, ou vide pour le mode seul (recommandé)"}},
           categorie="web", risque="faible",
           exemple='{"outil": "configurer_exploration", "parametres": {"actif": true}}')
    def configurer_exploration(actif: bool, heure: str = "") -> str:
        return configurer(actif, heure)

    @outil("bilan_exploration",
           "Montre les dernières explorations web autonomes de JIBI : sujets, "
           "pages lues et résumés.",
           {"nombre": {"type": "int", "obligatoire": False,
                       "description": "nombre de bilans (défaut 3)"}},
           categorie="web", risque="faible",
           exemple='{"outil": "bilan_exploration", "parametres": {}}')
    def bilan_exploration(nombre: int = 3) -> str:
        return dernier_bilan(nombre)

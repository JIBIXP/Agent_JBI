"""Registre des outils de JIBI 2.

Chaque outil est une simple fonction décorée avec @outil(...) : nom,
description en français, paramètres documentés, catégorie et niveau de
risque. Le catalogue est présenté au modèle (LLM) sous forme de texte ;
le modèle répond en JSON {"outil": ..., "parametres": {...}} et le
registre valide et exécute.

Les modules perso/ sont chargés au démarrage : c'est là que JIBI peut
ajouter ses propres outils après TA validation (jibi2/evolution.py).
"""
from __future__ import annotations

import importlib.util
import re
import sys
import traceback
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jibi2 import config

DOSSIER_PERSO = Path(__file__).parent / "perso"

OUTILS: dict[str, Outil] = {}
_SERVICES: dict[str, Any] = {}


@dataclass
class Outil:
    nom: str
    fonction: Callable
    description: str
    parametres: dict[str, dict] = field(default_factory=dict)
    categorie: str = "divers"
    risque: str = "faible"          # faible | moyen | eleve
    exemple: str = ""


def outil(nom: str, description: str, parametres: dict | None = None,
          categorie: str = "divers", risque: str = "faible", exemple: str = "") -> Callable:
    """Décorateur : enregistre la fonction comme outil de JIBI."""
    def decorateur(fonction: Callable) -> Callable:
        OUTILS[nom] = Outil(
            nom=nom, fonction=fonction, description=description.strip(),
            parametres=parametres or {}, categorie=categorie, risque=risque, exemple=exemple,
        )
        return fonction
    return decorateur


def regler_services(**services: Any) -> None:
    """Injecte les services partagés (mémoire, rappels...)."""
    _SERVICES.update(services)


def service(nom: str) -> Any:
    return _SERVICES[nom]


# ------------------------------------------------------------------ chargement
def charger_integres() -> None:
    """Importe les modules d'outils intégrés (idempotent)."""
    from . import (  # noqa: F401
        amaran,
        applications,
        calcul,
        chrome,
        design,
        documents,
        fichiers,
        jeux,
        memoire_faits,
        notes,
        notifications,
        noyau,
        rappels,
        souris,
        systeme,
        vision,
        voix,
        web,
        workflows,
    )


def charger_perso() -> int:
    """Charge les outils perso validés (outils/perso/*.py). Renvoie le nombre."""
    if not DOSSIER_PERSO.exists():
        return 0
    total = 0
    for chemin in sorted(DOSSIER_PERSO.glob("*.py")):
        if chemin.name.startswith("_"):
            continue
        nom_module = f"jibi2_perso_{chemin.stem}"
        try:
            spec = importlib.util.spec_from_file_location(nom_module, chemin)
            module = importlib.util.module_from_spec(spec)
            sys.modules[nom_module] = module
            spec.loader.exec_module(module)   # le décorateur @outil enregistre
            total += 1
        except Exception:
            print(f"⚠️  Outil perso ignoré ({chemin.name}) :")
            traceback.print_exc()
    return total


# ------------------------------------------------------------------- catalogue
# ------------------------------------------------- jeu d'outils adaptatif
# Leçon Jarvis : un petit modèle local se noie avec trop d'outils (lent,
# appels rendus en texte au lieu d'être exécutés). On ne montre donc au
# modèle que le NOYAU du quotidien, enrichi à la volée selon les mots de la
# demande. L'exposition n'est qu'un indice : tout outil reste exécutable.
NOYAU = frozenset({
    "heure_actuelle", "calculer",
    "ouvrir_application", "ouvrir_chrome", "ouvrir_site_web", "rechercher_web",
    "retenir", "rappeler", "ajouter_note", "lister_notes",
    "programmer_rappel", "lister_rappels", "notifier",
    "creer_workflow", "lister_workflows",
    "batterie", "espace_disque", "creer_pdf", "creer_word",
    "ouvrir_panneau",
})

# (motif sur le message sans accents → outils ajoutés au jeu montré)
DOMAINES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"fichier|dossier", ("lire_fichier", "ecrire_fichier", "lister_dossier",
                          "chercher_fichier", "ajouter_fichier", "supprimer_fichier")),
    (r"telechargement|\bbureau\b|mon pc|disque c", ("lire_fichier_pc", "lister_dossier_pc")),
    (r"\bnotes?\b|pense[- ]?bete", ("chercher_notes", "supprimer_note")),
    (r"annul", ("annuler_rappel",)),
    (r"volume|\bson\b|musique|silence|muet|chanson", ("monter_volume", "baisser_volume", "couper_son")),
    (r"processus|processeur|\bcpu\b|\bram\b|memoire vive|fiche du pc", ("processus", "info_systeme")),
    (r"eteins|eteindre|redemarre|arrete le pc", ("eteindre_pc",)),
    (r"commande|terminal|powershell|\bcmd\b|ipconfig|\bping\b", ("executer_commande",)),
    (r"ecran|capture|regarde|\bvois\b", ("voir_ecran",)),
    (r"amaran|godox|lumiere video|key ?light|aputure", ("controler_amaran",)),
    (r"souris|curseur|\bclique|defile|double[- ]?clic", (
        "deplacer_souris", "cliquer_souris", "defiler")),
    (r"\bjeux?\b|pile ou face|mystere|pierre|feuille|ciseaux|lance un de",
     ("lancer_un_de", "pile_ou_face", "pierre_feuille_ciseaux", "nombre_mystere")),
    (r"panneau|tableau de bord", ("ouvrir_panneau",)),
    (r"design|couleur[s]? de (l'?orbe|l'?interface|jibi)|\btheme\b|personnalise",
     ("personnaliser_design",)),
    (r"voix (masculine|feminine|homme|femme)|changer (de |la |ma )?voix|quelle voix|change (ta |de )?voix",
     ("changer_voix",)),
    (r"\bnoyau\b|auto[- ]?modifi|modifie (le|ton) (code|programme)|code source de jibi",
     ("modifier_noyau", "restaurer_noyau")),
    (r"mise[s]? a jour|mettre a jour|mets a jour|nouvelle version|version de jibi|a jour",
     ("verifier_mise_a_jour",)),
    (r"onglet|cette page|page active|\bresume\b|traduis", (
        "lister_onglets", "ouvrir_onglet", "activer_onglet",
        "fermer_onglet", "lire_onglet_actif")),
    (r"page web|lire (la |cette )?page|https?://", ("lire_page_web",)),
    (r"\bcode\b|\btests?\b|verifie|amelior|propose|\boutil|erreur|\bbug\b|corrige", (
        "analyser_code_projet", "lancer_verification", "lire_code_outil",
        "lister_erreurs", "proposer_nouvel_outil", "tester_proposition",
        "activer_proposition")),
    (r"routine|chaque (jour|matin|soir)", ("executer_workflow", "supprimer_workflow")),
)


def _sans_accent(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in texte if not unicodedata.combining(c))


def outils_pour_message(texte: str) -> list[str]:
    """Noms d'outils à montrer au modèle : noyau + domaines évoqués."""
    noms = set(NOYAU)
    t = _sans_accent(texte)
    for motif, domaine in DOMAINES:
        if re.search(motif, t):
            noms.update(domaine)
    return sorted(noms & set(OUTILS))


def catalogue_pour_llm(noms: set[str] | list[str] | None = None) -> str:
    """Liste des outils, lisible par le modèle, en français.

    noms = sous-ensemble (jeu adaptatif) ; None = catalogue complet.
    """
    if noms is None:
        outils = sorted(OUTILS.values(), key=lambda x: (x.categorie, x.nom))
    else:
        outils = [OUTILS[n] for n in sorted(noms) if n in OUTILS]
    # VITESSE : ce catalogue part dans le prompt à CHAQUE tour — sur CPU,
    # chaque caractère relus coûte du pré-remplissage. Format compact :
    # description courte + paramètres OBLIGATOIRES seulement + exemple court.
    lignes = []
    for o in outils:
        description = " ".join(o.description.split())
        if len(description) > 120:
            description = description[:117].rstrip() + "…"
        ligne = f"- {o.nom}[{o.risque}] {description}"
        obligatoires = [(p, " ".join(i.get("description", "").split()))
                        for p, i in o.parametres.items() if i.get("obligatoire")]
        if obligatoires:
            ligne += " | besoin: " + "; ".join(
                f"{p}={d[:50]}" if d else p for p, d in obligatoires)
        if o.exemple:
            ligne += f" | ex: {o.exemple[:80]}"
        lignes.append(ligne)
    return "\n".join(lignes)


def lister_noms() -> list[str]:
    return sorted(OUTILS)


# ------------------------------------------------------------------- exécution
def _journaliser_echec(nom: str, texte: str) -> None:
    """Note l'échec pour la boucle d'auto-amélioration (sauf refus utilisateur)."""
    if "refusé" in texte:
        return
    try:
        from jibi2.evolution import noter_erreur
        noter_erreur(nom, texte)
    except Exception:
        pass


def executer(nom: str, parametres: dict, garde) -> dict:
    """Valide et exécute un outil. Renvoie {ok, texte, risque}."""
    if nom not in OUTILS:
        texte = f"Outil « {nom} » inconnu. Utilise un outil de la liste."
        _journaliser_echec(nom, texte)
        return {"ok": False, "texte": texte, "risque": "faible"}
    o = OUTILS[nom]
    parametres = parametres or {}
    manquants = [p for p, i in o.parametres.items()
                 if i.get("obligatoire") and p not in parametres]
    if manquants:
        texte = f"Paramètre(s) manquant(s) pour {nom} : {', '.join(manquants)}."
        _journaliser_echec(nom, texte)
        return {"ok": False, "texte": texte, "risque": o.risque}
    if o.risque == "eleve":
        detail = _decrire_appel(o, parametres)
        if not garde.autoriser(nom, o.risque, detail):
            return {"ok": False, "texte": "L'utilisateur a refusé cette action risquée. "
                                          "Propose autre chose ou arrête-toi là.",
                    "risque": o.risque}
    try:
        resultat = o.fonction(**parametres)
    except TypeError as e:
        texte = f"Paramètres invalides pour {nom} : {e}"
        _journaliser_echec(nom, texte)
        return {"ok": False, "texte": texte, "risque": o.risque}
    except Exception as e:  # noqa: BLE001 — un outil ne doit jamais faire planter JIBI
        texte = f"Erreur pendant {nom} : {e}"
        _journaliser_echec(nom, texte)
        return {"ok": False, "texte": texte, "risque": o.risque}
    if isinstance(resultat, dict):
        texte = resultat.get("texte", str(resultat))
        ok = bool(resultat.get("ok", True))
    else:
        texte, ok = str(resultat), True
    if not ok:
        _journaliser_echec(nom, texte)
    return {"ok": ok, "texte": texte, "risque": o.risque}


def _decrire_appel(o: Outil, parametres: dict) -> str:
    morceaux = [f"{p} = {v!r}" for p, v in parametres.items()]
    return f"{o.description} — {', '.join(morceaux) or 'sans paramètre'}"


charger_integres()

# L'outil d'amélioration (proposer_nouvel_outil) est enregistré ici pour
# être visible partout : console, fenêtre, docteur. Import paresseux dans
# la fonction : pas de circularité.
try:
    from jibi2.evolution import enregistrer_outil

    enregistrer_outil()
except Exception:
    pass

config.preparer_dossiers()

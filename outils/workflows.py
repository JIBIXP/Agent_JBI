"""Workflows de JIBI 2 : des petites routines (« routine du matin ») qui
enchaînent plusieurs outils — ou plusieurs messages — dans l'ordre.

Un workflow = un fichier JSON dans donnees/workflows/. Rien n'est du
code : chaque étape appelle un outil existant (avec la même garde de
confirmation que d'habitude sur les étapes risquées) ou envoie un
message à JIBI. Créables par toi, par le modèle, exécutables à la voix.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from jibi2 import config
from outils import outil, service

_MOTIF_NOM = re.compile(r"^[a-z][a-z0-9_]{2,30}$")


def _dossier() -> Path:
    dossier = config.DOSSIER_DONNEES / "workflows"
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def _chemin(nom: str) -> Path:
    nom = (nom or "").strip().removesuffix(".json")
    if not _MOTIF_NOM.match(nom):
        raise ValueError("nom de workflow invalide")
    return _dossier() / f"{nom}.json"


def _exemple_si_vide() -> None:
    """Crée une routine d'exemple au premier lancement."""
    if not any(_dossier().glob("*.json")):
        creer("routine_matin", "Petit résumé du matin (exemple modifiable)",
              json.dumps([
                  {"outil": "heure_actuelle", "parametres": {}},
                  {"outil": "lister_rappels", "parametres": {}},
                  {"outil": "lister_notes", "parametres": {"nombre": 5}},
              ], ensure_ascii=False))


# ─────────────────────────────────────────────── création / gestion
def creer(nom: str, description: str, etapes_json: str, horaire: str = "") -> str:
    nom = (nom or "").strip()
    if not _MOTIF_NOM.match(nom):
        return "Nom invalide : minuscules, chiffres et _ seulement (ex. routine_matin)."
    try:
        etapes = json.loads(etapes_json or "[]")
    except json.JSONDecodeError as e:
        return f"Les étapes ne sont pas un JSON valide : {e}"
    if not isinstance(etapes, list) or not (1 <= len(etapes) <= 12):
        return "Il faut une LISTE de 1 à 12 étapes (JSON), ex. " \
               '[{"outil": "heure_actuelle", "parametres": {}}]'
    import outils
    for i, etape in enumerate(etapes, 1):
        if not isinstance(etape, dict):
            return f"Étape {i} : doit être un objet JSON."
        if "outil" in etape:
            if etape["outil"] not in outils.OUTILS:
                return (f"Étape {i} : l'outil « {etape['outil']} » n'existe pas. "
                        "Utilise un outil de la liste.")
            etape.setdefault("parametres", {})
            if not isinstance(etape["parametres"], dict):
                return f"Étape {i} : « parametres » doit être un objet JSON."
        elif "message" not in etape or not str(etape["message"]).strip():
            return f'Étape {i} : il faut "outil" ou "message".'
    horaire = (horaire or "").strip()
    if horaire:
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", horaire):
            return "Horaire invalide : utilise le format HH:MM (ex. 08:00)."
        horaire = f"{int(horaire.split(':')[0]):02d}:{horaire.split(':')[1]}"
    risque = " · ".join(
        outils.OUTILS[e["outil"]].risque for e in etapes if "outil" in e) or "faible"
    fichier = {"nom": nom, "description": (description or "").strip(),
               "etapes": etapes, "cree": time.strftime("%Y-%m-%d %H:%M")}
    if horaire:
        fichier["horaire"] = horaire
    _chemin(nom).write_text(json.dumps(fichier, ensure_ascii=False, indent=2), encoding="utf-8")
    alerte = (" ⚠️ Une étape est à risque élevé : elle demandera confirmation à l'exécution."
              if "eleve" in risque else "")
    return f"Workflow « {nom} » créé ({len(etapes)} étapes).{alerte} Lance-le : exécuter_workflow."


def lister() -> str:
    _exemple_si_vide()
    fichiers = sorted(_dossier().glob("*.json"))
    if not fichiers:
        return "Aucun workflow."
    lignes = []
    for f in fichiers:
        try:
            donnees = json.loads(f.read_text(encoding="utf-8"))
            etapes = donnees.get("etapes", [])
            resume = " → ".join(
                e.get("outil") or f'message : "{str(e.get("message", ""))[:40]}"' for e in etapes)
            lignes.append(f"- {donnees.get('nom', f.stem)} : {donnees.get('description', '')}"
                          f"\n    {len(etapes)} étape(s) : {resume}")
        except (json.JSONDecodeError, OSError):
            lignes.append(f"- {f.stem} : fichier illisible")
    return "Workflows disponibles :\n" + "\n".join(lignes)


def supprimer(nom: str) -> str:
    try:
        chemin = _chemin(nom)
    except ValueError:
        return "Nom de workflow invalide."
    if not chemin.exists():
        return f"Aucun workflow « {nom} »."
    chemin.unlink()
    return f"Workflow « {nom} » supprimé."


def executer(nom: str) -> str:
    try:
        chemin = _chemin(nom)
    except ValueError:
        return "Nom de workflow invalide."
    if not chemin.exists():
        return f"Aucun workflow « {nom} ». Voir lister_workflows."
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return f"Workflow « {nom} » illisible : {e}"
    import outils
    etapes = donnees.get("etapes", [])
    lignes = [f"▶ {donnees.get('description') or nom} — {len(etapes)} étape(s)"]
    reussies = passees = echecs = 0
    for i, etape in enumerate(etapes, 1):
        if "message" in etape:
            try:
                assistant = service("assistant")
                reponse = assistant.repondre(str(etape["message"]))
                lignes.append(f"  {i}. 💬 {reponse['reponse'][:200]}")
                if reponse.get("ok"):
                    reussies += 1
                else:
                    echecs += 1
            except KeyError:
                passees += 1
                lignes.append(f"  {i}. 💬 passée (assistant non disponible ici)")
            continue
        resultat = outils.executer(etape["outil"], etape.get("parametres", {}),
                                   service("garde"))
        croix = "✅" if resultat["ok"] else "❌"
        lignes.append(f"  {i}. {croix} {etape['outil']} : {resultat['texte'][:180]}")
        if resultat["ok"]:
            reussies += 1
        else:
            echecs += 1
    lignes.insert(1, f"Résultat : {reussies} ok · {passees} passée(s) · {echecs} échec(s)")
    return "\n".join(lignes)


# ─────────────────────────────────────────────── outils pour le modèle
@outil("creer_workflow",
       "Crée un workflow (routine) qui enchaîne des outils ou des messages. "
       "etapes est une CHAÎNE contenant du JSON : liste de {\"outil\": nom, \"parametres\": {...}} "
       "et/ou {\"message\": \"question à JIBI\"}.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom court : minuscules et _"},
        "description": {"type": "str", "obligatoire": True, "description": "à quoi sert la routine"},
        "etapes": {"type": "str", "obligatoire": True,
                   "description": "chaîne JSON : liste de {\"outil\": nom, \"parametres\": {...}} "
                                  "et/ou {\"message\": \"question à JIBI\"}"},
        "horaire": {"type": "str", "obligatoire": False,
                    "description": "HH:MM pour l'exécution chaque jour automatiquement (ex. 08:00)"}},
       categorie="workflows", risque="moyen",
       exemple='{"outil": "creer_workflow", "parametres": {"nom": "routine_soir", '
               '"description": "Résumé du soir", "etapes": "[{\\"outil\\": \\"lister_rappels\\", '
               '\\"parametres\\": {}}]"}}')
def creer_workflow(nom: str, description: str, etapes: str, horaire: str = "") -> str:
    return creer(nom, description, etapes, horaire)


@outil("lister_workflows", "Liste les workflows (routines) disponibles.", {},
       categorie="workflows")
def lister_workflows() -> str:
    return lister()


@outil("executer_workflow", "Exécute un workflow : toutes ses étapes, dans l'ordre "
                            "(les étapes risquées demandent confirmation comme d'habitude).",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du workflow"}},
       categorie="workflows", risque="moyen",
       exemple='{"outil": "executer_workflow", "parametres": {"nom": "routine_matin"}}')
def executer_workflow(nom: str) -> str:
    return executer(nom)


@outil("supprimer_workflow", "Supprime un workflow par son nom.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du workflow"}},
       categorie="workflows", risque="moyen")
def supprimer_workflow(nom: str) -> str:
    return supprimer(nom)

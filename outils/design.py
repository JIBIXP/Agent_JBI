"""Design de JIBI — personnalisable par JIBI lui-même, sans toucher au code.

Le design vit dans donnees/design.json (dossier des données utilisateur :
il survit aux mises à jour). JIBI le modifie via personnaliser_design :
- l'orbe (couleurs des 4 états) est relue par interface/bureau.py au
  démarrage de la fenêtre ;
- le panneau web (interface/panneau.html) est re-coloré IMMÉDIATEMENT
  (une feuille de style est injectée à chaque visite de la page).
C'est l'autonomie « niveau 1 » : aucune permission demandée, risque nul —
au pire un « personnaliser_design reset » ramène l'origine.
"""
from __future__ import annotations

import json
import re

from outils import outil

_CHEMIN = None            # défini paresseusement (config.RACINE)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

_ETATS_ORBE = ("repos", "ecoute", "reflexion", "parole")
_CLES_PANNEAU = ("fond", "carte", "accent", "texte")

DEFAUT: dict = {
    "orbe": {
        "repos": ["#0d3a2e", "#2fd6a3", "#7cf0cc"],
        "ecoute": ["#0a3d4a", "#1e8fb8", "#5cc8e8"],
        "reflexion": ["#4a3614", "#d19a3f", "#ffc46b"],
        "parole": ["#0d4d33", "#1fb87e", "#7cf0cc"],
    },
    "panneau": {"fond": "#0c0f0e", "carte": "#141a18",
                "accent": "#2fd6a3", "texte": "#eef2f0"},
}


def _fichier():
    global _CHEMIN
    if _CHEMIN is None:
        from jibi2 import config
        _CHEMIN = config.DOSSIER_DONNEES / "design.json"
    return _CHEMIN


def lire_design() -> dict:
    """Design effectif : défaut + personnalisations enregistrées."""
    design = json.loads(json.dumps(DEFAUT))          # copie profonde
    try:
        ecrit = json.loads(_fichier().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return design
    for section in ("orbe", "panneau"):
        for cle, valeur in (ecrit.get(section) or {}).items():
            if section == "orbe" and cle in design["orbe"] \
                    and isinstance(valeur, list) and len(valeur) == 3:
                design["orbe"][cle] = [str(v) for v in valeur]
            elif section == "panneau" and cle in design["panneau"]:
                design["panneau"][cle] = str(valeur)
    return design


def style_panneau() -> str:
    """Feuille de style CSS à injecter dans le panneau ("" si tout par défaut)."""
    ecrit = {}
    try:
        ecrit = json.loads(_fichier().read_text(encoding="utf-8")).get("panneau") or {}
    except (OSError, json.JSONDecodeError):
        return ""
    correspondance = {"fond": "--fond", "carte": "--carte",
                      "accent": "--accent", "texte": "--texte"}
    regles = [f"{correspondance[k]}:{v}" for k, v in ecrit.items()
              if k in correspondance and _HEX.match(str(v))]
    return "<style>:root{" + ";".join(regles) + "}</style>" if regles else ""


@outil("personnaliser_design",
       "Change les COULEURS de JIBI — son orbe et son panneau web. C'est ton "
       "design : tu peux le modifier sans demander. Cles : orbe.repos, "
       "orbe.ecoute, orbe.reflexion, orbe.parole (3 couleurs hex « #a12, #b34, "
       "#c56 ») ; panneau.fond, panneau.carte, panneau.accent, panneau.texte "
       "(1 hex). Cle vide = montrer le design actuel ; « reset » = retrouver "
       "l'origine. Panneau appliqué tout de suite, orbe au prochain démarrage.",
       parametres={
           "cle": {"type": "str", "description": "ex. panneau.accent ou orbe.reflexion (vide = état actuel)"},
           "valeur": {"type": "str", "description": "couleur(s) hex, ex. #ff8800 ou #111, #44aa88, #ccffdd"},
       },
       categorie="design", risque="faible",
       exemple="orbe rose → cle=orbe.reflexion, valeur=#5e1231, #b82a62, #ff7db2")
def personnaliser_design(cle: str = "", valeur: str = "") -> str:
    c = (cle or "").strip().lower()
    if c in ("", "etat", "actuel", "voir"):
        d = lire_design()
        orbe = " ; ".join(f"{e} = {' / '.join(v)}" for e, v in d["orbe"].items())
        panneau = " ; ".join(f"{k} = {v}" for k, v in d["panneau"].items())
        return f"Design actuel — Orbe : {orbe}. Panneau : {panneau}."
    if c in ("reset", "reinitialiser", "tout reinitialiser", "reinitialise"):
        _fichier().unlink(missing_ok=True)
        return "Design d'origine restauré (panneau immédiatement, orbe au prochain démarrage)."

    section, _, sous = c.partition(".")
    sous = sous.strip()
    if section == "orbe":
        if sous not in _ETATS_ORBE:
            return f"État d'orbe inconnu : {sous or c}. Choisis parmi : {', '.join(_ETATS_ORBE)}."
        couleurs = [m.group(0) for m in re.finditer(r"#[0-9a-fA-F]{6}", valeur or "")]
        if len(couleurs) != 3:
            return "Pour l'orbe il faut 3 couleurs hex : halo, milieu, cœur (ex. « #12315e, #2a62b8, #7db2ff »)."
        modification = {"orbe": {sous: couleurs}}
        message = f"Orbe « {sous} » recolorée ({' / '.join(couleurs)}). Appliqué au prochain démarrage."
    elif section == "panneau":
        if sous not in _CLES_PANNEAU:
            return f"Clé de panneau inconnue : {sous or c}. Choisis parmi : {', '.join(_CLES_PANNEAU)}."
        hexa = re.search(r"#[0-9a-fA-F]{6}\b", valeur or "")
        if hexa is None:
            return "Il faut une couleur hex, ex. #ff8800."
        modification = {"panneau": {sous: hexa.group(0)}}
        message = f"Panneau : {sous} → {hexa.group(0)}. Appliqué immédiatement (recharge la page)."
    else:
        return ("Clé inconnue. Utilise orbe.<etat> (repos, ecoute, reflexion, parole), "
                "panneau.<cle> (fond, carte, accent, texte), ou « reset ».")

    try:
        actuel = json.loads(_fichier().read_text(encoding="utf-8")) if _fichier().exists() else {}
    except (OSError, json.JSONDecodeError):
        actuel = {}
    fusion = {**actuel}
    for s, v in modification.items():
        fusion[s] = {**(fusion.get(s) or {}), **v}
    _fichier().parent.mkdir(parents=True, exist_ok=True)
    _fichier().write_text(json.dumps(fusion, ensure_ascii=False, indent=2), encoding="utf-8")
    from jibi2 import evolution
    evolution.noter_changelog(f"design modifié : {c} → {valeur[:60]}")
    return message + " Dis « reset le design » pour revenir en arrière."

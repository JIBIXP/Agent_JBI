"""Outils fichiers de JIBI 2.

Deux zones : l'ESPACE DE TRAVAIL (donnees/fichiers/, écritures autorisées)
et le RESTE DU PC (lecture seule, outil distinct et confirmé).
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from jibi2 import config
from outils import outil

MAX_LECTURE = 4000  # caractères renvoyés au modèle


def _racine() -> Path:
    racine = config.DOSSIER_FICHIERS
    racine.mkdir(parents=True, exist_ok=True)
    return racine


def _chemin_espace(nom: str) -> Path:
    racine = _racine().resolve()
    chemin = (racine / nom).resolve()
    if not chemin.is_relative_to(racine):
        raise ValueError("Le nom doit rester dans l'espace de travail (donnees/fichiers).")
    return chemin


def _taille_humaine(n: int) -> str:
    if n < 1024:
        return f"{n} o"
    for unite in ("Ko", "Mo", "Go"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.1f} {unite}"
    return f"{n:.1f} To"


@outil("lister_dossier", "Liste les fichiers de l'espace de travail de JIBI (dossier donnees/fichiers).",
       {"dossier": {"type": "str", "obligatoire": False,
                    "description": "sous-dossier relatif ; vide = la racine de l'espace"}},
       categorie="fichiers", exemple='{"outil": "lister_dossier", "parametres": {}}')
def lister_dossier(dossier: str = "") -> str:
    chemin = _chemin_espace(dossier or ".")
    if not chemin.exists():
        return f"Le dossier « {dossier} » n'existe pas dans l'espace de travail."
    if chemin.is_file():
        return f"C'est un fichier : {chemin.name} ({_taille_humaine(chemin.stat().st_size)})."
    entrees = sorted(chemin.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    if not entrees:
        return "Le dossier est vide."
    lignes = [f"📁 {e.name}/" if e.is_dir() else f"📄 {e.name} ({_taille_humaine(e.stat().st_size)})"
              for e in entrees[:60]]
    return f"{len(entrees)} élément(s) :\n" + "\n".join(lignes)


@outil("lire_fichier", "Lit un fichier texte de l'espace de travail de JIBI.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier, relatif à l'espace"}},
       categorie="fichiers")
def lire_fichier(nom: str) -> str:
    chemin = _chemin_espace(nom)
    if not chemin.is_file():
        return f"Le fichier « {nom} » n'existe pas dans l'espace de travail."
    texte = chemin.read_text(encoding="utf-8", errors="replace")
    if len(texte) > MAX_LECTURE:
        return texte[:MAX_LECTURE] + f"\n… (tronqué, {len(texte)} caractères au total)"
    return texte or "(fichier vide)"


@outil("ecrire_fichier", "Crée ou remplace un fichier texte dans l'espace de travail de JIBI.",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier à écrire"},
        "contenu": {"type": "str", "obligatoire": True, "description": "contenu complet du fichier"}},
       categorie="fichiers", risque="moyen")
def ecrire_fichier(nom: str, contenu: str) -> str:
    chemin = _chemin_espace(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")
    return f"Fichier « {chemin.name} » écrit ({len(contenu)} caractères)."


@outil("ajouter_fichier", "Ajoute du texte à la fin d'un fichier de l'espace de travail (le crée s'il n'existe pas).",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier"},
        "contenu": {"type": "str", "obligatoire": True, "description": "texte à ajouter"}},
       categorie="fichiers", risque="moyen")
def ajouter_fichier(nom: str, contenu: str) -> str:
    chemin = _chemin_espace(nom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as f:
        f.write(contenu.rstrip() + "\n")
    return f"Texte ajouté à « {chemin.name} »."


@outil("supprimer_fichier", "Supprime un fichier de l'espace de travail (en réalité : déplacé dans donnees/corbeille, récupérable).",
       {"nom": {"type": "str", "obligatoire": True, "description": "nom du fichier à supprimer"}},
       categorie="fichiers", risque="moyen")
def supprimer_fichier(nom: str) -> str:
    chemin = _chemin_espace(nom)
    if not chemin.exists():
        return f"« {nom} » n'existe pas."
    corbeille = config.DOSSIER_CORBEILLE
    corbeille.mkdir(parents=True, exist_ok=True)
    destination = corbeille / f"{chemin.name}.{int(time.time())}"
    shutil.move(str(chemin), str(destination))
    return f"« {chemin.name} » déplacé vers la corbeille (donnees/corbeille)."


@outil("chercher_fichier", "Cherche les fichiers de l'espace de travail dont le nom contient un mot.",
       {"mot": {"type": "str", "obligatoire": True, "description": "morceau de nom à chercher"}},
       categorie="fichiers")
def chercher_fichier(mot: str) -> str:
    racine = _racine()
    trouves = [e for e in racine.rglob("*") if mot.lower() in e.name.lower()][:30]
    if not trouves:
        return f"Aucun fichier ne contient « {mot} » dans son nom."
    return "\n".join(str(e.relative_to(racine)) for e in trouves)


@outil("lire_fichier_pc", "Lit un fichier texte N'IMPORTE OÙ sur le PC (lecture seule).",
       {"chemin": {"type": "str", "obligatoire": True,
                   "description": "chemin complet, ex. C:/Users/moi/Documents/notes.txt"}},
       categorie="fichiers", risque="eleve")
def lire_fichier_pc(chemin: str) -> str:
    cible = Path(chemin).expanduser()
    if not cible.is_file():
        return f"Introuvable ou pas un fichier : {chemin}"
    texte = cible.read_text(encoding="utf-8", errors="replace")
    if len(texte) > MAX_LECTURE:
        return texte[:MAX_LECTURE] + f"\n… (tronqué, {len(texte)} caractères au total)"
    return texte or "(fichier vide)"


@outil("lister_dossier_pc", "Liste le contenu d'un dossier N'IMPORTE OÙ sur le PC (lecture seule).",
       {"chemin": {"type": "str", "obligatoire": False,
                   "description": "chemin complet ; vide = dossier personnel"}},
       categorie="fichiers", risque="eleve")
def lister_dossier_pc(chemin: str = "") -> str:
    cible = Path(chemin).expanduser() if chemin else Path.home()
    if not cible.is_dir():
        return f"Dossier introuvable : {chemin}"
    entrees = sorted(cible.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))[:80]
    if not entrees:
        return "Dossier vide."
    lignes = [f"📁 {e.name}/" if e.is_dir() else f"📄 {e.name}" for e in entrees]
    return f"{cible} — {len(entrees)} élément(s) :\n" + "\n".join(lignes)
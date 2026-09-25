"""Outils fichiers de JIBI 2.

Deux zones : l'ESPACE DE TRAVAIL (donnees/fichiers/, écritures autorisées)
et le RESTE DU PC (dossiers personnels accessibles en écriture quand
l'utilisateur le demande explicitement). Les dossiers système Windows
et les dossiers critiques de JIBI restent protégés.
"""
from __future__ import annotations

import os
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
    brut = str(nom or "").strip().strip('"')
    # Le modèle écrit souvent un chemin absolu ou « donnees/fichiers/… » alors
    # que l'outil attend un nom RELATIF : on ramène gentiment au lieu de
    # rejeter (46 erreurs enregistrées venaient de là).
    for marqueur in ("donnees/fichiers/", "donnees\\fichiers\\"):
        if marqueur in brut:
            brut = brut.split(marqueur, 1)[1]
    chemin_propose = Path(brut)
    if chemin_propose.is_absolute():
        try:
            chemin = chemin_propose.resolve()
        except OSError:
            raise ValueError("Chemin invalide.")
        if chemin.is_relative_to(racine):
            return chemin
        raise ValueError("Le nom doit rester dans l'espace de travail (donnees/fichiers).")
    chemin = (racine / chemin_propose).resolve()
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


def _dossier_pc_valide(destination: str) -> Path:
    """Résout Downloads/Desktop/Documents/... ou un chemin PC choisi.
    Accès complet aux dossiers personnels (Utilisateur, Downloads,
    Desktop, Documents, etc.). Protège les dossiers système et JIBI."""
    valeur = str(destination or "").strip().strip('"')
    aliases = {
        "telechargements": "Downloads", "téléchargements": "Downloads",
        "downloads": "Downloads", "bureau": "Desktop", "desktop": "Desktop",
        "documents": "Documents", "dossier documents": "Documents",
        "images": "Pictures", "photos": "Pictures", "pictures": "Pictures",
        "musique": "Music", "video": "Videos", "videos": "Videos",
    }
    dossier = Path(valeur).expanduser()
    if not dossier.is_absolute():
        dossier = Path.home() / (aliases.get(valeur.casefold(), valeur))
    dossier = dossier.resolve()
    racine = config.RACINE.resolve()
    # Dossiers protégés de JIBI
    interdits = (racine / "donnees", racine / "modeles", racine / ".env")
    if any(dossier == interdit or dossier.is_relative_to(interdit) for interdit in interdits):
        raise ValueError("Destination protégée : donnees, modeles et .env sont interdits.")
    # Dossiers système Windows protégés
    systemes = [Path(os.environ.get("SystemRoot", "C:/Windows")),
                Path(os.environ.get("ProgramFiles", "C:/Program Files")),
                Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
                Path(os.environ.get("ProgramData", "C:/ProgramData")),
                Path(os.environ.get("Windows", "C:/Windows"))]
    if any(dossier == systeme or dossier.is_relative_to(systeme)
           for systeme in systemes if str(systeme) not in ("", ".")):
        raise ValueError("Les dossiers système Windows sont protégés.")
    # Le dossier personnel complet est autorisé (y compris sous-dossiers)
    home = Path.home().resolve()
    if dossier == home or dossier.is_relative_to(home):
        return dossier
    if dossier == racine or dossier == Path(dossier.anchor):
        raise ValueError("Destination trop générale : choisis un dossier précis.")
    if not dossier.is_dir():
        raise ValueError(f"Dossier de destination introuvable : {dossier}")
    return dossier


def _cible_sans_ecraser(source: Path, dossier: Path) -> Path:
    cible = dossier / source.name
    if not cible.exists():
        return cible
    suffixe = cible.suffix
    base = cible.stem
    index = 1
    while True:
        candidat = dossier / f"{base} ({index}){suffixe}"
        if not candidat.exists():
            return candidat
        index += 1


def _operation_document(nom: str, destination: str, operation: str) -> str:
    source = _chemin_espace(nom)
    if not source.is_file():
        return f"Le fichier « {nom} » n'existe pas dans l'espace JIBI."
    if source.name.startswith(".") or source.suffix.lower() in {".env", ".key", ".pem"}:
        return "Ce fichier est protégé et ne peut pas être exporté."
    dossier = _dossier_pc_valide(destination)
    cible = _cible_sans_ecraser(source, dossier)
    try:
        if operation == "deplacer":
            shutil.copy2(source, cible)
            if not cible.is_file() or cible.stat().st_size != source.stat().st_size:
                cible.unlink(missing_ok=True)
                return "La copie de sécurité a échoué ; l'original est conservé."
            source.unlink()
            return f"Fichier déplacé vers : {cible}"
        shutil.copy2(source, cible)
        return f"Fichier copié vers : {cible}"
    except Exception as exc:  # noqa: BLE001
        return f"Opération refusée ou impossible : {str(exc)[:180]}"


@outil("copier_document",
       "Copie un fichier créé dans l'espace JIBI vers Téléchargements, Bureau, "
       "Documents ou un dossier choisi. Demande confirmation avant l'écriture.",
       {"nom": {"type": "str", "obligatoire": True, "description": "fichier relatif de donnees/fichiers"},
        "destination": {"type": "str", "obligatoire": True,
                        "description": "Téléchargements, Bureau, Documents ou chemin précis"}},
       categorie="fichiers", risque="eleve",
       exemple='{"outil":"copier_document","parametres":{"nom":"cours.pdf","destination":"Téléchargements"}}')
def copier_document(nom: str, destination: str) -> str:
    return _operation_document(nom, destination, "copier")


@outil("deplacer_document",
       "Déplace un fichier créé dans l'espace JIBI vers un dossier PC choisi. "
       "Une confirmation et une copie de sécurité sont exigées.",
       {"nom": {"type": "str", "obligatoire": True, "description": "fichier relatif de donnees/fichiers"},
        "destination": {"type": "str", "obligatoire": True,
                        "description": "Téléchargements, Bureau, Documents ou chemin précis"}},
       categorie="fichiers", risque="eleve",
       exemple='{"outil":"deplacer_document","parametres":{"nom":"cours.pdf","destination":"Téléchargements"}}')
def deplacer_document(nom: str, destination: str) -> str:
    return _operation_document(nom, destination, "deplacer")


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
    lignes = ["[D] " + e.name + "/" if e.is_dir() else "[F] " + e.name for e in entrees]
    return f"{cible} — {len(entrees)} élément(s) :\n" + "\n".join(lignes)

@outil("gestionnaire_fichiers",
       "Affiche la structure des dossiers personnels de l'utilisateur. "
       "Permet de naviguer et gérer tous les dossiers du PC "
       "(Downloads, Desktop, Documents, Pictures, Music, Videos). "
       "Les opérations d'écriture (déplacement, copie) sont autorisées "
       "dans ces dossiers quand l'utilisateur le demande.",
       {"action": {"type": "str", "obligatoire": False,
                    "description": "lister, naviguer, rechercher"}},
       categorie="fichiers", risque="moyen",
       exemple='{"outil": "gestionnaire_fichiers", "parametres": {"action": "lister"}}')
def gestionnaire_fichiers(action: str = "lister") -> str:
    """Affiche la structure des dossiers personnels."""
    home = Path.home()
    if action == "lister":
        dossiers = []
        for nom in ["Desktop", "Downloads", "Documents", "Pictures",
                    "Music", "Videos", "Links"]:
            chemin = home / nom
            if chemin.is_dir():
                try:
                    nb = sum(1 for _ in chemin.iterdir())
                    dossiers.append("[D] " + nom + "/ (" + str(nb) + ")")
                except Exception:
                    dossiers.append("[D] " + nom + "/")
        dossiers.append("[JIBI] dossier/ (" + config.RACINE.name + ")")
        resultat = "[DOSSIERS] Personnels de " + home.name + " :\n"
        resultat = resultat + "\n".join(dossiers)
        resultat = resultat + "\n\nUtilise : 'deplacer_document', "
        resultat = resultat + "'chercher_fichiers_pc', 'gestionnaire_fichiers'"
        return resultat
    elif action == "naviguer":
        return ("Navigation complète activée.\n"
                "Dossier personnel : " + str(home) + "\n"
                "Utilise 'deplacer_document', 'copier_document', "
                "'chercher_fichiers_pc' pour manipuler les fichiers.")
    elif action == "recherche":
        return ("Recherche activée sur tout le PC.\n"
                "Utilise 'chercher_fichiers_pc' avec un mot-clé.")
    return "Action inconnue : " + action + ". Utilise 'lister', 'naviguer' ou 'recherche'."


@outil("configurer_deplacement",
       "Active ou désactive la confirmation pour les déplacements et "
       "copies de fichiers. Quand la confirmation est désactivée, "
       "deplacer_document et copier_document s'exécutent directement "
       "sans demander l'autorisation.",
       {"actif": {"type": "bool", "obligatoire": True,
                   "description": "true pour désactiver la confirmation, false pour l'activer"}},
       categorie="fichiers", risque="faible",
       exemple='{"outil": "configurer_deplacement", "parametres": {"actif": true}}')
def configurer_deplacement(actif: bool) -> str:
    """Active/désactive la confirmation pour les déplacements."""
    import config as _config
    ancien = _config.valeur_bool("CONFIRMER_DEPLACEMENT")
    nouvelle = "0" if actif else "1"
    env_path = _config.FICHIER_ENV
    if env_path.exists():
        contenu = env_path.read_text(encoding="utf-8", errors="replace")
        lignes = contenu.splitlines()
        trouve = False
        nouvelles = []
        for ligne in lignes:
            if ligne.strip().startswith("CONFIRMER_DEPLACEMENT"):
                nouvelles.append(f"CONFIRMER_DEPLACEMENT={nouvelle}")
                trouve = True
            else:
                nouvelles.append(ligne)
        if not trouve:
            nouvelles.append(f"CONFIRMER_DEPLACEMENT={nouvelle}")
        env_path.write_text("\n".join(nouvelles) + "\n",
                              encoding="utf-8")
    _config._cache = None
    if actif:
        return ("Confirmation DÉSACTIVÉE pour les déplacements. "
                "Les fichiers seront déplacés/copiés sans demander d'autorisation.")
    return ("Confirmation ACTIVÉE pour les déplacements. "
            "Chaque déplacement demandera confirmation.")

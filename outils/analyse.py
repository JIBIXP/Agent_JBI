"""Analyse locale de fichiers et de dossiers pour JIBI.

Les fichiers de l'espace ``donnees/fichiers`` sont simples à analyser. Un
chemin absolu sur le PC passe par un outil à risque élevé et une confirmation.
Les secrets usuels (.env, clés, cookies,etc.) sont refusés même en lecture.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path

from outils import outil

MAX_FICHIER = 25 * 1024 * 1024
MAX_TEXTE = 2_000_000
INTERDITS = (".env", "credentials", "cookies", "login data", "id_rsa", "id_ed25519",
             ".key", ".pem", ".pfx", ".kdbx", "shadow", "sam", "ntds.dit")
STOP = set("""a au aux avec ce ces dans de des du elle en et eux il je la le les leur
lui ma mais me même mes moi mon ne nos notre nous on ou par pas pour qu que qui sa se
ses son sur ta te tes toi ton tu un une vos votre vous c d j l m n s t y été être plus
""".split())


def _refuse(chemin: Path) -> str:
    nom = chemin.name.lower()
    if (nom in INTERDITS or nom.startswith(("credentials", "cookies", "login data",
                                               "id_rsa", "id_ed25519"))
            or nom.endswith((".key", ".pem", ".pfx", ".kdbx"))
            or "shadow" in nom or "ntds.dit" in nom):
        return "Analyse refusée : ce fichier ressemble à un secret ou à une base d'identifiants."
    return ""


def _resoudre(chemin: str, espace: bool = False) -> tuple[Path | None, str]:
    if not chemin:
        return None, "Chemin manquant."
    if espace or not (Path(chemin).is_absolute() or ":" in chemin or "\\" in chemin):
        from outils.fichiers import _chemin_espace
        try:
            return _chemin_espace(chemin), ""
        except ValueError as e:
            return None, str(e)
    return Path(chemin).expanduser().resolve(), ""


def _texte(chemin: Path) -> tuple[str, str]:
    suffixe = chemin.suffix.lower()
    if suffixe == ".docx":
        try:
            with zipfile.ZipFile(chemin) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", "replace")
            return re.sub(r"<[^>]+>", " ", xml), "Word"
        except (OSError, KeyError, zipfile.BadZipFile) as e:
            return "", f"document illisible ({e})"
    if suffixe == ".pdf":
        try:
            import pypdf  # type: ignore[import-not-found]
            lecteur = pypdf.PdfReader(str(chemin))
            return "\n".join(page.extract_text() or "" for page in lecteur.pages), "PDF"
        except Exception:
            # Sans dépendance : on extrait les chaînes ASCII/UTF-16 usuelles.
            brut = chemin.read_bytes()[:MAX_TEXTE]
            morceaux = re.findall(rb"[ -~]{4,}", brut)
            return "\n".join(m.decode("latin1", "replace") for m in morceaux), "PDF (texte approximatif)"
    try:
        return chemin.read_text(encoding="utf-8", errors="replace")[:MAX_TEXTE], "texte"
    except UnicodeError:
        return chemin.read_bytes()[:MAX_TEXTE].decode("latin1", "replace"), "binaire"


def _resume(chemin: Path) -> str:
    try:
        taille = chemin.stat().st_size
    except OSError as e:
        return f"Fichier inaccessible : {e}"
    if taille > MAX_FICHIER:
        return f"Fichier trop volumineux pour l'analyse ({taille / 1024 / 1024:.1f} Mo)."
    refus = _refuse(chemin)
    if refus:
        return refus
    if chemin.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        try:
            from PIL import Image
            with Image.open(chemin) as image:
                return (f"Fichier : {chemin.name}\nType : image\nTaille : {taille} octets\n"
                        f"Format : {image.format}\nDimensions : {image.width}×{image.height}\n"
                        f"Mode : {image.mode}\nSHA-256 : {hashlib.sha256(chemin.read_bytes()).hexdigest()}")
        except Exception as e:
            return f"Fichier : {chemin.name}\nType : image\nTaille : {taille} octets\nAnalyse visuelle impossible : {e}"
    texte, type_document = _texte(chemin)
    mots = re.findall(r"[\wÀ-ÿ'-]{2,}", texte.lower())
    utiles = [m for m in mots if m not in STOP and not m.isdigit()]
    frequences = Counter(utiles).most_common(8)
    lignes = len(texte.splitlines()) if texte else 0
    details = [f"Fichier : {chemin.name}", f"Type : {type_document}",
               f"Taille : {taille} octets", f"Caractères lus : {len(texte)}",
               f"Lignes : {lignes}", f"Mots : {len(mots)}"]
    if suffixe := chemin.suffix.lower():
        details.append(f"Extension : {suffixe}")
    if chemin.suffix.lower() == ".json" and texte:
        try:
            json.loads(texte)
            details.append("JSON valide")
        except json.JSONDecodeError as e:
            details.append(f"JSON invalide : ligne {e.lineno}")
    if chemin.suffix.lower() == ".csv" and texte:
        try:
            details.append(f"CSV : {max(0, len(texte.splitlines()) - 1)} ligne(s) de données")
        except csv.Error as e:
            details.append(f"CSV à vérifier : {e}")
    if chemin.suffix.lower() in (".py", ".js", ".ts", ".html", ".css"):
        details.append(f"Fonctions/méthodes : {len(re.findall(r'\b(def|function)\s+\w+', texte))}")
    if frequences:
        details.append("Mots fréquents : " + ", ".join(f"{mot} ({nombre})" for mot, nombre in frequences))
    details.append("SHA-256 : " + hashlib.sha256(chemin.read_bytes()).hexdigest())
    return "\n".join(details)


@outil("analyser_fichier",
       "Analyse un fichier local : type, taille, texte, statistiques, structure et "
       "empreinte SHA-256. Un chemin absolu du PC demande une confirmation ; les "
       "secrets usuels sont toujours refusés.",
       {"chemin": {"type": "str", "obligatoire": True,
                   "description": "nom dans donnees/fichiers ou chemin absolu du PC"}},
       categorie="fichiers", risque="eleve",
       exemple='{"outil": "analyser_fichier", "parametres": {"chemin": "rapport.pdf"}}')
def analyser_fichier(chemin: str) -> str:
    # Si l'utilisateur dit "ce fichier", "ce document", "ça" → dernier fichier importé
    if chemin.lower().strip() in ("ce fichier", "ce document", "ce fichier importé",
                                   "ça", "ceci", "le fichier", "le document"):
        import_dir = config.DOSSIER_FICHIERS / "imports"
        if import_dir.is_dir():
            fichiers = sorted(import_dir.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
            if fichiers and fichiers[0].is_file():
                chemin = str(fichiers[0])
            else:
                return "Aucun fichier récemment importé. Importe un fichier d'abord."
        else:
            return "Dossier d'import introuvable."
    cible, erreur = _resoudre(chemin)
    if cible is None:
        return erreur
    if not cible.is_file():
        return f"Fichier introuvable : {chemin}"
    return _resume(cible)


@outil("chercher_fichiers_pc",
       "Cherche un fichier par nom dans le PC (lecture seule), en ignorant les "
       "dossiers système volumineux. Les chemins trouvés peuvent ensuite être "
       "passés à analyser_fichier.",
       {"mot": {"type": "str", "obligatoire": True, "description": "morceau du nom"},
        "racine": {"type": "str", "obligatoire": False,
                    "description": "dossier de départ ; vide = dossier personnel"},
        "limite": {"type": "int", "obligatoire": False,
                    "description": "maximum de résultats (défaut 50)"}},
       categorie="fichiers", risque="eleve",
       exemple='{"outil": "chercher_fichiers_pc", "parametres": {"mot": "contrat"}}')
def chercher_fichiers_pc(mot: str, racine: str = "", limite: int = 50) -> str:
    if not (mot or "").strip():
        return "Motif de recherche vide."
    base = Path(racine).expanduser() if racine else Path.home()
    if not base.is_dir():
        return f"Dossier de recherche introuvable : {base}"
    limite = max(1, min(int(limite), 200))
    ignores = {".git", "node_modules", "$recycle.bin", "system volume information",
               "windows", "program files", "program files (x86)", "appdata"}
    trouves: list[str] = []
    for courant, sous_dossiers, noms in os.walk(str(base), topdown=True, onerror=lambda _e: None):
        courant_bas = Path(courant).name.lower()
        if courant_bas in ignores or len(Path(courant).relative_to(base).parts) > 7:
            sous_dossiers[:] = []
            continue
        for nom in noms:
            if mot.lower() in nom.lower():
                trouves.append(str(Path(courant) / nom))
                if len(trouves) >= limite:
                    return "\n".join(trouves)
    return "\n".join(trouves) if trouves else f"Aucun fichier trouvé pour « {mot} »."


@outil("analyser_dossier",
       "Analyse un dossier local : nombre de fichiers, types, tailles, plus gros "
       "fichiers et profondeur. Ne suit pas les liens vers un autre disque.",
       {"chemin": {"type": "str", "obligatoire": False,
                   "description": "dossier ; vide = donnees/fichiers"},
        "profondeur": {"type": "int", "obligatoire": False,
                       "description": "profondeur maximale (défaut 2, max 5)"},
        "limite": {"type": "int", "obligatoire": False,
                    "description": "maximum de fichiers (défaut 500)"}},
       categorie="fichiers", risque="eleve",
       exemple='{"outil": "analyser_dossier", "parametres": {"chemin": "C:/Users/moi/Documents"}}')
def analyser_dossier(chemin: str = "", profondeur: int = 2, limite: int = 500) -> str:
    if not chemin:
        from outils.fichiers import _racine
        racine = _racine().resolve()
    else:
        racine, erreur = _resoudre(chemin)
        if racine is None:
            return erreur
    if not racine.is_dir():
        return f"Dossier introuvable : {chemin or racine}"
    profondeur = max(1, min(int(profondeur), 5))
    limite = max(1, min(int(limite), 2000))
    base = racine.resolve()
    fichiers: list[Path] = []
    for courant, sous_dossiers, noms in os.walk(str(racine)):
        chemin_courant = Path(courant).resolve()
        if not chemin_courant.is_relative_to(base):
            sous_dossiers[:] = []
            continue
        profondeur_courante = len(chemin_courant.relative_to(base).parts)
        if profondeur_courante >= profondeur:
            sous_dossiers[:] = []
        for nom in noms:
            fichier = (chemin_courant / nom).resolve()
            if fichier.is_relative_to(base) and fichier.is_file():
                fichiers.append(fichier)
                if len(fichiers) >= limite:
                    break
        if len(fichiers) >= limite:
            break
    tailles = []
    par_type: Counter = Counter()
    for fichier in fichiers:
        try:
            taille = fichier.stat().st_size
        except OSError:
            continue
        tailles.append((taille, fichier))
        par_type[fichier.suffix.lower() or "(sans extension)"] += 1
    total = sum(taille for taille, _ in tailles)
    lignes = [f"Dossier : {racine}", f"Fichiers analysés : {len(tailles)}",
              f"Taille totale : {total / 1024 / 1024:.1f} Mo",
              "Types : " + ", ".join(f"{ext}={nombre}" for ext, nombre in par_type.most_common(10))]
    if tailles:
        lignes.append("Plus gros : " + ", ".join(
            f"{fichier.name} ({taille / 1024 / 1024:.1f} Mo)"
            for taille, fichier in sorted(tailles, reverse=True)[:5]))
    return "\n".join(lignes)

"""Importation seguro de documents et images dans l'espace JIBI."""
from __future__ import annotations

import io
import re
import shutil
import time
import zipfile
from pathlib import Path

from jibi2 import config
from outils import outil

DOCUMENTS = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".json",
             ".html", ".htm", ".odt", ".rtf", ".pptx"}
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
SECRETS = re.compile(r"(?:\.env|cookie|login\s*data|password|passwd|secret|token|api[_-]?key|private[_-]?key|\.pem$|\.key$)", re.I)


def _refuse_source(cible: Path) -> str:
    racine = config.RACINE.resolve()
    if cible == (racine / ".env").resolve() or cible.is_relative_to(config.DOSSIER_DONNEES.resolve()):
        return "Import refusé : les secrets et le dossier donnees/ sont protégés."
    if cible.is_relative_to(config.DOSSIER_MODELES.resolve()):
        return "Import refusé : modeles/ est protégé."
    if cible.is_relative_to((racine / ".git").resolve()):
        return "Import refusé : les fichiers Git internes sont protégés."
    if SECRETS.search(cible.name):
        return "Import refusé : ce nom ressemble à un secret ou à une donnée sensible."
    return ""


def _destination_import(nom: str, type_fichier: str = "auto") -> tuple[Path | None, str]:
    nom_propre = Path(str(nom or "")).name
    if not nom_propre or nom_propre != str(nom or "") or "/" in nom_propre or "\\" in nom_propre:
        return None, "Nom de fichier refusé."
    if SECRETS.search(nom_propre):
        return None, "Import refusé : ce nom ressemble à un secret."
    extension = Path(nom_propre).suffix.lower()
    if type_fichier.lower() == "image" and extension not in IMAGES:
        return None, "Ce fichier n'est pas une image autorisée."
    if type_fichier.lower() == "document" and extension not in DOCUMENTS:
        return None, "Ce fichier n'est pas un document autorisé."
    if extension not in DOCUMENTS | IMAGES:
        return None, "Type non pris en charge. Documents et images uniquement."
    racine = config.DOSSIER_FICHIERS / "imports"
    racine.mkdir(parents=True, exist_ok=True)
    destination = racine / nom_propre
    if destination.exists():
        destination = racine / f"{Path(nom_propre).stem}_{int(time.time())}{extension}"
    return destination, ""


def _valider_contenu(nom: str, source) -> str:
    extension = Path(nom).suffix.lower()
    try:
        if extension in IMAGES:
            from PIL import Image
            with Image.open(source) as image:
                image.verify()
        elif extension in {".docx", ".xlsx", ".pptx", ".odt"} and not zipfile.is_zipfile(source):
            return "Le document OOXML est illisible ou corrompu."
        elif extension == ".pdf":
            if hasattr(source, "read"):
                source.seek(0)
                entete = source.read(5)
                source.seek(0)
            else:
                with open(source, "rb") as flux:
                    entete = flux.read(5)
            if entete != b"%PDF-":
                return "Le fichier PDF est illisible."
    except Exception:
        return "Le contenu du fichier est illisible."
    return ""


def _copier(chemin: str, type_fichier: str = "auto") -> str:
    if not (chemin or "").strip():
        return "Chemin de fichier manquant."
    try:
        source = Path(chemin).expanduser().resolve()
    except (OSError, RuntimeError):
        return "Chemin de fichier invalide."
    if not source.is_file():
        return f"Fichier introuvable : {chemin}"
    raison = _refuse_source(source)
    if raison:
        return raison
    extension = source.suffix.lower()
    if type_fichier.lower() == "image" and extension not in IMAGES:
        return "Ce fichier n'est pas une image autorisée."
    if type_fichier.lower() == "document" and extension not in DOCUMENTS:
        return "Ce fichier n'est pas un document autorisé."
    if extension not in DOCUMENTS | IMAGES:
        return "Type non pris en charge. Documents et images uniquement."
    try:
        taille = source.stat().st_size
    except OSError:
        return "Impossible de lire la taille du fichier."
    if taille > 50 * 1024 * 1024:
        return "Import refusé : fichier supérieur à 50 Mo."
    raison = _valider_contenu(source.name, source)
    if raison:
        return raison
    racine = config.DOSSIER_FICHIERS / "imports"
    racine.mkdir(parents=True, exist_ok=True)
    destination = racine / source.name
    if destination.exists():
        destination = racine / f"{source.stem}_{int(time.time())}{source.suffix}"
    try:
        shutil.copy2(source, destination)
    except OSError as exc:
        return f"Import impossible : {str(exc)[:180]}"
    return f"Import réussi : {source.name} est disponible dans donnees/fichiers/imports/{destination.name}."


def importer_buffer(nom: str, donnees: bytes, type: str = "auto") -> str:
    """Enregistre un fichier envoyé par le sélecteur du panneau web."""
    if not isinstance(donnees, (bytes, bytearray)) or len(donnees) > 50 * 1024 * 1024:
        return "Import refusé : fichier vide ou supérieur à 50 Mo."
    destination, raison = _destination_import(nom, type)
    if destination is None:
        return raison
    raison = _valider_contenu(destination.name, io.BytesIO(bytes(donnees)))
    if raison:
        return raison
    try:
        destination.write_bytes(bytes(donnees))
    except OSError as exc:
        return f"Import impossible : {str(exc)[:180]}"
    return f"Import réussi : {destination.name} est disponible dans donnees/fichiers/imports."


def _fichier_importe(nom_source: str) -> Path | None:
    """Retrouve le fichier VRAIMENT importé à l'instant.

    En cas de collision de nom, _copier renomme « rapport_1758… » : chercher
    le nom d'origine trouvait l'ANCIEN fichier (analyse du mauvais document).
    On prend donc le plus récent parmi : nom exact, ou même racine du nom.
    """
    import_dir = config.DOSSIER_FICHIERS / "imports"
    if not import_dir.is_dir():
        return None
    tige = Path(nom_source).stem.lower()
    candidates: list[tuple[float, Path]] = []
    seuil = time.time() - 60          # import des 60 dernières secondes seulement
    for fichier in import_dir.glob("*"):
        if not fichier.is_file():
            continue
        try:
            quand = fichier.stat().st_mtime
        except OSError:
            continue
        if quand < seuil:
            continue
        if fichier.name.lower() == nom_source.lower() or fichier.stem.lower().startswith(tige):
            candidates.append((quand, fichier))
    if not candidates:
        return None
    return max(candidates, key=lambda paire: paire[0])[1]


@outil("importer_fichier",
       "Importe dans JIBI un document ou une image choisi par l'utilisateur. "
       "Le fichier est copié dans donnees/fichiers/imports, analysé automatiquement, "
       "et le résultat est retourné au chat. Utilise aussi analyser_fichier ou voir_image.",
       {"chemin": {"type": "str", "obligatoire": True, "description": "chemin complet du fichier choisi"},
        "type": {"type": "str", "obligatoire": False, "description": "auto, document ou image"}},
       categorie="fichiers", risque="moyen",
       exemple='{"outil": "importer_fichier", "parametres": {"chemin": "C:/Users/moi/Documents/rapport.pdf"}}')
def importer_fichier(chemin: str, type: str = "auto") -> str:
    resultat = _copier(chemin, type)
    if resultat.startswith(("Import refusé", "Chemin de fichier", "Fichier introuvable",
                           "Type non pris", "Impossible de lire", "Import impossible")):
        raise ValueError(resultat)
    # Analyse automatique du fichier réellement importé (gère le renommage)
    try:
        from outils.analyse import analyser_fichier
        importe = _fichier_importe(Path(chemin).name)
        if importe is not None:
            analyse = analyser_fichier(str(importe))
            return resultat + "\n\n📄 Analyse du fichier :\n" + analyse
    except Exception:
        pass
    return resultat + "\n\n💡 Utilise 'analyser_fichier' pour une analyse détaillée."

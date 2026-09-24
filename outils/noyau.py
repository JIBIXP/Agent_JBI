"""Modifications du NOYAU de JIBI — autonomie explicite et transactionnelle.

L'utilisateur a accordé à JIBI le droit de modifier tout son code :
- `JIBI_MODIFICATION_AUTO=1` active le mode de modification, mais
  `JIBI_AUTONOMIE_NOYAU=0` conserve une confirmation humaine avant
  `modifier_noyau` et `restaurer_noyau` ;
- les autres actions dangereuses (terminal, extinction du PC) continuent
  de demander leur confirmation ;
- les secrets, les données, les modèles et tout chemin extérieur restent
  toujours interdits.

Filet de sécurité pour chaque modification :
1. l'ancien fichier est sauvegardé dans donnees/historique_noyau/ ;
2. la syntaxe est vérifiée immédiatement — erreur → retour arrière auto ;
3. la suite de tests complète est relancée — échec → retour arrière auto ;
4. tout est noté dans le CHANGELOG et l'ancienne version reste restaurable.

JIBI peut aussi relire un fichier du noyau ou remplacer un extrait unique,
ce qui évite de renvoyer un fichier de 200 000 caractères au modèle local.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from outils import outil
from jibi2 import audit

PERMIS = (
    "jibi2/*.py", "jibi2/*.md",
    "outils/*.py", "outils/*.md",
    "interface/*.py", "interface/*.html",
    "audio/*.py", "tests/*.py",
    "run.py", "docteur.py", "*.bat",
    "*.md", "VERSION", "requirements.txt", "ruff.toml",
)
INTERDITS_TOUJOURS = (".env", "donnees/", "modeles/", "jibi_files/", "logs/")
MAX_TAILLE = 200_000                    # caractères d'un coup, ça suffit


def _racine() -> Path:
    from jibi2 import config
    return config.RACINE


def _chemin_sur(fichier: str) -> tuple[Path | None, str]:
    """Chemin absolu si le fichier est modifiable, sinon (None, raison)."""
    brut = (fichier or "").strip().replace("\\", "/").lstrip("/")
    if not brut or ".." in brut or ":" in brut or brut.startswith("~"):
        return None, "chemin refusé (relatif au dossier JIBI, sans remontée)."
    bas = brut.lower()
    for interdit in INTERDITS_TOUJOURS:
        if bas == interdit.rstrip("/") or bas.startswith(interdit):
            return None, f"« {interdit} » n'est jamais modifiable (données ou secrets)."
    if not any(re.match(pattern_to_regex(p), bas) for p in PERMIS):
        return None, ("fichier hors du noyau modifiable. Autorisés : "
                      "jibi2/, outils/, interface/, audio/, tests/, run.py, "
                      "docteur.py, scripts .bat, documentation et configuration du projet.")
    racine = _racine().resolve()
    candidat = (racine / brut).resolve(strict=False)
    try:
        dans_projet = candidat.is_relative_to(racine)
    except AttributeError:       # Python 3.8/3.9 : contrôle équivalent
        dans_projet = racine == candidat or racine in candidat.parents
    if not dans_projet:
        return None, "chemin refusé (le lien ou le chemin sort du dossier JIBI)."
    return candidat, ""


def pattern_to_regex(motif: str) -> str:
    motif = motif.lower()
    corps = motif.replace(".", r"\.").replace("*", ".*").replace("?.", "\\?.")
    return "^" + corps + "$"


def _sauvegarder(chemin: Path) -> Path | None:
    """Copie l'ancien fichier dans donnees/historique_noyau/. None si neuf."""
    if not chemin.exists():
        return None
    from jibi2 import config
    relatif = chemin.relative_to(_racine())
    destination = config.DOSSIER_DONNEES / "historique_noyau" / \
        str(relatif).replace("\\", "/").replace("/", "__")
    destination.parent.mkdir(parents=True, exist_ok=True)
    copie = destination.with_name(f"{destination.name}.{time.time_ns()}")
    shutil.copy2(chemin, copie)
    return copie


def _annuler(chemin: Path, sauvegarde: Path | None) -> None:
    if sauvegarde is not None:
        shutil.copy2(sauvegarde, chemin)
    else:
        chemin.unlink(missing_ok=True)


def _verifier_suite() -> tuple[bool, str]:
    import subprocess
    import sys
    racine = _racine()
    script = racine / "tests" / "verification.py"
    if not script.exists():
        return False, "suite de vérification introuvable"

    def _ignorer(_dossier, noms):
        return {nom for nom in noms
                if nom in {".git", "__pycache__", "donnees", "modeles"}
                or nom.endswith(".pyc")}

    try:
        # La suite historique modifie des fichiers de test et le CHANGELOG.
        # On l'exécute dans une copie jetable pour que la transaction du noyau
        # n'altère jamais les données ou l'arbre de travail réel.
        with tempfile.TemporaryDirectory(prefix="jibi_verification_") as dossier:
            copie = Path(dossier) / "JIBI"
            shutil.copytree(racine, copie, ignore=_ignorer)
            script_copie = copie / "tests" / "verification.py"
            environnement = dict(os.environ)
            environnement["PYTHONUTF8"] = "1"
            fait = subprocess.run(
                [sys.executable, "-X", "utf8", str(script_copie)], capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=180,
                cwd=str(copie), env=environnement)
        sortie = fait.stdout or ""
        erreurs = fait.stderr or ""
        lignes = [li for li in sortie.splitlines() if li.strip()]
        bilan = lignes[-1] if lignes else "?"
        ok = (fait.returncode == 0 and "❌" not in sortie
              and bilan.strip().endswith("OK") and not erreurs.strip())
        if not ok and erreurs.strip():
            bilan += f" (stderr: {erreurs.strip()[:120]})"
        if not ok:
            echecs = [li for li in lignes if "❌" in li][:3]
            if echecs:
                bilan += " | " + " ; ".join(echecs)
        return ok, bilan.strip()
    except Exception as e:  # noqa: BLE001
        return False, f"vérification impossible ({str(e)[:80]})"


@outil("lire_code_noyau",
       "Lit une partie d'un fichier du noyau pour préparer une modification. "
       "Lecture seule et limitée aux fichiers autorisés ; jamais .env/données/modèles.",
       parametres={
           "fichier": {"type": "str", "obligatoire": True,
                       "description": "chemin relatif, ex. jibi2/assistant.py"},
           "debut": {"type": "int", "obligatoire": False,
                     "description": "première ligne à lire (défaut 1)"},
           "lignes": {"type": "int", "obligatoire": False,
                      "description": "nombre de lignes (défaut 300, maximum 600)"},
       },
       categorie="amelioration", risque="moyen",
       exemple='{"outil": "lire_code_noyau", "parametres": {"fichier": "jibi2/assistant.py"}}')
def lire_code_noyau(fichier: str, debut: int = 1, lignes: int = 300) -> str:
    chemin, refus = _chemin_sur(fichier)
    if chemin is None:
        return {"ok": False, "texte": f"Lecture refusée : {refus}"}
    if not chemin.is_file():
        return {"ok": False, "texte": f"Fichier du noyau introuvable : {fichier}"}
    toutes = chemin.read_text(encoding="utf-8", errors="replace").splitlines()
    premier = max(1, int(debut))
    nombre = max(1, min(int(lignes), 600))
    tranche = toutes[premier - 1:premier - 1 + nombre]
    if not tranche:
        return {"ok": False, "texte": f"{fichier} ne contient pas de ligne {premier}."}
    texte = "\n".join(tranche)
    if len(texte) > 30_000:
        texte = texte[:30_000] + "\n… (tronqué)"
    fin = premier + len(tranche) - 1
    return f"{fichier} — lignes {premier} à {fin} :\n{texte}"


@outil("modifier_noyau",
       "Modifie le CODE DU NOYAU de JIBI (jibi2/, outils, interface, audio, "
       "scripts, run.py, docteur.py, tests). Le fichier est sauvegardé, la "
       "syntaxe et les tests sont relancés, retour arrière automatique si ça casse. "
       "Fournis soit le contenu complet, soit un extrait `avant` unique à remplacer "
       "par `apres`. En autonomie accordée, les tests ne peuvent pas être désactivés.",
       parametres={
           "fichier": {"type": "str", "obligatoire": True,
                       "description": "chemin relatif, ex. outils/calcul.py ou jibi2/assistant.py"},
           "contenu": {"type": "str", "obligatoire": False,
                       "description": "CONTENU COMPLET du nouveau fichier (nouveau fichier)"},
           "avant": {"type": "str", "obligatoire": False,
                     "description": "extrait existant à remplacer, présent exactement une fois"},
           "apres": {"type": "str", "obligatoire": False,
                     "description": "nouveau texte qui remplace exactement `avant`"},
           "raison": {"type": "str", "description": "pourquoi cette modification"},
           "verifier": {"type": "bool", "description": "tests après (défaut true; toujours true en autonomie)"},
       },
       categorie="amelioration", risque="eleve",
       exemple="corriger l.orbe → fichier=interface/bureau.py, avant=extrait exact, apres=nouveau texte")
def modifier_noyau(fichier: str, contenu: str = "", raison: str = "",
                   avant: str = "", apres: str = "",
                   verifier: bool = True) -> str:
    chemin, refus = _chemin_sur(fichier)
    if chemin is None:
        return {"ok": False, "texte": f"Modification refusée : {refus}"}
    from jibi2 import config
    if (avant or "").strip() and not (apres or "").strip():
        return {"ok": False, "texte": "Modification refusée : `apres` est obligatoire quand `avant` est fourni."}
    if (apres or "").strip() and not (avant or "").strip():
        return {"ok": False, "texte": "Modification refusée : `avant` est obligatoire quand `apres` est fourni."}
    if (contenu or "").strip() and ((avant or "").strip() or (apres or "").strip()):
        return {"ok": False,
                "texte": "Utilise soit `contenu`, soit le couple `avant`/`apres`, pas les deux."}
    if (avant or "").strip():
        if not chemin.is_file():
            return {"ok": False, "texte": "Impossible de remplacer un extrait : le fichier n'existe pas."}
        actuel = chemin.read_text(encoding="utf-8", errors="replace")
        occurrences = actuel.count(avant)
        if occurrences != 1:
            return {"ok": False,
                    "texte": (f"Modification refusée : l'extrait `avant` apparaît {occurrences} fois ; "
                              "il doit être unique et identique au fichier.")}
        contenu = actuel.replace(avant, apres, 1)
    if not (contenu or "").strip():
        return {"ok": False,
                "texte": "Contenu vide refusé. Fournis `contenu` ou une paire `avant`/`apres`."}
    if len(contenu) > MAX_TAILLE:
        return {"ok": False,
                "texte": f"Contenu trop gros ({len(contenu)} caractères, max {MAX_TAILLE})."}
    autonomie = config.valeur_bool("JIBI_MODIFICATION_AUTO")
    if autonomie:
        verifier = True
        if not (raison or "").strip():
            return {"ok": False,
                    "texte": "Autonomie : indique une raison pour pouvoir tracer la modification."}

    if chemin.suffix == ".py":
        try:
            compile(contenu, str(chemin), "exec")
        except SyntaxError as e:
            return {"ok": False,
                    "texte": (f"❌ Rien n'a été modifié : erreur de SYNTAXE dans le nouveau "
                              f"contenu (ligne {e.lineno} : {e.msg}).")}

    existed = chemin.exists()
    sauvegarde = _sauvegarder(chemin) if existed else None
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + f".tmp.{time.time_ns()}")
    try:
        temporaire.write_text(contenu, encoding="utf-8")
        temporaire.replace(chemin)
    except Exception as e:
        temporaire.unlink(missing_ok=True)
        return {"ok": False, "texte": f"Modification refusée : écriture impossible ({str(e)[:120]})."}

    if verifier:
        ok, bilan = _verifier_suite()
        if not ok:
            _annuler(chemin, sauvegarde)
            audit.journaliser("noyau_rollback", str(chemin.relative_to(_racine())),
                              details=f"tests échoués : {bilan}", resultat="annule")
            return {"ok": False,
                    "texte": (f"❌ Les tests ont échoué ({bilan}) — j'ai RESTAURÉ "
                              "l'ancienne version toute seule. La modification est annulée.")}
        suite = f" Tests : {bilan}."
    else:
        suite = " (tests non relancés cette fois)."

    from jibi2 import evolution
    audit.journaliser("noyau_modifie", str(chemin.relative_to(_racine())),
                      details=raison, resultat="tests_ok",
                      empreinte=hashlib.sha256(contenu.encode("utf-8")).hexdigest())
    evolution.noter_changelog(
        f"noyau {'créé' if not existed else 'modifié'} : {chemin.relative_to(_racine())}"
        f"{' — ' + raison if raison else ''}")
    if chemin.suffix == ".py" and not chemin.name.startswith("_"):
        suite += " Prendra effet au PROCHAIN démarrage de JIBI."
    return (f"✅ {'créé' if not existed else 'remplacé'} : "
            f"{chemin.relative_to(_racine())}.{suite}"
            + (" Ancienne version dans donnees/historique_noyau." if sauvegarde else ""))


@outil("restaurer_noyau",
       "Restaure la sauvegarde précédente d'un fichier du noyau, puis vérifie la "
       "syntaxe et toute la suite de tests. Un retour arrière automatic annule la "
       "restauration si elle casse JIBI.",
       parametres={"fichier": {"type": "str", "obligatoire": True,
                               "description": "chemin relatif du fichier à restaurer"}},
       categorie="amelioration", risque="eleve",
       exemple="annule ta modification de bureau.py → fichier=interface/bureau.py")
def restaurer_noyau(fichier: str) -> str:
    chemin, refus = _chemin_sur(fichier)
    if chemin is None:
        return {"ok": False, "texte": f"Restauration refusée : {refus}"}
    from jibi2 import config
    relatif = str(chemin.relative_to(_racine())).replace("\\", "/").replace("/", "__")
    dossier = config.DOSSIER_DONNEES / "historique_noyau"
    versions = sorted(dossier.glob(f"{relatif}.*")) if dossier.exists() else []
    if not versions:
        return {"ok": False,
                "texte": f"Aucune sauvegarde trouvée pour {relatif} — rien à restaurer."}
    version = versions[-1]
    contenu = version.read_text(encoding="utf-8", errors="replace")
    if chemin.suffix == ".py":
        try:
            compile(contenu, str(chemin), "exec")
        except SyntaxError as e:
            return {"ok": False,
                    "texte": (f"Restauration refusée : cette sauvegarde contient une erreur "
                              f"de syntaxe (ligne {e.lineno}).")}
    if not chemin.exists():
        return {"ok": False,
                "texte": "Restauration refusée : le fichier actuel n'existe plus."}
    sauvegarde = _sauvegarder(chemin)         # l'état actuel aussi, par prudence
    shutil.copy2(version, chemin)
    ok, bilan = _verifier_suite()
    if not ok:
        _annuler(chemin, sauvegarde)
        audit.journaliser("noyau_restauration_rollback", str(chemin.relative_to(_racine())),
                          details=f"tests échoués : {bilan}", resultat="annule")
        return {"ok": False,
                "texte": (f"❌ Cette sauvegarde casserait JIBI ({bilan}) — "
                          "la version actuelle a été restaurée automatiquement.")}
    from jibi2 import evolution
    audit.journaliser("noyau_restaure", str(chemin.relative_to(_racine())),
                      details=version.name, resultat="tests_ok",
                      empreinte=hashlib.sha256(contenu.encode("utf-8")).hexdigest())
    evolution.noter_changelog(f"noyau restauré : {chemin.relative_to(_racine())} "
                              f"(version {version.name.split('.')[-1]}, tests {bilan})")
    return (f"✅ {chemin.relative_to(_racine())} restauré depuis la sauvegarde "
            f"{version.name}. Tests : {bilan}. Prendra effet au prochain démarrage.")

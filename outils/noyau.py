"""Modifications du NOYAU de JIBI — toujours avec ta permission.

L'utilisateur a fixé la règle d'autonomie :
- outils, fonctionnalités, design → JIBI décide seul (risque faible) ;
- le NOYAU (jibi2/, outils intégrés, interface/, run.py, docteur.py,
  tests/) → l'outil est à RISQUE ÉLEVÉ : la boîte « Puis-je le faire ? »
  s'affiche automatiquement et l'utilisateur tranche à chaque fois.

Filet de sécurité quand une modification est acceptée :
1. l'ancien fichier est sauvegardé dans donnees/historique_noyau/ ;
2. la syntaxe est vérifiée immédiatement — erreur → retour arrière auto ;
3. la suite de tests complète est relancée (verifier=True) — échec →
   retour arrière auto, JIBI avoue et restaure ;
4. tout est noté dans le CHANGELOG, et restaurer_noyau permet de
   revenir en arrière à la main.

Jamais modifiables : .env (secrets), donnees/ (tes données),
modeles/ (les modèles), tout chemin hors du dossier de JIBI.
"""
from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from outils import outil

PERMIS = (
    "jibi2/*.py", "jibi2/*.md",
    "outils/*.py", "outils/*.md",
    "interface/*.py", "interface/*.html",
    "tests/*.py", "run.py", "docteur.py",
    "*.md", "VERSION", "requirements.txt",
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
                      "jibi2/, outils/, interface/, tests/, run.py, docteur.py, *.md, VERSION.")
    return _racine() / brut, ""


def pattern_to_regex(motif: str) -> str:
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
    copie = destination.with_name(f"{destination.name}.{int(time.time())}")
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
    script = _racine() / "tests" / "verification.py"
    if not script.exists():
        return True, "(suite absente, vérification ignorée)"
    try:
        fait = subprocess.run([sys.executable, str(script)], capture_output=True,
                              text=True, timeout=180)
        sortie = fait.stdout or ""
        lignes = [li for li in sortie.splitlines() if li.strip()]
        bilan = lignes[-1] if lignes else "?"
        ok = "❌" not in sortie and bilan.strip().endswith("OK")
        return ok, bilan.strip()
    except Exception as e:  # noqa: BLE001
        return False, f"vérification impossible ({str(e)[:80]})"


@outil("modifier_noyau",
       "Modifie le CODE DU NOYAU de JIBI (jibi2/, outils intégrés, interface, "
       "run.py, docteur.py, tests). Le fichier est sauvegardé, la syntaxe et "
       "les tests sont relancés, retour arrière automatique si ça casse. "
       "ACTION SENSIBLE : la boîte « Puis-je le faire ? » s'affichera — "
       "l'utilisateur décide. Nouveau fichier = nouvelle fonctionnalité.",
       parametres={
           "fichier": {"type": "str", "obligatoire": True,
                       "description": "chemin relatif, ex. outils/calcul.py ou jibi2/assistant.py"},
           "contenu": {"type": "str", "obligatoire": True,
                       "description": "le CONTENU COMPLET nouveau du fichier"},
           "raison": {"type": "str", "description": "pourquoi cette modification (montrée à l'utilisateur)"},
           "verifier": {"type": "bool", "description": "relancer les tests après (défaut true)"},
       },
       categorie="amelioration", risque="eleve",
       exemple="ajouter une devise à l'orbe → fichier=interface/bureau.py, contenu=…")
def modifier_noyau(fichier: str, contenu: str, raison: str = "",
                   verifier: bool = True) -> str:
    chemin, refus = _chemin_sur(fichier)
    if chemin is None:
        return {"ok": False, "texte": f"Modification refusée : {refus}"}
    if not (contenu or "").strip():
        return {"ok": False,
                "texte": "Contenu vide refusé (pour retirer un fichier, parle à ton utilisateur)."}
    if len(contenu) > MAX_TAILLE:
        return {"ok": False,
                "texte": f"Contenu trop gros ({len(contenu)} caractères, max {MAX_TAILLE})."}

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
    chemin.write_text(contenu, encoding="utf-8")

    if verifier:
        ok, bilan = _verifier_suite()
        if not ok:
            _annuler(chemin, sauvegarde)
            return {"ok": False,
                    "texte": (f"❌ Les tests ont échoué ({bilan}) — j'ai RESTAURÉ "
                              "l'ancienne version toute seule. La modification est annulée.")}
        suite = f" Tests : {bilan}."
    else:
        suite = " (tests non relancés cette fois)."

    from jibi2 import evolution
    evolution.noter_changelog(
        f"noyau {'créé' if not existed else 'modifié'} : {chemin.relative_to(_racine())}"
        f"{' — ' + raison if raison else ''}")
    if chemin.suffix == ".py" and not chemin.name.startswith("_"):
        suite += " Prendra effet au PROCHAIN démarrage de JIBI."
    return (f"✅ {'créé' if not existed else 'remplacé'} : "
            f"{chemin.relative_to(_racine())}.{suite}"
            + (" Ancienne version dans donnees/historique_noyau." if sauvegarde else ""))


@outil("restaurer_noyau",
       "Restaure une ancienne version d'un fichier du noyau (dans le sens "
       "inverse d'une modification). Action sensible : permission demandée.",
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
    _sauvegarder(chemin)                     # l'état actuel aussi, par prudence
    shutil.copy2(versions[-1], chemin)
    from jibi2 import evolution
    evolution.noter_changelog(f"noyau restauré : {chemin.relative_to(_racine())} "
                              f"(version {versions[-1].name.split('.')[-1]})")
    return (f"✅ {chemin.relative_to(_racine())} restauré depuis la sauvegarde "
            f"{versions[-1].name}. Prendra effet au prochain démarrage.")

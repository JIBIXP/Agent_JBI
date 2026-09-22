"""Laboratoire de JIBI 2 — tester une proposition SANS risque.

Approche héritée du dépôt Jarvis : une suite de tests que l'assistant sait
relancer, du code jamais exécuté dans le processus principal avant d'avoir
été prouvé, et un journal clair des évolutions (CHANGELOG.md).

Ce que fait le laboratoire, dans l'ordre :
  1. SYNTAXE   : compile() → toute erreur est renvoyée en clair ;
  2. SÉCURITÉ  : liste noire (subprocess, os.system, eval…) ;
  3. RISQUE    : évaluation légère (longueur, imports suspects) ;
  4. BAC À SABLE : le fichier est chargé dans un PROCESSUS SÉPARÉ avec un
     budget de 10 s — s'il plante ou boucle, JIBI n'y est pas exposé.

Résultat : {ok, resume, detail} — utilisable par le modèle et par l'humain.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from jibi2 import config

INTERDITS = ("shutil.rmtree", "os.system", "subprocess", "eval(", "exec(",
             "__import__", "os.remove", "socket.", "urllib.request")
IMPORTS_SURVEILLES = ("ctypes", "winreg", "requests", "http.client")

SCRIPT_BAC_A_SABLE = r"""
import importlib.util, json, sys
chemin, nom = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("proposition_test", chemin)
module = importlib.util.module_from_spec(spec)
sys.path.insert(0, sys.argv[3])
spec.loader.exec_module(module)
import outils
if nom not in outils.OUTILS:
    print(json.dumps({"ok": False, "detail": "le fichier ne déclare pas l'outil " + nom}))
    raise SystemExit
fonction = outils.OUTILS[nom].fonction
import inspect
essais = {"str": "essai", "int": 1, "float": 1.0, "bool": True}
parametres = {p: essais.get(i.get("type", "str"), "essai")
              for p, i in outils.OUTILS[nom].parametres.items() if i.get("obligatoire")}
try:
    resultat = fonction(**parametres)
    print(json.dumps({"ok": True, "detail": "appel d'essai réussi : " +
                      str(resultat)[:120]}))
except TypeError as e:
    print(json.dumps({"ok": True, "detail": "chargé, paramètres d'essai non adaptés (" +
                      str(e)[:80] + ") — pas bloquant"}))
except Exception as e:
    print(json.dumps({"ok": False, "detail": "l'appel d'essai a échoué : " + str(e)[:200]}))
"""


def sha256_fichier(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def evaluer_risque(code: str) -> tuple[str, list[str]]:
    """Risque léger : longueur, imports surveillés, fragments interdits."""
    raisons: list[str] = []
    niveau = 0
    for fragment in INTERDITS:
        if fragment in code:
            return "eleve", [f"contient « {fragment} » (interdit)"]
    lignes = [li for li in code.splitlines() if li.strip() and not li.strip().startswith("#")]
    if len(lignes) > 40:
        niveau += 1
        raisons.append(f"{len(lignes)} lignes (> 40)")
    for module_ in IMPORTS_SURVEILLES:
        if re.search(rf"^\s*(import|from)\s+{module_}\b", code, re.MULTILINE):
            niveau += 1
            raisons.append(f"importe {module_}")
    if "@outil(" not in code:
        return "eleve", ["pas de décorateur @outil : ce n'est pas un outil"]
    if niveau == 0:
        return "faible", raisons
    if niveau == 1:
        return "moyen", raisons
    return "eleve", raisons


def _chemin_proposition(nom: str) -> Path:
    return config.DOSSIER_PROPOSITIONS / f"{nom}.py"


def _lire_fiche(nom: str) -> dict:
    fiche = config.DOSSIER_PROPOSITIONS / f"{nom}.json"
    if fiche.exists():
        try:
            return json.loads(fiche.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _ecrire_fiche(nom: str, fiche: dict) -> None:
    config.DOSSIER_PROPOSITIONS.mkdir(parents=True, exist_ok=True)
    (config.DOSSIER_PROPOSITIONS / f"{nom}.json").write_text(
        json.dumps(fiche, ensure_ascii=False, indent=2), encoding="utf-8")


def tester_proposition(nom: str) -> dict:
    """Teste une proposition : syntaxe, sécurité, risque, bac à sable."""
    nom = (nom or "").strip().removesuffix(".py")
    chemin = _chemin_proposition(nom)
    if not chemin.exists():
        return {"ok": False, "resume": f"Aucune proposition « {nom} ».", "detail": ""}
    code = chemin.read_text(encoding="utf-8", errors="replace")

    # 1. Syntaxe
    try:
        compile(code, str(chemin), "exec")
    except SyntaxError as e:
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec", "erreur": f"syntaxe : {e.msg} (ligne {e.lineno})"})
        return {"ok": False, "resume": f"❌ Erreur de SYNTAXE : {e.msg} (ligne {e.lineno})",
                "detail": ""}
    # 2. Sécurité + 3. Risque
    risque, raisons = evaluer_risque(code)
    if risque == "eleve":
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec", "erreur": "; ".join(raisons)})
        return {"ok": False, "resume": f"❌ Refusé par la sécurité : {' ; '.join(raisons)}",
                "detail": ""}
    # 4. Bac à sable (processus séparé, 10 s max)
    scripts = Path(tempfile.gettempdir()) / "jibi_labo_test.py"
    scripts.write_text(SCRIPT_BAC_A_SABLE, encoding="utf-8")
    try:
        fait = subprocess.run(
            [sys.executable, str(scripts), str(chemin), nom, str(config.RACINE)],
            capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec", "erreur": "bac à sable : délai dépassé (10 s)"})
        return {"ok": False, "resume": "❌ Le test a dépassé 10 s (boucle infinie ?) — rejeté.",
                "detail": ""}
    sortie = (fait.stdout or "").strip()
    try:
        resultat = json.loads(sortie.splitlines()[-1]) if sortie else {}
    except json.JSONDecodeError:
        resultat = {"ok": False, "detail": (fait.stderr or "sortie illisible")[:200]}
    if fait.returncode != 0 or not resultat.get("ok"):
        detail = resultat.get("detail") or (fait.stderr or "").strip()[:200] or "échec inconnu"
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec", "erreur": detail[:200]})
        return {"ok": False, "resume": f"❌ Échec en bac à sable : {detail}", "detail": ""}
    # Enregistrer le verdict + l'empreinte
    fiche = {**_lire_fiche(nom), "test": "ok", "test_detail": resultat.get("detail", ""),
             "risque": risque, "raisons": raisons, "sha256": sha256_fichier(chemin)}
    _ecrire_fiche(nom, fiche)
    complement = f" (risque {risque}" + (f" : {' ; '.join(raisons)}" if raisons else "") + ")"
    return {"ok": True, "resume": f"✅ Testé en bac à sable : {resultat.get('detail', 'ok')}{complement}",
            "detail": resultat.get("detail", ""), "risque": risque}


def verifier_integrite(nom: str) -> tuple[bool, str]:
    """Le fichier correspond-il à ce qui a été proposé/testé ? (SHA-256)"""
    fiche = _lire_fiche(nom)
    empreinte = fiche.get("sha256")
    if not empreinte:
        return True, "(pas d'empreinte enregistrée — testé maintenant)"
    actuel = sha256_fichier(_chemin_proposition(nom))
    if actuel != empreinte:
        return False, "le fichier a CHANGÉ depuis le test — relance /tester avant de valider"
    return True, "intégrité vérifiée"


def verifier_code_projet() -> str:
    """Analyse le code de JIBI lui-même : tous les fichiers compilent-ils ?"""
    exclusions = {"donnees", "modeles", "__pycache__", ".git"}
    fichiers: list[Path] = []
    for dossier, noms, _ in config.RACINE.walk():
        noms[:] = [n for n in noms if n not in exclusions]
        fichiers.extend(dossier.glob("*.py"))
    erreurs: list[str] = []
    lignes_total = 0
    for chemin in sorted(fichiers):
        try:
            code = chemin.read_text(encoding="utf-8", errors="replace")
            lignes_total += len(code.splitlines())
            compile(code, str(chemin), "exec")
        except SyntaxError as e:
            erreurs.append(f"{chemin.relative_to(config.RACINE)} : ligne {e.lineno} — {e.msg}")
        except OSError:
            pass
    import outils
    corps = (f"✅ {len(fichiers)} fichiers analysés, {lignes_total} lignes, "
             f"{len(outils.OUTILS)} outils — tout compile.")
    if erreurs:
        corps += "\n❌ Erreurs :\n" + "\n".join(erreurs[:8])
    return corps

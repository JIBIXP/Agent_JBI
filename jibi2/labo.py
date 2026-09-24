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

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from jibi2 import config

INTERDITS = ("shutil.rmtree", "os.system", "subprocess", "eval(", "exec(",
             "__import__", "os.remove", "socket.", "urllib.request")
IMPORTS_SURVEILLES = ("ctypes", "winreg", "requests", "http.client")

# Le code produit par un modèle et influencé par une page web n'est jamais
# chargé dans le processus principal avant une validation stricte. Cette
# politique est volontairement plus étroite que l'ancien evaluer_risque().
IMPORTS_AUTONOMES = frozenset({
    "math", "statistics", "decimal", "fractions", "datetime", "time", "re",
    "json", "unicodedata", "textwrap", "string", "random", "hashlib",
})
APPELS_INTERDITS = frozenset({
    "eval", "exec", "compile", "open", "input", "__import__", "globals",
    "locals", "vars", "getattr", "setattr", "delattr", "breakpoint", "exit",
    "quit", "memoryview",
})
_NOMS_AUTONOMES = re.compile(r"^[a-z][a-z0-9_]{2,40}$")


def analyser_code_autonome(code: str, nom_attendu: str = "") -> tuple[bool, list[str]]:
    """Valide un petit outil pur sans imports système, réseau ou écritures.

    Cette fonction est une politique statique, pas un bac à sable. Le test
    d'exécution reste obligatoire, mais un code qui échappe à cette lecture
    doit être refusé plutôt que chargé dans JIBI.
    """
    raisons: list[str] = []
    if len(code or "") > 16_000 or len((code or "").splitlines()) > 120:
        return False, ["code trop long pour l'activation autonome (>120 lignes)"]
    if nom_attendu and not _NOMS_AUTONOMES.match(nom_attendu):
        return False, ["nom d'outil invalide"]
    try:
        arbre = ast.parse(code or "")
    except SyntaxError as e:
        return False, [f"syntaxe invalide (ligne {e.lineno})"]
    if sum(1 for n in ast.walk(arbre) if isinstance(n, ast.Constant)) > 500:
        return False, ["trop de constantes"]

    imports_outils = 0
    imports_autorises = 0
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                racine = alias.name.split(".", 1)[0]
                if racine not in IMPORTS_AUTONOMES:
                    raisons.append(f"import interdit : {alias.name}")
                else:
                    imports_autorises += 1
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.module == "outils" and [a.name for a in noeud.names] == ["outil"] \
                    and noeud.level == 0:
                imports_outils += 1
            else:
                raisons.append(f"import interdit : {noeud.module or noeud.names}")
        elif isinstance(noeud, ast.Attribute) and noeud.attr.startswith("_"):
            raisons.append(f"attribut privé interdit : {noeud.attr}")
        elif isinstance(noeud, ast.Name):
            if noeud.id.startswith("__") or noeud.id in APPELS_INTERDITS:
                raisons.append(f"capacité interdite : {noeud.id}")
        elif isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) \
                and noeud.func.id in APPELS_INTERDITS:
            raisons.append(f"appel interdit : {noeud.func.id}")
        elif isinstance(noeud, (ast.While, ast.AsyncFunctionDef, ast.AsyncFor,
                                 ast.AsyncWith, ast.Yield, ast.YieldFrom, ast.With)):
            raisons.append(f"construction non autorisée : {type(noeud).__name__}")
        elif isinstance(noeud, (ast.Global, ast.Nonlocal)):
            raisons.append("portée globale interdite")
    if imports_outils != 1:
        raisons.append("il faut exactement un import « from outils import outil »")
    if imports_autorises > 12:
        raisons.append("trop d'imports")

    fonctions = [n for n in arbre.body if isinstance(n, ast.FunctionDef)]
    if len(fonctions) != 1:
        raisons.append("il faut exactement une fonction d'outil")
    else:
        fonction = fonctions[0]
        if nom_attendu and fonction.name != nom_attendu:
            raisons.append("le nom de la fonction ne correspond pas au nom déclaré")
        decorateurs = [d for d in fonction.decorator_list
                       if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                       and d.func.id == "outil"]
        if len(decorateurs) != 1 or len(fonction.decorator_list) != 1:
            raisons.append("il faut exactement un décorateur @outil")
    # Un seul appel @outil avec un nom littéral equal à l'artefact.
    appels_outil = [n for n in ast.walk(arbre) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == "outil"]
    if len(appels_outil) != 1 or not appels_outil[0].args \
            or not isinstance(appels_outil[0].args[0], ast.Constant) \
            or appels_outil[0].args[0].value != (nom_attendu or appels_outil[0].args[0].value):
        raisons.append("le décorateur doit déclarer exactement le nom de l'outil")
    if len(list(ast.walk(arbre))) > 800:
        raisons.append("arbre de code trop complexe")
    return not raisons, list(dict.fromkeys(raisons))

SCRIPT_BAC_A_SABLE = r"""
import importlib.util
import io
import json
import sys
import types

# Le module candidat ne voit qu'un décorateur minimal : aucun OUTILS, aucun
# service, aucun .env et aucun module JIBI ne sont chargés dans le worker.
registre = {}
def outil(nom, description, parametres=None, **kwargs):
    def decorateur(fonction):
        registre[nom] = {"fonction": fonction, "parametres": parametres or {}}
        return fonction
    return decorateur
module_outils = types.ModuleType("outils")
module_outils.outil = outil
sys.modules["outils"] = module_outils

# Le module candidat ne doit pas pouvoir remplacer le protocole du worker.
sortie = sys.stdout
sys.stdout = io.StringIO()
try:
    chemin, nom = sys.argv[1], sys.argv[2]
    spec = importlib.util.spec_from_file_location("proposition_test", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if set(registre) != {nom}:
        raise RuntimeError("le fichier doit déclarer exactement l'outil " + nom)
    entree = registre[nom]
    fonction = entree["fonction"]
    essais = {"str": "essai", "int": 1, "float": 1.0, "bool": True}
    parametres = {p: essais.get(i.get("type", "str"), "essai")
                  for p, i in entree["parametres"].items() if i.get("obligatoire")}
    resultat = fonction(**parametres)
    detail = "appel d'essai réussi : " + str(resultat)[:120]
    reponse = {"ok": True, "detail": detail}
except Exception as e:
    reponse = {"ok": False, "detail": "l'appel d'essai a échoué : " + str(e)[:200]}
finally:
    sys.stdout = sortie
    # Marqueur interne : une fausse impression du code candidat ne peut pas
    # être prise pour le rapport du worker.
    print("JIBI_TEST_RESULT:" + json.dumps(reponse, ensure_ascii=False))
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
    nom = (nom or "").strip().removesuffix(".py")
    if not re.match(r"^[a-z][a-z0-9_]{2,40}$", nom):
        raise ValueError("nom de proposition invalide")
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
    try:
        chemin = _chemin_proposition(nom)
    except ValueError:
        return {"ok": False, "resume": "Nom de proposition invalide.", "detail": ""}
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
    auto_ok, auto_raisons = analyser_code_autonome(code, nom)
    if not auto_ok:
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec",
                            "erreur": "autonomie sûre : " + "; ".join(auto_raisons)})
        return {"ok": False,
                "resume": "❌ Refusé par la politique autonome : " + " ; ".join(auto_raisons),
                "detail": ""}
    risque, raisons = evaluer_risque(code)
    if risque == "eleve":
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec", "erreur": "; ".join(raisons)})
        return {"ok": False, "resume": f"❌ Refusé par la sécurité : {' ; '.join(raisons)}",
                "detail": ""}
    # 4. Worker séparé, environnement sans secrets et fichier temporaire unique.
    sha_avant = sha256_fichier(chemin)
    environnement = {cle: valeur for cle, valeur in os.environ.items()
                      if cle.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
                                         "COMSPEC", "PATHEXT"}}
    environnement.update({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        with tempfile.TemporaryDirectory(prefix="jibi_labo_") as dossier_temporaire:
            script = Path(dossier_temporaire) / "worker.py"
            script.write_text(SCRIPT_BAC_A_SABLE, encoding="utf-8")
            fait = subprocess.run(
                [sys.executable, "-I", str(script), str(chemin), nom],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=10, cwd=dossier_temporaire, env=environnement)
    except subprocess.TimeoutExpired:
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec", "erreur": "bac à sable : délai dépassé (10 s)"})
        return {"ok": False, "resume": "❌ Le test a dépassé 10 s (boucle infinie ?) — rejeté.",
                "detail": ""}
    sortie = fait.stdout or ""
    marqueurs = [ln.split(":", 1)[1] for ln in sortie.splitlines()
                  if ln.startswith("JIBI_TEST_RESULT:")]
    try:
        resultat = json.loads(marqueurs[-1]) if marqueurs else {}
    except json.JSONDecodeError:
        resultat = {"ok": False, "detail": (fait.stderr or "sortie illisible")[:200]}
    if fait.returncode != 0 or not resultat.get("ok"):
        detail = resultat.get("detail") or (fait.stderr or "").strip()[:200] or "échec inconnu"
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec", "erreur": detail[:200]})
        return {"ok": False, "resume": f"❌ Échec en bac à sable : {detail}", "detail": ""}
    if sha256_fichier(chemin) != sha_avant:
        _ecrire_fiche(nom, {**_lire_fiche(nom), "test": "echec",
                            "erreur": "le fichier a changé pendant le test"})
        return {"ok": False, "resume": "❌ Le fichier a changé pendant le test — refusé.", "detail": ""}
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
    if erreurs:
        return (f"❌ {len(fichiers)} fichiers analysés, {lignes_total} lignes, "
                f"{len(outils.OUTILS)} outils — des erreurs de syntaxe ont été trouvées :\n"
                + "\n".join(erreurs[:8]))
    return (f"✅ {len(fichiers)} fichiers analysés, {lignes_total} lignes, "
            f"{len(outils.OUTILS)} outils — tout compile.")

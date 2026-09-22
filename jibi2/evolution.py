"""Auto-amélioration de JIBI 2 — JIBI propose, TU disposes.

Le cycle complet (tout est local, tout est visible) :

  1. DÉTECTER : chaque échec d'outil est noté dans donnees/journal/erreurs.jsonl
  2. ANALYSER : JIBI peut relire le journal (outil lister_erreurs) et son
     propre code (outil lire_code_outil)
  3. PROPOSER : JIBI écrit un outil nouveau ou corrigé dans
     donnees/propositions/ — le code n'est JAMAIS exécuté avant validation
  4. DÉCIDER  : dans la console : /propositions · /valider <nom> (active) ·
     /retirer <nom> (désactive et restaure l'ancien) · /bilan (résumé)

Limites volontaires : JIBI ne modifie jamais son noyau (jibi2/,
interface/, run.py) ni le .env — il ne peut proposer que des OUTILS, et
jamais activés sans ton accord. Pas de modification automatique, pas
d'autonomie sur le code du cerveau.
"""
from __future__ import annotations

import contextlib
import inspect
import json
import re
import shutil
import subprocess
import sys
import time

from . import config
from .labo import (
    evaluer_risque,
    sha256_fichier,
    tester_proposition,
    verifier_code_projet,
    verifier_integrite,
)

PROPOSITIONS = config.DOSSIER_PROPOSITIONS
CHANGELOG = config.RACINE / "CHANGELOG.md"
JOURNAL = config.DOSSIER_JOURNAL / "erreurs.jsonl"
HISTORIQUE = config.DOSSIER_DONNEES / "historique_outils"
_MOTIF_NOM = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

# Fragments interdits dans une proposition (sécurité de base avant relecture humaine).
INTERDITS = ("shutil.rmtree", "os.system", "subprocess", "eval(", "exec(",
             "__import__", "os.remove", "socket.", "urllib.request")

# Outils intégrés provisoirement masqués par une proposition (pour /retirer).
_SAUVEGARDES: dict = {}


# ── 1. DÉTECTER ──────────────────────────────────────────────────────────────
def noter_erreur(outil: str, erreur: str) -> None:
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"quand": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "outil": outil, "erreur": erreur[:400]}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def lister_erreurs(mot: str = "", nombre: int = 15) -> str:
    if not JOURNAL.exists():
        return "Aucune erreur enregistrée : tout roule."
    entrees = []
    for ligne in JOURNAL.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entrees.append(json.loads(ligne))
        except json.JSONDecodeError:
            continue
    if mot:
        bas = mot.lower()
        entrees = [e for e in entrees
                   if bas in e.get("outil", "").lower() or bas in e.get("erreur", "").lower()]
    if not entrees:
        return f"Aucune erreur ne contient « {mot} »."
    dernieres = entrees[-min(max(1, int(nombre)), 40):][::-1]
    corps = "\n".join(f"{e.get('quand', '?')} — {e.get('outil', '?')} : "
                      f"{e.get('erreur', '')[:120]}" for e in dernieres)
    return f"{len(entrees)} erreur(s) enregistrée(s). Les dernières :\n{corps}"


# ── 2. ANALYSER ──────────────────────────────────────────────────────────────
def lire_code_outil(nom: str) -> str:
    import outils
    o = outils.OUTILS.get(nom)
    if o is None:
        return f"Outil « {nom} » inconnu. Utilise un outil de la liste."
    try:
        source = inspect.getsource(o.fonction)
        fichier = inspect.getsourcefile(o.fonction)
    except (OSError, TypeError):
        return f"Impossible de lire la source de {nom}."
    if len(source) > 2500:
        source = source[:2500] + "… (tronqué)"
    return f"Source de {nom} ({fichier}) :\n{source}"


# ── 3. PROPOSER ──────────────────────────────────────────────────────────────
def proposer_outil(nom: str, code: str) -> str:
    nom = (nom or "").strip()
    if not _MOTIF_NOM.match(nom):
        return ("Nom invalide : lettres minuscules, chiffres et _ seulement "
                "(ex. convertisseur_euro).")
    for fragment in INTERDITS:
        if fragment in code:
            return (f"Proposition refusée : elle contient « {fragment} », "
                    "interdit pour un outil proposé.")
    if "@outil(" not in code or "from outils import" not in code:
        return ("La proposition doit définir un outil avec le décorateur @outil(...) "
                "et commencer par « from outils import outil ».")
    risque, raisons = evaluer_risque(code)
    if risque == "eleve":
        return f"Proposition refusée : {' ; '.join(raisons)}."
    PROPOSITIONS.mkdir(parents=True, exist_ok=True)
    chemin = PROPOSITIONS / f"{nom}.py"
    chemin.write_text(code, encoding="utf-8")
    (PROPOSITIONS / f"{nom}.json").write_text(json.dumps(
        {"sha256": sha256_fichier(chemin), "risque": risque, "raisons": raisons,
         "quand": time.strftime("%Y-%m-%d %H:%M"), "test": "pas_encore"}, ensure_ascii=False),
        encoding="utf-8")
    deja = "(correction d'un outil existant)" if (nom in _outils_actifs()) else "(nouvel outil)"
    return (f"Proposition enregistrée {deja}, risque {risque}"
            + (f" ({'; '.join(raisons)})" if raisons else "")
            + f". Teste-la : /tester {nom} — puis active : /valider {nom}")


def lister_propositions() -> str:
    if not PROPOSITIONS.exists():
        return "Aucune proposition."
    fichiers = sorted(p for p in PROPOSITIONS.glob("*.py") if not p.name.startswith("_"))
    if not fichiers:
        return "Aucune proposition en attente."
    lignes = []
    for p in fichiers:
        premiere = next((ln.strip() for ln in p.read_text(encoding="utf-8",
                          errors="replace").splitlines() if ln.strip() and not ln.startswith("#")), "")
        fiche = {}
        fiche_path = PROPOSITIONS / (p.stem + ".json")
        if fiche_path.exists():
            with contextlib.suppress(json.JSONDecodeError):
                fiche = json.loads(fiche_path.read_text(encoding="utf-8"))
        etat = {"ok": "✅ testé", "echec": "❌ test raté", "pas_encore": "⚪ non testé"}.get(
            fiche.get("test", ""), "⚪ non testé")
        lignes.append(f"- {p.stem} [{fiche.get('risque', '?')}·{etat}] : {premiere[:90]}"
                      + (f"\n    → {fiche['erreur']}" if fiche.get("erreur") else ""))
    return ("Propositions en attente de validation :\n" + "\n".join(lignes)
            + "\nTester : /tester <nom>   Activer : /valider <nom>")


# ── 4. DÉCIDER ───────────────────────────────────────────────────────────────
def valider(nom: str) -> str:
    nom = (nom or "").strip().removesuffix(".py")
    source = PROPOSITIONS / f"{nom}.py"
    if not source.exists():
        return f"Aucune proposition nommée « {nom} »."
    code = source.read_text(encoding="utf-8", errors="replace")
    for fragment in INTERDITS:
        if fragment in code:
            source.unlink()
            return f"Proposition « {nom} » rejetée et supprimée : elle contenait « {fragment} »."
    ok_integrite, message_integrite = verifier_integrite(nom)
    if not ok_integrite:
        return f"⚠️ {nom} : {message_integrite}"
    verdict = tester_proposition(nom)
    if not verdict["ok"]:
        return (f"{verdict['resume']} La proposition reste dans donnees/propositions/ "
                "pour correction — ou supprime-la.")
    import outils
    destination = outils.DOSSIER_PERSO / f"{nom}.py"
    HISTORIQUE.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.copy2(destination, HISTORIQUE / f"{nom}.{int(time.time())}.py")
        message = (f"Proposition validée : outils/perso/{nom}.py REMPLACÉ "
                   "(l'ancienne version est dans donnees/historique_outils).")
    elif nom in outils.OUTILS:
        _SAUVEGARDES[nom] = outils.OUTILS[nom]
        message = (f"Proposition validée → outils/perso/{nom}.py. Elle masque l'outil "
                   f"intégré « {nom} » : /retirer {nom} restaurera l'original.")
    else:
        message = f"Proposition validée → outils/perso/{nom}.py (activée)."
    shutil.move(str(source), str(destination))
    (PROPOSITIONS / f"{nom}.json").unlink(missing_ok=True)
    outils.charger_perso()
    noter_changelog(f"outil « {nom} » {'remplacé' if 'REMPLACÉ' in message else 'activé'} "
                    f"(risque {verdict.get('risque', '?')}, testé en bac à sable ✅)")
    return message + f" Test bac à sable : {verdict['resume']}"


def retirer(nom: str) -> str:
    """Désactive un outil perso ; restaure l'outil intégré s'il était masqué."""
    nom = (nom or "").strip().removesuffix(".py")
    import outils
    destination = outils.DOSSIER_PERSO / f"{nom}.py"
    if not destination.exists():
        return f"« {nom} » n'est pas un outil perso : rien à retirer."
    HISTORIQUE.mkdir(parents=True, exist_ok=True)
    shutil.move(str(destination), HISTORIQUE / f"{nom}.{int(time.time())}.py")
    if nom in _SAUVEGARDES:
        outils.OUTILS[nom] = _SAUVEGARDES.pop(nom)
        noter_changelog(f"outil « {nom} » retiré, version intégrée restaurée")
        return f"Outil « {nom} » retiré : la version intégrée est restaurée."
    outils.OUTILS.pop(nom, None)
    noter_changelog(f"outil perso « {nom} » retiré (fichier gardé dans historique)")
    return f"Outil « {nom} » retiré (fichier gardé dans donnees/historique_outils)."


def bilan() -> str:
    import outils
    perso = len(list(outils.DOSSIER_PERSO.glob("*.py"))) if outils.DOSSIER_PERSO.exists() else 0
    en_attente = (len([p for p in PROPOSITIONS.glob("*.py") if not p.name.startswith("_")])
                  if PROPOSITIONS.exists() else 0)
    erreurs = 0
    if JOURNAL.exists():
        with JOURNAL.open(encoding="utf-8", errors="replace") as f:
            erreurs = sum(1 for _ in f)
    return (f"{len(outils.OUTILS)} outils actifs dont {perso} perso · "
            f"{en_attente} proposition(s) en attente (/propositions) · "
            f"{erreurs} erreur(s) notée(s) (détail : outil lister_erreurs)")


def noter_changelog(annonce: str) -> None:
    """Journal des évolutions, format Keep a Changelog (inspiré du dépôt Jarvis)."""
    try:
        entree = f"- {time.strftime('%Y-%m-%d %H:%M')} — {annonce}\n"
        if CHANGELOG.exists():
            texte = CHANGELOG.read_text(encoding="utf-8")
            marqueur = "## Non publié\n"
            if marqueur in texte:
                texte = texte.replace(marqueur, marqueur + entree, 1)
            else:
                texte += f"\n## Non publié\n\n{entree}"
        else:
            texte = f"# Changelog de JIBI 2\n\n## Non publié\n\n{entree}"
        CHANGELOG.write_text(texte, encoding="utf-8")
    except Exception:
        pass


def lancer_verification() -> str:
    """Relance la suite de vérification de JIBI (inspiré du dossier tests/ de Jarvis)."""
    script = config.RACINE / "tests" / "verification.py"
    if not script.exists():
        return f"Suite de vérification introuvable : {script}"
    try:
        fait = subprocess.run([sys.executable, str(script)], capture_output=True,
                              text=True, timeout=180)
        lignes = [li for li in (fait.stdout or "").splitlines() if li.strip()]
        bilan_ligne = lignes[-1] if lignes else "?"
        echecs = [li for li in lignes if "❌" in li][:6]
        etat = "✅" if fait.returncode == 0 else "❌"
        resume = f"{etat} {bilan_ligne}"
        if echecs:
            resume += "\n" + "\n".join(echecs)
        return resume
    except subprocess.TimeoutExpired:
        return "❌ La suite de vérification a dépassé 180 s."
    except Exception as e:
        return f"Impossible de lancer la vérification : {e}"


def _outils_actifs() -> dict:
    import outils
    return outils.OUTILS


# ── enregistrement des outils « méta » (visibles du modèle) ─────────────────
def enregistrer_outil() -> None:
    from outils import outil

    @outil("proposer_nouvel_outil",
           "Propose un NOUVEL outil (ou une CORRECTION d'un outil existant, en gardant le même nom). "
           "Le code est stocké inactif dans donnees/propositions/ ; seul l'utilisateur peut l'activer.",
           {"nom": {"type": "str", "obligatoire": True,
                    "description": "nom court : minuscules et _ seulement (le même nom qu'un outil "
                                   "existant = proposition de correction)"},
            "code": {"type": "str", "obligatoire": True,
                     "description": "code Python complet : from outils import outil + fonction décorée @outil(...)"}},
           categorie="amelioration", risque="moyen",
           exemple='{"outil": "proposer_nouvel_outil", "parametres": {"nom": "convertisseur_euro", "code": "from outils import outil\\n\\n@outil(\'convertisseur_euro\', \'Convertit des euros en francs.\', {\'euros\': {\'type\': \'float\', \'obligatoire\': True}}, categorie=\'calcul\')\\ndef convertir(euros):\\n    return f\'{euros} EUR = {euros * 6.55957:.2f} FRF\'"}}')
    def proposer_nouvel_outil(nom: str, code: str) -> str:
        return proposer_outil(nom, code)

    @outil("lister_erreurs",
           "Liste les erreurs récentes des outils de JIBI (journal interne) pour les analyser.",
           {"mot": {"type": "str", "obligatoire": False,
                    "description": "filtre par mot (nom d'outil ou morceau de message)"},
            "nombre": {"type": "int", "obligatoire": False, "description": "lignes à montrer (défaut 15)"}},
           categorie="amelioration",
           exemple='{"outil": "lister_erreurs", "parametres": {}}')
    def lister_erreurs_outil(mot: str = "", nombre: int = 15) -> str:
        return lister_erreurs(mot, nombre)

    @outil("tester_proposition",
           "Teste en bac à sable (processus séparé, 10 s) une proposition en attente : "
           "syntaxe, sécurité, appel d'essai. À faire AVANT de demander la validation.",
           {"nom": {"type": "str", "obligatoire": True, "description": "nom de la proposition"}},
           categorie="amelioration")
    def tester_proposition_outil(nom: str) -> str:
        verdict = tester_proposition(nom)
        return verdict["resume"]

    @outil("lancer_verification",
           "Relance la suite de vérification complète de JIBI (tests internes) et renvoie le bilan.",
           {}, categorie="amelioration",
           exemple='{"outil": "lancer_verification", "parametres": {}}')
    def lancer_verification_outil() -> str:
        return lancer_verification()

    @outil("analyser_code_projet",
           "Analyse le code source de JIBI lui-même : compile chaque fichier et donne "
           "l'inventaire (fichiers, lignes, outils). Pour l'auto-contrôle.",
           {}, categorie="amelioration")
    def analyser_code_projet_outil() -> str:
        return verifier_code_projet()

    @outil("lire_code_outil",
           "Relit le code source d'un outil installé (pour préparer une correction avec proposer_nouvel_outil).",
           {"nom": {"type": "str", "obligatoire": True, "description": "nom exact de l'outil"}},
           categorie="amelioration")
    def lire_code_outil_outil(nom: str) -> str:
        return lire_code_outil(nom)

    @outil("activer_proposition",
           "Active (installe) une proposition d'outil — AUTORISATION ACCORDÉE "
           "par l'utilisateur : tu peux le faire toi-même une fois le test bac "
           "à sable passé. La sécurité est re-vérifiée à l'activation.",
           {"nom": {"type": "str", "obligatoire": True,
                    "description": "nom de la proposition à activer"}},
           categorie="amelioration", risque="moyen",
           exemple="activer ma proposition → nom=le_nom_de_la_proposition")
    def activer_proposition_outil(nom: str) -> str:
        return valider(nom)

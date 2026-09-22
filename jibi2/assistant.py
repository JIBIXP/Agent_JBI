"""Le cerveau de JIBI 2 : comprendre un message, agir avec les outils, répondre.

Protocole (simple et robuste, testé avec qwen3.5) :
  1. le système impose au modèle de répondre UNIQUEMENT en JSON :
       {"outil": "nom", "parametres": {...}}  → agir
       {"reponse": "texte"}                   → parler
  2. si le JSON est invalide → UNE relance corrective (comme Jarvis),
     sinon la réponse brute est prise telle quelle ;
  3. chaque résultat d'outil est renvoyé au modèle pour la phrase finale ;
  4. si Ollama est éteint → repli local par mots-clés (heure, calcul,
     note, recherche, ouvrir) pour les cas de base.
"""
from __future__ import annotations

import json
import re

from . import config, llm
from .memoire import Memoire
from .securite import Garde

SYSTEME = """Tu es {nom}, un assistant personnel en français installé sur le PC de l'utilisateur.
Tu réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, sans balises de code :
- pour utiliser un outil : {{"outil": "nom_outil", "parametres": {{...}}}}
- pour parler : {{"reponse": "ta phrase en français"}}
Sers-toi d'un outil dès que c'est utile. Après un résultat d'outil, réponds avec {{"reponse": "..."}} en t'appuyant sur ce résultat.
RÈGLE DE STYLE : réponds COURT — 1 à 2 phrases maximum, direct, sans préambule ("Bien sûr !", "Voilà") ni répétition de la question. Ça sera dit à voix haute.
Ne promets jamais une action sans appeler l'outil qui la fait. Tu ne peux pas inventer d'outils hors de la liste.

Ce que tu SAIS faire (parle-en au présent, tu as les outils) :
- créer de VRAIS documents : creer_pdf et creer_word (l'utilisateur n'a rien à faire d'autre) ;
- routines automatiques : creer_workflow avec un horaire "HH:MM" exécute la routine CHAQUE JOUR toute seule tant que tu tournes (c'est toi qui es partiellement automatique) ;
- t'améliorer SEUL (autonomie accordée par l'utilisateur) : proposer un outil nouveau ou une correction (proposer_nouvel_outil), le tester (tester_proposition), puis l'ACTIVER toi-même avec activer_proposition, sans demander ; personnalise tes couleurs avec personnaliser_design (orbe + panneau) ;
- t'instruire sur le WEB : cherche une technique ou du code (rechercher_web, lire_page_web) puis fabrique-toi un outil avec (proposer_nouvel_outil → tester_proposition → activer_proposition) — cite ta source à l'utilisateur ;
- pour toucher au NOYAU du programme (modifier_noyau ou restaurer_noyau : fichiers jibi2/, outils intégrés, interface/, run.py, docteur.py, tests/) : appelle l'outil et dis d'abord « puis-je le faire ? » — la boîte de permission s'affichera et l'utilisateur décidera ; en cas de refus, n'insiste jamais ;
- contrôler ton code (analyser_code_projet, lancer_verification), voir l'écran (voir_ecran), te souvenir (retenir, ajouter_note), Programmer des rappels, chercher sur le web, gérer des fichiers, ouvrir des applications."""

# ---------------------------------------------------------- voie rapide
# Certaines demandes n'ont pas besoin de réfléchir : heure, dé, pile ou
# face, calcul simple, coup de chifoumi, essai du nombre mystère. On y
# répond en < 0,1 s sans passer par le modèle (qui met 2 à 8 s sur CPU).
# Volontairement ÉTROIT : tout le reste suit le chemin normal.
_RE_HEURE = re.compile(
    r"\b(quelle?[s]? heure|il est quelle heure|donne[- ]moi l'heure|l'heure s'il te plait)\b")
_RE_JOUR = re.compile(r"\b(quel(le)? jour|quelle est la date)\b")
_RE_PASSE = re.compile(r"\b(hier|etait|etaient|avant|dernier\w*)\b")
_RE_DE = re.compile(r"\b(?:lances?|jettes?|tires?)\s+(?:un |une |le |la |les )?des?\b")
_RE_PILE = re.compile(r"\bpile ou face\b")
_RE_CHIFOU = re.compile(r"\b(pierre|feuille|ciseaux)\b")
_RE_CHIFOU_JEU = re.compile(r"\b(je (joue|choisis|dis)|chifoumi|pierre feuille ciseaux)\b")
_RE_CALCUL = re.compile(r"(?:calcule|combien font|combien fait)\s+(.+)")
_RE_GUESS = re.compile(r"\b(?:c'?est|cest|je dis|je propose|propose|essai)\s*:?\s*(\d{1,3})\b")


def _voie_rapide(texte: str, garde) -> dict | None:
    """Réponse instantanée pour les demandes évidentes. None = chemin normal."""
    from outils import _sans_accent
    t = _sans_accent(texte).strip()

    if (_RE_HEURE.search(t) or _RE_JOUR.search(t)) and not _RE_PASSE.search(t):
        return _reponse_outil("heure_actuelle", {}, garde)
    if _RE_DE.search(t):
        n = re.search(r"(?:a|@)\s*(\d{1,3})|(\d{1,3})\s*faces?", t)
        faces = int(n.group(1) or n.group(2)) if n else 6
        return _reponse_outil("lancer_un_de", {"faces": faces}, garde)
    if _RE_PILE.search(t):
        return _reponse_outil("pile_ou_face", {}, garde)
    if _RE_CHIFOU_JEU.search(t):
        choix = _RE_CHIFOU.search(t)
        if choix:
            return _reponse_outil("pierre_feuille_ciseaux", {"choix": choix.group(1)}, garde)
    if "mystere" in t and re.search(r"\b(commence|commencer|on joue|nouvelle partie)\b", t):
        return _reponse_outil("nombre_mystere", {"action": "commencer"}, garde)
    g = _RE_GUESS.search(t)
    if g is not None and _etat_mystere() is not None:
        return _reponse_outil("nombre_mystere", {"action": "deviner", "nombre": int(g.group(1))}, garde)
    m = _RE_CALCUL.search(t)
    if m is not None:
        expression = m.group(1).rstrip("?. !")
        if len(expression) <= 80 and re.fullmatch(r"[0-9+\-*/().,%\s]*", expression):
            return _reponse_outil("calculer", {"expression": expression}, garde)
    return None


def _etat_mystere() -> dict | None:
    """L'état du nombre mystère s'il y a une partie en cours."""
    from outils.jeux import _MYSTERE
    return _MYSTERE if "cible" in _MYSTERE else None


def _reponse_outil(nom: str, parametres: dict, garde) -> dict:
    from outils import executer
    r = executer(nom, parametres, garde)
    return {"reponse": r["texte"], "actions": [{"outil": nom, **r}], "ok": r["ok"]}


CORRECTIF = ("Ta réponse précédente n'était pas un JSON valide : « {extrait} ». "
             "Réponds UNIQUEMENT avec un JSON : {{\"outil\": \"nom\", \"parametres\": {{...}}}} "
             "ou {{\"reponse\": \"...\"}}.")


class Assistant:
    def __init__(self, memoire: Memoire, garde: Garde, sur_rappel=None) -> None:
        self.memoire = memoire
        self.garde = garde
        self.client = llm.ClientLLM()
        self.histoire: list[dict] = []
        self.max_histoire = max(4, _entier("JIBI_HISTOIRE", 12))
        self._noms_outils: list[str] | None = None   # jeu adaptatif (None = tous)
        from outils import regler_services
        regler_services(memoire=memoire, sur_rappel=sur_rappel)

    # ------------------------------------------------------------------ API
    def _garde_flux(self, on_chunk):
        """N'émet le flux que si la réponse n'est pas du JSON de protocole.

        Dès que le 1er caractère significatif est « { », on se tait : c'est
        un appel d'outil, pas du texte à montrer.
        """
        etat = {"decide": False, "muet": False}

        def emettre(morceau: str) -> None:
            if not etat["decide"]:
                etat["muet"] = morceau.lstrip()[:1] == "{"
                etat["decide"] = True
            if not etat["muet"]:
                on_chunk(morceau)

        return emettre

    def _appeler(self, on_chunk=None, messages=None) -> str:
        if messages is not None:
            if on_chunk is None:
                return self.client.discuter(messages)
            return self.client.discuter_stream(messages, on_chunk=self._garde_flux(on_chunk))
        if on_chunk is None:
            return self.client.discuter(self._messages())
        return self.client.discuter_stream(self._messages(),
                                           on_chunk=self._garde_flux(on_chunk))

    def repondre(self, texte: str, max_etapes: int = 3, on_chunk=None) -> dict:
        """Boucle complète : renvoie {"reponse", "actions", "ok"}.

        on_chunk(delta) est appelé au fil de l'eau avec les morceaux de la
        réponse FINALE seulement (les appels d'outils JSON restent muets).
        """
        self.memoire.ajouter_message("utilisateur", texte)
        self._ajouter("user", texte)

        # voie rapide : heure, dé, chifoumi… réponse instantanée sans modèle
        rapide = _voie_rapide(texte, self.garde)
        if rapide is not None:
            self.memoire.ajouter_message("jibi", rapide["reponse"])
            return rapide

        # Jarvis : un petit modèle se noie avec 47 outils → jeu réduit adapté
        # à la demande ("tous" dans le .env pour l'ancien comportement).
        if config.valeur("JIBI_OUTILS", "noyau").strip().lower() == "tous":
            self._noms_outils = None
        else:
            from outils import outils_pour_message
            self._noms_outils = outils_pour_message(texte)

        if not self.client.disponible():
            resultat = self._repli_local(texte)
            self.memoire.ajouter_message("jibi", resultat["reponse"])
            return resultat

        actions: list[dict] = []
        final = ""
        for _ in range(max_etapes + 1):
            try:
                brut = self._appeler(on_chunk)
            except llm.ErreurLLM as e:
                final = str(e)
                self._ajouter("assistant", final)
                self.memoire.ajouter_message("jibi", final)
                return {"reponse": final, "actions": actions, "ok": False}

            analyse = _extraire_json(brut)
            if analyse is None:                       # une seule relance corrective
                # relance SANS flux : l'aperçu déjà affiché ne doit pas être doublé
                brut2 = self._appeler(
                    None,
                    self._messages() + [{"role": "user", "content": CORRECTIF.format(extrait=brut[:120])}],
                )
                analyse = _extraire_json(brut2)
                if analyse is None:
                    final = llm.nettoyer_think(brut2 or brut)[:1500] or "Je n'ai pas su répondre."
                    break
                brut = brut2

            if isinstance(analyse.get("reponse"), str) and analyse["reponse"].strip():
                final = analyse["reponse"].strip()
                self._ajouter("assistant", llm.nettoyer_think(brut))
                break

            nom = analyse.get("outil")
            if isinstance(nom, str) and nom:
                from outils import executer
                resultat = executer(nom, analyse.get("parametres") or {}, self.garde)
                actions.append({"outil": nom, **resultat})
                self._ajouter("assistant", llm.nettoyer_think(brut))
                suite = ("[Résultat de l'outil " + nom + "] " + resultat["texte"] +
                         "\nRéponds maintenant avec {\"reponse\": \"...\"} en français, "
                         "courtement, à partir de ce résultat.")
                self._ajouter("user", suite)
                continue

            final = "Je n'ai pas compris ce que je voulais faire — reformule, s'il te plaît."
            break

        if not final:
            if actions:
                final = "Voilà ce que j'ai fait : " + " ; ".join(
                    f"{a['outil']} → {a['texte'][:180]}" for a in actions)
            else:
                final = "J'ai atteint ma limite d'actions pour ce message."
        self.memoire.ajouter_message("jibi", final)
        return {"reponse": final, "actions": actions, "ok": True}

    def nouvelle_session(self) -> int:
        self.histoire.clear()
        return self.memoire.nouvelle_session()

    def reprendre(self, session_id: int) -> str:
        """Reprend une session passée : recharge son historique pour continuer."""
        messages = self.memoire.charger_session(session_id)
        if messages is None:
            return f"Session #{session_id} introuvable."
        self.histoire.clear()
        for role, contenu in messages:
            equivalent = "user" if role == "utilisateur" else "assistant"
            self._ajouter(equivalent, contenu)
        n = len(messages)
        titre = next((t for s, t, _ in self.memoire.lister_sessions(50) if s == session_id),
                     f"session #{session_id}")
        return f"Session reprise ({n} message{'s' if n > 1 else ''}) : {titre}"

    # ------------------------------------------------------------- internes
    def _ajouter(self, role: str, contenu: str) -> None:
        if len(contenu) > 1500:      # régime : tout l'historique est relu à
            contenu = contenu[:1500]  # chaque tour (prefill lent sur CPU)
        self.histoire.append({"role": role, "content": contenu})
        if len(self.histoire) > self.max_histoire * 2:
            self.histoire[:] = self.histoire[-self.max_histoire * 2:]

    def _messages(self) -> list[dict]:
        from outils import catalogue_pour_llm

        systeme = (SYSTEME.format(nom=config.valeur("JIBI_NOM", "JIBI"))
                   + "\n\nOutils disponibles :\n" + catalogue_pour_llm(self._noms_outils)
                   + "\n/no_think")          # coupe-faim du raisonnement Qwen
        histoire = list(self.histoire)
        # VITESSE : les VIEUX résultats d'outils (pages web, analyses…) ne
        # servent plus à grand-chose mais gonflent chaque tour → compressés.
        for i in range(len(histoire) - 2):
            contenu = histoire[i]["content"]
            if contenu.startswith("[Résultat de l'outil") and len(contenu) > 220:
                histoire[i] = {**histoire[i], "content": contenu[:220]}
        return [{"role": "system", "content": systeme}] + histoire

    def _repli_local(self, texte: str) -> dict:
        """Quand Ollama est éteint : cas simples traités sans modèle."""
        t = texte.lower().strip()
        def _faire(nom: str, parametres: dict) -> dict:
            from outils import executer
            r = executer(nom, parametres, self.garde)
            return {"outil": nom, **r}
        if "heure" in t or "date" in t or "quel jour" in t:
            r = _faire("heure_actuelle", {})
            return {"reponse": r["texte"], "actions": [r], "ok": r["ok"]}
        m = re.search(r"(?:calcule|combien font|combien fait)\s+(.+)", t)
        if m:
            r = _faire("calculer", {"expression": m.group(1).rstrip("?. !")})
            return {"reponse": r["texte"], "actions": [r], "ok": r["ok"]}
        if t.startswith(("note ", "notez ", "prends note")):
            note = re.sub(r"^(note[rz]? |prends note( que | :)? ?)", "", t)
            r = _faire("ajouter_note", {"texte": note})
            return {"reponse": r["texte"], "actions": [r], "ok": r["ok"]}
        if ("cherche" in t or "recherche" in t) and ("web" in t or "internet" in t):
            requete = re.sub(r".*(cherche|recherche)(-moi)?\s+", "", t)
            requete = re.sub(r"\s+sur\s+(le\s+)?(web|internet).*", "", requete)
            r = _faire("rechercher_web", {"requete": requete})
            return {"reponse": r["texte"], "actions": [r], "ok": r["ok"]}
        if t.startswith("ouvre "):
            cible = texte[6:].strip()
            nom = "ouvrir_site_web" if "." in cible.split()[0] else "ouvrir_application"
            r = _faire(nom, {"cible": cible} if nom == "ouvrir_application" else {"url": cible})
            return {"reponse": r["texte"], "actions": [r], "ok": r["ok"]}
        return {
            "reponse": ("Ollama ne répond pas, je ne peux pas réfléchir. "
                        "Lance Ollama, puis vérifie avec `python docteur.py`. "
                        "En attendant je gère encore : heure, calcule, note…, cherche … sur le web, ouvre …"),
            "actions": [], "ok": False,
        }


# ------------------------------------------------------------------- helpers
def _extraire_json(brut: str) -> dict | None:
    """Tire le premier objet JSON d'une réponse modèle (tolère ``` et texte autour)."""
    if not brut:
        return None
    s = brut.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.MULTILINE).strip()
    debut, fin = s.find("{"), s.rfind("}")
    if debut == -1 or fin <= debut:
        return None
    try:
        objet = json.loads(s[debut:fin + 1])
        return objet if isinstance(objet, dict) else None
    except json.JSONDecodeError:
        return None


def _entier(cle: str, defaut: int) -> int:
    from . import config
    try:
        return int(config.valeur(cle, str(defaut)))
    except ValueError:
        return defaut

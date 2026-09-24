"""Client LLM de JIBI 2 — cerveau local (Ollama) + cerveau cloud (OpenRouter).

ClientLLM   : inchangé, parle à Ollama en local (bibliothèque standard).
ClientCloud : même interface, parle à OpenRouter (API compatible OpenAI).
ClientRouteur : choisit automatiquement local ou cloud selon la complexité
                de la demande, et bascule aussi si le local échoue.
"""
from __future__ import annotations

import contextlib
import json
import re
import threading
import time
import urllib.error
import urllib.request

from . import config

_RE_THINK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def _entier(cle: str, defaut: int) -> int:
    try:
        return int(str(config.valeur(cle, str(defaut))).strip() or defaut)
    except ValueError:
        return defaut


def _plafond() -> int:
    """Plafond de tokens générés (JIBI_LLM_MAX, défaut 600).

    Sans plafond, une réponse qui divague = des MINUTES sur CPU. 600 reste
    assez large pour un appel d'outil bavard (créer un PDF entier).
    """
    return _entier("JIBI_LLM_MAX", 600)


def _contexte() -> int:
    """Fenêtre de contexte (JIBI_LLM_CTX, défaut 4096) : petite = prefill rapide."""
    return _entier("JIBI_LLM_CTX", 4096)


def _keep_alive() -> str:
    """Combien de temps Ollama garde le modèle en RAM (vitesse !).

    JIBI_KEEP_ALIVE dans le .env : minutes ("10m"), heures ("1h") ou -1
    (toujours chargé = réponses instantanées après le 1er message).
    Défaut : 30 m. Sans ça, Ollama décharge le modèle au bout de 5 min
    et chaque échange paie 30-60 s de rechargement sur CPU.
    """
    brut = config.valeur("JIBI_KEEP_ALIVE", "30m").strip() or "30m"
    if brut in ("-1", "toujours"):
        return -1
    if brut.isdigit():
        return f"{brut}m"
    return brut


class ErreurLLM(Exception):
    """Erreur parlante (affichable telle quelle à l'utilisateur)."""


def nettoyer_think(texte: str) -> str:
    """Retire un éventuel bloc <think>…</think> (sécurité défensive)."""
    return _RE_THINK.sub("", texte or "").strip()


class ClientLLM:
    """Cerveau local : Ollama, sur le PC de l'utilisateur."""

    def __init__(self, url: str | None = None, modele: str | None = None) -> None:
        self.url = (url or config.valeur("JIBI_LLM_URL")).rstrip("/")
        self.modele = modele or config.valeur("JIBI_LLM_MODEL", "qwen3.5:4b")
        self.think = config.valeur_bool("JIBI_LLM_THINK")
        self._tags_cache: tuple[float, list[str], str] | None = None

    # ----------------------------------------------------------- état serveur
    def etat(self, force: bool = False) -> tuple[bool, list[str], str]:
        """Renvoie (serveur joignable, modèles installés, version)."""
        if not force and self._tags_cache is not None:
            age = time.time() - self._tags_cache[0]
            if age < 30:
                return True, self._tags_cache[1], self._tags_cache[2]
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=4) as rep:
                donnees = json.loads(rep.read().decode("utf-8"))
        except Exception:
            self._tags_cache = None
            return False, [], ""
        modeles = [m.get("name", "") for m in donnees.get("models", [])]
        version = str(donnees.get("version", ""))
        self._tags_cache = (time.time(), modeles, version)
        return True, modeles, version

    def disponible(self) -> bool:
        return self.etat()[0]

    def modele_present(self) -> bool:
        _, modeles, _ = self.etat()
        base = self.modele.split(":")[0]
        return any(m == self.modele or m.split(":")[0] == base for m in modeles)

    # ------------------------------------------------------------------ chat
    def _corps(self, messages: list[dict], temperature: float,
               stream: bool) -> dict:
        """Corps de requête Ollama, construit à un seul endroit (testable)."""
        return {
            "model": self.modele,
            "messages": messages,
            "stream": stream,
            "think": self.think,
            "keep_alive": _keep_alive(),
            "options": {"temperature": temperature,
                        "num_predict": _plafond(), "num_ctx": _contexte()},
        }

    def discuter(self, messages: list[dict], temperature: float = 0.4) -> str:
        ok, _, _version = self.etat()
        if not ok:
            raise ErreurLLM(
                f"Ollama ne répond pas sur {self.url}.\n"
                "Vérifie qu'il est lancé (icône Ollama ou commande `ollama serve`)."
            )
        corps = self._corps(messages, temperature, stream=False)
        requete = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(corps).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(requete, timeout=600) as rep:
                donnees = json.loads(rep.read().decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ErreurLLM("La réponse d'Ollama est illisible (version trop ancienne ?).") from e
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ErreurLLM(
                    f"Le modèle « {self.modele} » est introuvable dans Ollama.\n"
                    f"Télécharge-le une fois :  ollama pull {self.modele}"
                ) from e
            raise ErreurLLM(f"Ollama a répondu une erreur HTTP {e.code}.") from e
        except urllib.error.URLError as e:
            raise ErreurLLM(f"Ollama ne répond pas sur {self.url}.") from e
        contenu = (donnees.get("message") or {}).get("content", "")
        return nettoyer_think(contenu).strip()

    # ------------------------------------------------------------- chat + flux
    @staticmethod
    def _filtre_think(accumule: str, delta: str, silencieux: bool) -> tuple[str, bool]:
        """Décide quoi émettre pendant un flux, en masquant les blocs <think>."""
        if "<think>" in accumule:
            if "</think>" in accumule:
                return delta.split("</think>", 1)[1], False
            return "", True
        return ("" if silencieux else delta), silencieux

    def _lire_flux(self, reponse, on_chunk) -> str:
        """Lit la réponse NDJSON d'Ollama morceau par morceau."""
        morceaux: list[str] = []
        accumule = ""
        silencieux = False
        for ligne in reponse:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                donnees = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            delta = (donnees.get("message") or {}).get("content", "")
            if not delta:
                if donnees.get("done"):
                    break
                continue
            morceaux.append(delta)
            accumule += delta
            if on_chunk is not None:
                emission, silencieux = self._filtre_think(accumule, delta, silencieux)
                if emission:
                    on_chunk(emission)
            if donnees.get("done"):
                break
        return "".join(morceaux)

    def discuter_stream(self, messages: list[dict], temperature: float = 0.4,
                        on_chunk=None) -> str:
        """Comme discuter(), mais lit la réponse au fil de l'eau (Ollama stream).

        on_chunk(delta) est appelé pour chaque morceau émis (les blocs
        <think> éventuels sont filtrés). Renvoie toujours le texte complet
        nettoyé — c'est lui qui fait foi, l'affichage n'est qu'un aperçu.
        """
        ok, _, _version = self.etat()
        if not ok:
            raise ErreurLLM(
                f"Ollama ne répond pas sur {self.url}.\n"
                "Vérifie qu'il est lancé (icône Ollama ou commande `ollama serve`)."
            )
        corps = self._corps(messages, temperature, stream=True)
        requete = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(corps).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(requete, timeout=600) as reponse:
                complet = self._lire_flux(reponse, on_chunk)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ErreurLLM(
                    f"Le modèle « {self.modele} » est introuvable dans Ollama.\n"
                    f"Télécharge-le une fois :  ollama pull {self.modele}"
                ) from e
            raise ErreurLLM(f"Ollama a répondu une erreur HTTP {e.code}.") from e
        except urllib.error.URLError as e:
            raise ErreurLLM(f"Ollama ne répond pas sur {self.url}.") from e
        return nettoyer_think(complet).strip()


# ═══════════════════════════════════════════════════════════════════════
#  Cerveau cloud : OpenRouter (API compatible OpenAI)
# ═══════════════════════════════════════════════════════════════════════

class ClientCloud:
    """Cerveau distant via OpenRouter — même interface que ClientLLM.

    Sert de repli pour les tâches complexes (voir ClientRouteur plus bas).
    Gratuit avec les modèles ":free" d'OpenRouter (ex. deepseek/deepseek-chat),
    à condition de rester sous leur limite de débit.
    """

    URL_API = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, cle: str | None = None, modele: str | None = None) -> None:
        self.cle = cle or config.valeur("OPENROUTER_API_KEY", "")
        self.modele = modele or config.valeur("JIBI_CLOUD_MODEL", "deepseek/deepseek-chat")

    def disponible(self) -> bool:
        return bool(self.cle)

    def _entetes(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.cle}",
            # Recommandés par OpenRouter (facultatifs mais évitent d'être bridé) :
            "HTTP-Referer": "https://github.com/JIBIXP",
            "X-Title": "JIBI",
        }

    def _corps(self, messages: list[dict], temperature: float, stream: bool) -> dict:
        return {
            "model": self.modele,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": _entier("JIBI_CLOUD_MAX", 1200),
        }

    def _requete(self, corps: dict) -> urllib.request.Request:
        return urllib.request.Request(
            self.URL_API,
            data=json.dumps(corps).encode("utf-8"),
            headers=self._entetes(),
            method="POST",
        )

    def _lever_erreur_http(self, e: urllib.error.HTTPError) -> None:
        if e.code == 401:
            raise ErreurLLM("Clé OPENROUTER_API_KEY invalide ou absente du .env.") from e
        if e.code == 429:
            raise ErreurLLM(
                "Limite de débit OpenRouter atteinte (modèle gratuit). "
                "Réessaie dans un instant, ou repasse en local."
            ) from e
        raise ErreurLLM(f"OpenRouter a répondu une erreur HTTP {e.code}.") from e

    def discuter(self, messages: list[dict], temperature: float = 0.4) -> str:
        if not self.disponible():
            raise ErreurLLM("OPENROUTER_API_KEY absente du .env : le cloud n'est pas configuré.")
        corps = self._corps(messages, temperature, stream=False)
        try:
            with urllib.request.urlopen(self._requete(corps), timeout=120) as rep:
                donnees = json.loads(rep.read().decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ErreurLLM("La réponse d'OpenRouter est illisible.") from e
        except urllib.error.HTTPError as e:
            self._lever_erreur_http(e)
        except urllib.error.URLError as e:
            raise ErreurLLM(f"OpenRouter injoignable (connexion ?) : {e}") from e
        choix = (donnees.get("choices") or [{}])[0]
        contenu = (choix.get("message") or {}).get("content", "")
        return nettoyer_think(contenu).strip()

    def _lire_flux_sse(self, reponse, on_chunk) -> str:
        """Lit un flux SSE ("data: {...}" par ligne, terminé par "data: [DONE]")."""
        morceaux: list[str] = []
        for ligne_brute in reponse:
            ligne = ligne_brute.decode("utf-8", errors="replace").strip()
            if not ligne or not ligne.startswith("data:"):
                continue
            charge = ligne[len("data:"):].strip()
            if charge == "[DONE]":
                break
            try:
                donnees = json.loads(charge)
            except json.JSONDecodeError:
                continue
            delta = ((donnees.get("choices") or [{}])[0].get("delta") or {}).get("content", "")
            if delta:
                morceaux.append(delta)
                if on_chunk is not None:
                    on_chunk(delta)
        return "".join(morceaux)

    def discuter_stream(self, messages: list[dict], temperature: float = 0.4,
                        on_chunk=None) -> str:
        if not self.disponible():
            raise ErreurLLM("OPENROUTER_API_KEY absente du .env : le cloud n'est pas configuré.")
        corps = self._corps(messages, temperature, stream=True)
        try:
            with urllib.request.urlopen(self._requete(corps), timeout=120) as reponse:
                complet = self._lire_flux_sse(reponse, on_chunk)
        except urllib.error.HTTPError as e:
            self._lever_erreur_http(e)
        except urllib.error.URLError as e:
            raise ErreurLLM(f"OpenRouter injoignable (connexion ?) : {e}") from e
        return nettoyer_think(complet).strip()


# ═══════════════════════════════════════════════════════════════════════
#  Routeur : choisit local ou cloud automatiquement
# ═══════════════════════════════════════════════════════════════════════

# Signaux textuels d'une demande "complexe" (code, raisonnement multi-étapes,
# analyse poussée) — volontairement large plutôt que parfait : un faux positif
# occasionnel (bascule cloud pour une question simple) coûte peu ; un faux
# négatif renvoie juste vers le comportement actuel (tout en local).
_MOTS_COMPLEXES = (
    "debug", "déboguer", "corrige le code", "corrige ce code", "erreur dans le code",
    "algorithme", "optimise", "optimiser", "refactore", "refactoriser",
    "analyse en détail", "analyse approfondie", "explique en détail",
    "étape par étape", "plan détaillé", "raisonnement", "démontre",
    "compare en détail", "architecture logicielle",
)
_SEUIL_MOTS = 80  # longueur (en mots) au-delà de laquelle on considère la demande complexe


def _demande_complexe(texte: str) -> bool:
    minuscule = texte.lower()
    if "```" in texte:
        return True
    if any(mot in minuscule for mot in _MOTS_COMPLEXES):
        return True
    return len(texte.split()) > _SEUIL_MOTS


class ClientRouteur:
    """Choisit ClientLLM (local) ou ClientCloud (OpenRouter) automatiquement.

    Règles, dans l'ordre :
    1. Si JIBI_CLOUD_AUTO=0 dans le .env → toujours local (comportement actuel).
    2. Si la demande est jugée complexe (_demande_complexe) ET que le cloud
       est configuré (clé présente) → cloud direct.
    3. Sinon → local ; si le local échoue (Ollama éteint, modèle absent...)
       ET que le cloud est configuré → repli automatique sur le cloud.
    """

    def __init__(self) -> None:
        self.local = ClientLLM()
        self.cloud = ClientCloud()
        self.auto_actif = config.valeur_bool("JIBI_CLOUD_AUTO")
        self._contexte_local = threading.local()
        self.dernier_moteur = "local"  # exposé pour affichage ("JIBI (cloud) › ...")

    @contextlib.contextmanager
    def contexte_local(self):
        """Force le modèle local pour une opération sensible (autonomie)."""
        previous = getattr(self._contexte_local, "active", False)
        self._contexte_local.active = True
        try:
            yield self
        finally:
            self._contexte_local.active = previous

    def _local_force(self) -> bool:
        return bool(getattr(self._contexte_local, "active", False))

    def _choisir(self, texte_utilisateur: str) -> ClientLLM | ClientCloud:
        if self._local_force() or not self.auto_actif or not self.cloud.disponible():
            self.dernier_moteur = "local"
            return self.local
        if _demande_complexe(texte_utilisateur):
            self.dernier_moteur = "cloud"
            return self.cloud
        self.dernier_moteur = "local"
        return self.local

    @staticmethod
    def _dernier_texte_utilisateur(messages: list[dict]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                return m.get("content", "")
        return ""

    def discuter(self, messages: list[dict], temperature: float = 0.4) -> str:
        texte = self._dernier_texte_utilisateur(messages)
        moteur = self._choisir(texte)
        try:
            return moteur.discuter(messages, temperature)
        except ErreurLLM:
            if moteur is self.local and not self._local_force() and self.cloud.disponible():
                self.dernier_moteur = "cloud"
                return self.cloud.discuter(messages, temperature)
            raise

    def _stream_sans_risque_cloud(self, messages: list[dict], temperature: float,
                                   on_chunk) -> str:
        """Le cloud n'émet pas de manière fiable un JSON qui commence pile par
        « { » (préambule, blocs ```json… selon le modèle gratuit tombé) — ça
        casse la détection de silence d'assistant.py (_garde_flux), qui se
        met alors à afficher/dire le flux brut EN PLUS de la réponse finale
        nettoyée juste après → effet de « deux réponses en même temps ».
        Parade : on récupère la réponse cloud d'un seul bloc (pas de vrai
        streaming), puis on l'émet en un seul appel à on_chunk — l'appelant
        (assistant.py) la traite alors exactement comme avant, silencieuse
        tant qu'elle commence par « { »."""
        complet = self.cloud.discuter(messages, temperature)
        if on_chunk is not None and complet:
            on_chunk(complet)
        return complet

    def discuter_stream(self, messages: list[dict], temperature: float = 0.4,
                        on_chunk=None) -> str:
        texte = self._dernier_texte_utilisateur(messages)
        moteur = self._choisir(texte)
        try:
            if moteur is self.cloud:
                return self._stream_sans_risque_cloud(messages, temperature, on_chunk)
            return moteur.discuter_stream(messages, temperature, on_chunk=on_chunk)
        except ErreurLLM:
            if moteur is self.local and not self._local_force() and self.cloud.disponible():
                self.dernier_moteur = "cloud"
                return self._stream_sans_risque_cloud(messages, temperature, on_chunk)
            raise

    # ------------------------------------------------------- délégué au local
    # (le "modèle installé / serveur joignable" ne concerne que le local ;
    #  l'affichage d'entête de la console continue de fonctionner tel quel)
    def etat(self, force: bool = False) -> tuple[bool, list[str], str]:
        return self.local.etat(force)

    def disponible(self) -> bool:
        return self.local.disponible() or self.cloud.disponible()

    def modele_present(self) -> bool:
        return self.local.modele_present()

    @property
    def modele(self) -> str:
        return self.local.modele
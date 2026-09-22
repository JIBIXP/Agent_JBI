"""Client Ollama de JIBI 2 — uniquement la bibliothèque standard (urllib).

Gère : disponibilité, modèles installés, chat avec `think` désactivé
(indispensable avec qwen3.5 : sans quoi le modèle « réfléchit » en texte,
ce qui est lent et rend les appels d'outils illisibles).
"""
from __future__ import annotations

import json
import re
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
    if brut in ("-1", "toujours", "toujours"):
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

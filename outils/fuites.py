"""Outils « fuites de données » de JIBI : mot de passe compromis, adresse e-mail fuitée.

Gravité cloud (lisible dans chaque outil) :
- verifier_fuite_mot_de_passe : API gratuite Pwned Passwords avec k-anonymie —
  SEULS les 5 premiers caractères du SHA-1 quittent le PC ; le mot de passe en
  clair et l'empreinte complète ne sortent jamais, le serveur ne peut pas les
  retrouver.
- verifier_fuites_email : envoie l'adresse telle quelle à un service de fuites ;
  désactivé tant que la clé correspondante n'est pas posée dans le .env
  (JIBI_HIBP_API_KEY, payant, ou JIBI_DEHASHED_USERNAME + JIBI_DEHASHED_API_KEY,
  le compte Dehashed qu'utilise DarkGPT).
"""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request

from outils import outil


# ----------------------------------------------------------------- interne
def _compte_dans_interval(brut: str, fin: str) -> int:
    """Compteur max du suffixe `fin` dans une réponse de type
    « SUFFIXE:nombre » de Pwned Passwords (0 si absent)."""
    maximum = 0
    for ligne in brut.splitlines():
        fin_ligne = ligne.split(":", 1)[0].strip().upper()
        if fin_ligne == fin.strip().upper():
            compteur = ligne.rpartition(":")[2].strip()
            if compteur.isdigit():
                maximum = max(maximum, int(compteur))
    return maximum


def _bilan_mot_de_passe(mot_de_passe: str) -> tuple[int, str]:
    """(compteur max, message d'échec éventuel) via l'API gratuite."""
    complet = hashlib.sha1(mot_de_passe.encode("utf-8")).hexdigest().upper()
    prefixe = complet[:5]
    fin = complet[5:]
    try:
        requete = urllib.request.Request(
            f"https://api.pwnedpasswords.com/range/{prefixe}",
            headers={"User-Agent": "JIBI-Assistant"})
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            brut = reponse.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, f"Impossible de joindre Pwned Passwords ({str(e)[:80]})."
    return _compte_dans_interval(brut, fin), ""


# ------------------------------------------------------------------ outils
@outil("verifier_fuite_mot_de_passe",
       "Vérifie gratuitement si un mot de passe est apparu dans des fuites "
       "publiques (Pwned Passwords, k-anonymie : seuls 5 caractères du SHA-1 "
       "quittent le PC). Ne répète jamais le mot de passe dans la réponse.",
       parametres={"mot_de_passe": {"type": "str", "obligatoire": True,
                                    "description": "le mot de passe à examiner"}},
       categorie="securite", risque="faible",
       exemple="ce mot de passe est-il apparu dans des fuites ?")
def verifier_fuite_mot_de_passe(mot_de_passe: str = "") -> str:
    mot_de_passe = (mot_de_passe or "").strip()
    if not mot_de_passe:
        return "Donne-moi le mot de passe à examiner entre ton message."
    if "\n" in mot_de_passe:
        return "Un seul mot de passe à la fois (pas de retours à la ligne)."
    compteur, echec = _bilan_mot_de_passe(mot_de_passe)
    if echec:
        return echec
    if compteur == 0:
        return ("✅ Rien connu : ce mot de passe n'apparaît dans aucune base "
                "de fuites publique. (Vérification par k-anonymie : seuls 5 "
                "caractères du SHA-1 ont quitté le PC.) Reste vigilant : une "
                "absence de fuite ne prémunit pas d'un mot de passe trop simple.")
    return (f"🚨 COMPROMIS : ce mot de passe apparaît {compteur} fois dans "
            "les bases de fuites publiques. Ne l'utilise plus nulle part : "
            "remplace-le par une passphrase unique, et active "
            "l'authentification à deux facteurs sur tes comptes importants. "
            "(Vérification k-anonymie : seuls 5 caractères du SHA-1 ont "
            "quitté le PC.)")


@outil("verifier_fuites_email",
       "Vérifie si une adresse e-mail apparaît dans des fuites connues. "
       "Nécessite une clé réglée dans le .env : JIBI_HIBP_API_KEY "
       "(haveibeenpwned, payant) ou JIBI_DEHASHED_USERNAME + "
       "JIBI_DEHASHED_API_KEY (le compte Dehashed d'outils type DarkGPT).",
       parametres={"email": {"type": "str", "obligatoire": True,
                             "description": "l'adresse e-mail à vérifier"}},
       categorie="securite", risque="moyen",
       exemple="mes fuites pour prenom.nom@exemple.com ?")
def verifier_fuites_email(email: str = "") -> str:
    from jibi2 import config
    email = (email or "").strip()
    if "@" not in email or email.count("@") != 1 or len(email) < 6:
        return "Donne une adresse e-mail complète (ex : prenom.nom@exemple.com)."
    cle_hibp = config.valeur("JIBI_HIBP_API_KEY", "").strip()
    utilisateur_deh = config.valeur("JIBI_DEHASHED_USERNAME", "").strip()
    cle_deh = config.valeur("JIBI_DEHASHED_API_KEY", "").strip()

    if cle_hibp:
        try:
            chemin = urllib.parse.quote(email, safe="")
            requete = urllib.request.Request(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{chemin}?truncateResponse=false",
                headers={"hibp-api-key": cle_hibp, "Accept": "application/json",
                         "User-Agent": "JIBI-Assistant"})
            with urllib.request.urlopen(requete, timeout=12) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return (f"✅ Aucune fuite connue pour {email} "
                        "(haveibeenpwned, compte à jour).")
            return f"Requête haveibeenpwned refusée (HTTP {e.code})."
        except Exception as e:  # noqa: BLE001
            return f"haveibeenpwned injoignable ({str(e)[:80]})."
        lignes = []
        for fuite in donnees[:8]:
            noms = ", ".join(str(d) for d in fuite.get("DataClasses", [])[:4])
            lignes.append(f"• {fuite.get('Name', '?')} "
                          f"({fuite.get('BreachDate', '?')}) : {noms}")
        plus = "" if len(donnees) <= 8 else f" (+ {len(donnees) - 8} autres)"
        return (f"🚨 {email} apparaît dans {len(donnees)} fuite(s) :{plus}\n"
                + "\n".join(lignes)
                + "\nConseil : change immédiatement les mots de passe de ces "
                  "services (un mot de passe différent partout) et active l'A2F.")

    if utilisateur_deh and cle_deh:
        try:
            jeton = base64.b64encode(
                f"{utilisateur_deh}:{cle_deh}".encode("utf-8")).decode("ascii")
            requete = urllib.request.Request(
                "https://api.dehashed.com/search?query=" + urllib.parse.quote(email),
                headers={"Accept": "application/json",
                         "Authorization": "Basic " + jeton,
                         "User-Agent": "JIBI-Assistant"})
            with urllib.request.urlopen(requete, timeout=12) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            return f"Dehashed injoignable ({str(e)[:80]})."
        entrees = donnees.get("entries") or []
        if not entrees:
            return f"✅ Aucune entrée connue pour {email} (Dehashed)."
        total = donnees.get("total", len(entrees))
        lignes = []
        for entree in entrees[:8]:
            hache = "oui" if entree.get("hashed_password") else "inconnu"
            lignes.append(f"• {entree.get('email') or '?'} | "
                          f"{entree.get('username') or '?'} | base : "
                          f"{entree.get('database_name') or '?'} | "
                          f"hash : {hache}")
        return (f"⚠️ {total} entrée(s) Dehashed pour {email} :\n"
                + "\n".join(lignes)
                + "\nPour la sécurité : change les mots de passe de ces bases "
                  "où tu réutilisais ce mail, et active l'A2F.")

    return ("Aucune clé de fuites réglée pour l'e-mail. Deux options :"
            "\n1. haveibeenpwned.com (payant) → JIBI_HIBP_API_KEY dans ton .env"
            "\n2. dehashed.com (payant, comme DarkGPT) → JIBI_DEHASHED_USERNAME "
            "et JIBI_DEHASHED_API_KEY dans ton .env, puis relance JIBI."
            "\nEn attendant, la vérification de MOT DE PASSE est gratuite : "
            "« mon mot de passe <mdp> est-il dans des fuites ? »")

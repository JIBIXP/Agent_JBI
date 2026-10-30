# -*- coding: utf-8 -*-
"""Section 40 — outils « fuites » : enregistrement, cadres, parse sans réseau."""
import moteur as _moteur
from moteur import *  # noqa: E402,F403  (prélude + partages entre sections)

# Le module se charge via charger_integres si présent, sinon on l'importe ici.
import outils.fuites as fuites  # noqa: E402

verif("outil mot de passe enregistré",
      "verifier_fuite_mot_de_passe" in OUTILS)
verif("outil e-mail enregistré", "verifier_fuites_email" in OUTILS)

# k-anonymie : le calcul sert de garde-fou conceptuel (5 puis reste)
h = __import__("hashlib").sha1("titre-unique-de-test".encode()).hexdigest().upper()
verif("répartition SHA-1 5+35", len(h[:5]) == 5 and len(h[5:]) == 35, h)

# parseur de la réponse « SUFFIXE:compteur », sans réseau
brut = "A0F0F:12\n5B0AF:3\n1ACDF:0\nABCD1:777"
verif("compteur présent", fuites._compte_dans_interval(brut, "abcd1") == 777)
verif("compteur absent → 0", fuites._compte_dans_interval(brut, "FFFFFF") == 0)
verif("casse ignorée", fuites._compte_dans_interval(brut.lower(), "ABCD1") == 777)

# messages de cadre (aucun réseau : l'outil teste d'abord les entrées/sans clé)
G = Garde(lambda n, d: False)
r = executer("verifier_fuite_mot_de_passe", {"mot_de_passe": ""}, G)
verif("mot de passe vide → invitation", r.get("ok") and "Donne" in r.get("texte", ""), r.get("texte"))
r = executer("verifier_fuite_mot_de_passe", {"mot_de_passe": "une\nligne\nplus"}, G)
verif("multi-lignes refusé", r.get("ok") and "Un seul mot de passe" in r.get("texte", ""), r.get("texte"))
r = executer("verifier_fuites_email", {"email": "pas-un-mail"}, G)
verif("e-mail invalide → invitation", r.get("ok") and "adresse e-mail complète" in r.get("texte", ""), r.get("texte"))
from jibi2 import config as _cfg
if not (_cfg.valeur("JIBI_HIBP_API_KEY", "").strip()
        or _cfg.valeur("JIBI_DEHASHED_USERNAME", "").strip()):
    r = executer("verifier_fuites_email", {"email": "test@exemple.com"}, G)
    verif("sans clé → guide d'installation",
          r.get("ok") and "JIBI_HIBP_API_KEY" in r.get("texte", ""), r.get("texte"))

# -*- coding: utf-8 -*-
'''Rail Chrome de JIBI 2 — helpers de recherche Chrome extraits de jibi2/assistant.py.

Tranche T3 de la refonte : extrait TEL QUEL (verbatim), comportement
identique. Les noms restent importables depuis jibi2.assistant, qui
ré-exporte tout (contrat des tests et des rails vivants).
'''
from __future__ import annotations

import re


def _est_sujet_chrome(texte: str) -> bool:


    """Reconnaît un sujet bref envoyé après une question de capacité Chrome."""


    t = " ".join(str(texte or "").strip().split()).rstrip(" ?.!,;:")


    if not 2 <= len(t) <= 160 or "\n" in t or "?" in t:


        return False


    if re.match(r"^(?:oui|non|merci|stop|arr[eê]te|bonjour|salut|hello)\b", t, re.I):


        return False


    if re.search(r"\b(cherche|chercher|recherche|recherches|ouvre|ouvrir|"


                 r"lance|montre|explique|dis|que|quoi)\b", t, re.I):


        return False


    return bool(re.search(r"[\wÀ-ÿ]", t))


def _reponse_chrome(texte: str, garde, sujet_en_attente: bool = False) -> dict | None:


    """Route les demandes Chrome et enchaîne un sujet après une question de capacité."""


    t = " ".join((texte or "").strip().split())


    minuscule = t.lower()


    if (re.search(r"\b(aller|naviguer)\b", minuscule)


            and re.search(r"\b(seul|tout seul)\b", minuscule)):


        return {


            "reponse": ("Oui. Je peux lancer Google dans ChromeJIBI en arrière-plan "


                        "quand tu me donnes un sujet précis, sans afficher la page. "


                        "Si tu demandes explicitement de me la montrer, je l'ouvrirai."),


            "actions": [], "ok": True, "_chrome_attente_sujet": True,


        }





    # Si l'utilisateur vient de demander si JIBI peut chercher dans Chrome,


    # le message bref suivant est son sujet, même s'il ne répète pas « Chrome ».


    requete = t if sujet_en_attente and _est_sujet_chrome(t) else None


    mention = re.search(r"\b(chrome|google|navigateur)\b", minuscule)


    recherche = re.search(r"\b(cherche|chercher|recherche|recherches|trouve)\b", minuscule)


    if requete is None and (not mention or not recherche):


        return None





    if requete is None:


        # Question de capacité sans objet de recherche : répondre oui et demander le sujet.


        motifs = (


            r"\b(?:cherche|chercher|recherche|trouve)\s+(?:moi\s+)?(?:une?|le|la|les|des|un)?\s*(.+?)\s+(?:sur|avec|via)\s+(?:chrome|google)\b",


            r"\b(?:ouvre|ouvrir).*?\bchrome\b.*?\b(?:cherche|chercher|recherche|trouve)\s+(.+)",


            r"\b(?:cherche|chercher|recherche|trouve)\s+(?:sur|avec|via)\s+(?:chrome|google)\s+(?:les?\s+)?(.+)",


            r"\b(?:fais|font|effectue|lance)\s+(?:des\s+)?recherches?\s+(?:sur|avec|via)\s+(.+)",


        )


        for motif in motifs:


            trouve = re.search(motif, minuscule, re.IGNORECASE)


            if trouve:


                candidat = trouve.group(1).strip(" ?.!,;:")


                if len(candidat) >= 2:


                    requete = candidat


                    break


    if requete is None:


        return {


            "reponse": ("Oui. Donne-moi le sujet à rechercher et je lancerai Google "


                        "dans ChromeJIBI en arrière-plan, sans afficher la page."),


            "actions": [], "ok": True, "_chrome_attente_sujet": True,


        }


    # Une demande de recherche utilise Google dans ChromeJIBI sans afficher


    # la page par défaut. Une demande explicite d'afficher passe par le même


    # outil avec afficher=true, donc aucune fenêtre n'est ouverte implicitement.


    visible = bool(re.search(r"\b(ouvre|ouvrir|montre|montrer|affiche|afficher|voir)\b",


                             minuscule, re.IGNORECASE))


    from outils import executer


    actions: list[dict] = []


    if visible:


        resultat = executer("chercher_dans_chrome",


                            {"requete": requete, "afficher": True}, garde)


        actions.append({"outil": "chercher_dans_chrome", **resultat})


        prefixe = ""


    else:


        resultat = executer("chercher_google_headless", {"requete": requete}, garde)


        actions.append({"outil": "chercher_google_headless", **resultat})


        texte = str(resultat.get("texte", "")).lower()


        if (not resultat.get("ok", False)


                or "captcha" in texte or "vérification" in texte


                or "aucun résultat exploitable" in texte):


            # Google peut refuser une session headless temporaire. On ne


            # contourne rien : on relance en arrière-plan dans ChromeJIBI.


            repli = executer("chercher_dans_chrome", {"requete": requete}, garde)


            actions.append({"outil": "chercher_dans_chrome", **repli})


            if repli.get("ok", False):


                resultat = repli


                prefixe = ("Google a bloqué la session headless ; la recherche a été "


                           "relancée dans ChromeJIBI en arrière-plan, sans afficher "


                           "la page.\n\n")


            else:


                prefixe = ("La recherche headless et le repli ChromeJIBI ont échoué.\n\n")


                resultat = {"ok": False, "texte": str(resultat.get("texte", ""))


                            + "\n\n" + str(repli.get("texte", ""))}


        else:


            prefixe = "Recherche Google headless terminée sans afficher Chrome.\n\n"


    return {"reponse": prefixe + resultat.get("texte", ""),


            "actions": actions,


            "ok": bool(resultat.get("ok", False)), "_chrome_attente_sujet": False}

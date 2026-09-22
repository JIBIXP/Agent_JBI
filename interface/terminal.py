"""Console de JIBI 2 — simple, en français, avec commandes slash."""
from __future__ import annotations

import contextlib
import threading

BANNIERE = r"""
   ╔══════════════════════════════════════════╗
   ║   J I B I   2  —  assistant local        ║
   ║   Ollama + voix, tout reste sur ton PC   ║
   ╚══════════════════════════════════════════╝
"""


def confirmer_console(nom_outil: str, detail: str) -> bool:
    print(f"\n⚠️  Action risquée demandée : {nom_outil}\n    {detail}")
    try:
        return input("    Confirmer ? (o/N) ").strip().lower() in ("o", "oui", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def lancer(assistant, garde, memoire, voix_on: bool = False, mains_libres: bool = False,
           annonces=None) -> None:
    from audio import ecoute, parole
    from jibi2 import config, evolution
    from jibi2.llm import ClientLLM

    garde.confirmer = confirmer_console

    if annonces is not None and not mains_libres:
        def _ecouter_annonces() -> None:
            while True:
                message = annonces.get()
                print(f"\n{message}\ntoi › ", end="", flush=True)
        threading.Thread(target=_ecouter_annonces, daemon=True).start()

    if mains_libres:
        from audio.mains_libres import boucle
        with contextlib.suppress(KeyboardInterrupt):
            boucle(assistant)
        return

    client = ClientLLM()
    ok, modeles, version = client.etat(force=True)
    print(BANNIERE)
    print(f"   Modèle   : {client.modele}{'  ✅' if ok and client.modele_present() else '  ❌ (ollama pull ' + client.modele + ')' if ok else '  ❌ Ollama éteint'}")
    print(f"   Mémoire  : {memoire.chemin}")
    print(f"   Voix     : {'on' if voix_on else 'off'}  (/voix on)   Micro : {'✅' if ecoute.micro_disponible() else '—'}")
    print("   Commandes : /aide /outils /bilan /workflows /sessions /notes /propositions "
          "/tester <nom> /valider <nom> /retirer <nom> /verif /micro /voix on|off /nouvelle /quitter")
    flux_on = config.valeur_bool("JIBI_FLUX")

    while True:
        try:
            texte = input("\ntoi › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texte:
            continue

        if texte.startswith("/"):
            commande, _, argument = texte.partition(" ")
            commande = commande.lower()
            if commande in ("/quitter", "/exit", "/q"):
                break
            if commande == "/aide":
                print("Parle simplement à JIBI. Commandes : /outils (liste), /bilan (santé des "
                      "outils), /workflows (routines), /sessions, /notes, /propositions, "
                      "/tester <nom> (bac à sable), /valider <nom> (activer), /retirer <nom> "
                      "(désactiver/restaurer), /verif (tests internes), /micro (parler), "
                      "/voix on|off, /nouvelle, /quitter.")
            elif commande == "/outils":
                from outils import OUTILS
                par_categorie: dict[str, list[str]] = {}
                for o in OUTILS.values():
                    par_categorie.setdefault(o.categorie, []).append(
                        f"{o.nom} [{o.risque}]")
                for cat, noms in sorted(par_categorie.items()):
                    print(f"  {cat} : " + ", ".join(noms))
            elif commande == "/sessions":
                for sid, titre, n in memoire.lister_sessions():
                    print(f"  #{sid} — {titre} ({n} message{'s' if n > 1 else ''})")
            elif commande == "/notes":
                for n, t, h in memoire.lister_notes(15):
                    print(f"  n°{n} — {t}  ({h})")
            elif commande == "/propositions":
                print(evolution.lister_propositions())
            elif commande == "/valider":
                print(evolution.valider(argument))
            elif commande == "/micro":
                print("   🎤 J'écoute… (parle, puis silence)")
                entendu = ecoute.ecouter_phrase()
                if entendu:
                    print(f"   tu as dit : {entendu}")
                    texte = entendu
                else:
                    print("   (rien entendu : " + (ecoute.ERREUR_DERNIERE or "silence") + ")")
                    continue
            elif commande == "/voix":
                voix_on = argument.strip().lower() in ("on", "1", "oui")
                print(f"   Voix : {'on' if voix_on else 'off'}")
                continue
            elif commande == "/nouvelle":
                sid = assistant.nouvelle_session()
                print(f"   Nouvelle session #{sid}.")
                continue
            else:
                print("   Commande inconnue. /aide pour la liste.")
                continue
        else:
            pass

        print("\nJIBI › ", end="", flush=True)
        recu: list[str] = []
        lecteur = parole.LecteurPhrases() if (voix_on and flux_on) else None

        def sur_delta(morceau: str, _recu=recu, _lecteur=lecteur) -> None:
            _recu.append(morceau)
            print(morceau, end="", flush=True)
            if _lecteur is not None:
                _lecteur.alimenter(morceau)

        try:
            reponse = assistant.repondre(texte, on_chunk=sur_delta if flux_on else None)
        except Exception as e:  # noqa: BLE001 — la console ne doit jamais planter
            reponse = {"reponse": f"Erreur interne : {e}", "actions": [], "ok": False}
        if "".join(recu).strip() != reponse["reponse"]:
            # rien diffusé, OU réponse corrigée après relance → affiche la finale
            if recu:
                print("\n   [réponse corrigée] ", end="")
            print(reponse["reponse"], end="")
        print()
        for a in reponse.get("actions", []):
            croix = "✅" if a.get("ok") else "❌"
            print(f"   {croix} outil {a['outil']} : {a['texte'][:200]}")
        if lecteur is not None:
            if "".join(recu).strip() == reponse["reponse"]:
                lecteur.terminer()
                lecteur.attendre()          # console : on attend la fin de la parole
            else:
                lecteur.couper()            # réponse corrigée : on coupe et on dit la finale
                if not parole.parler(reponse["reponse"]):
                    print("   (voix indisponible : " + (parole.ERREUR_DERNIERE or "?") + ")")
        elif voix_on:
            if not parole.parler(reponse["reponse"]):
                print("   (voix indisponible : " + (parole.ERREUR_DERNIERE or "?") + ")")

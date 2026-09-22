"""Interface « boule » de JIBI 2 — HUD inspiré des interfaces de Jarvis.

Une orbe animée (Canvas Tkinter pur, aucune dépendance) indique l'état :
  ● repos      bleu, pulsation lente
  ● écoute     cyan, pulsation rapide + ondes
  ● réflexion  violet, pulsation nerveuse
  ● parole     vert, respiration douce

La conversation défile sous la boule ; les réponses apparaissent au fil
de l'eau (streaming). Threads : tout passe par une file pompée par
root.after — jamais de Tkinter hors du thread principal.
"""
from __future__ import annotations

import json
import math
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

FOND = "#0a0d14"
PANNEAU = "#121722"
TEXTE = "#e8ecf4"
GRIS = "#8a93a6"
ACCENT = "#4f8cff"

COULEURS = {                       # (halo, milieu, cœur)
    "repos": ("#12315e", "#2a62b8", "#7db2ff"),
    "ecoute": ("#0c4a56", "#1294ad", "#5ce4f7"),
    "reflexion": ("#3b2470", "#6d47d8", "#b9a1ff"),
    "parole": ("#0d4d33", "#17a06a", "#67e8b0"),
}
RYTHME = {"repos": 1.1, "ecoute": 4.2, "reflexion": 6.5, "parole": 2.6}

try:  # design personnalisé (donnees/design.json, via personnaliser_design)
    _fichier_design = Path(__file__).parent.parent / "donnees" / "design.json"
    if _fichier_design.exists():
        for _etat, _rgb in json.loads(
                _fichier_design.read_text(encoding="utf-8")).get("orbe", {}).items():
            if _etat in COULEURS and isinstance(_rgb, list) and len(_rgb) == 3:
                COULEURS[_etat] = tuple(str(c) for c in _rgb)
except Exception:                                    # noqa: BLE001
    pass                                             # design d'origine
del _fichier_design


class FenetreJIBI:
    def __init__(self, assistant, garde, voix_on: bool = False, annonces=None) -> None:
        from audio import ecoute
        from jibi2 import config as cfg

        self.assistant = assistant
        self.ecoute = ecoute
        self.voix_module = None
        try:
            from audio import parole as module_parole
            self.voix_module = module_parole
        except Exception:
            pass
        self.annonces = annonces
        self.flux_actif = cfg.valeur_bool("JIBI_FLUX")

        self.root = tk.Tk()
        self.root.title("JIBI — assistant personnel")
        self.root.geometry("1000x700")
        self.root.configure(bg=FOND)
        self.root.minsize(860, 600)
        try:
            base = tkfont.nametofont("TkDefaultFont")
            base.configure(size=10, family="Segoe UI")
            self.root.option_add("*Font", base)
        except Exception:
            pass

        self.file: queue.Queue = queue.Queue()
        self.var_voix = tk.BooleanVar(value=voix_on)
        self.occupe = False
        self.etat_orbe = "repos"
        self._flux_mark = False
        self._t0 = time.time()

        # ── bandeau haut ────────────────────────────────────────────────
        bandeau = tk.Frame(self.root, bg=FOND)
        bandeau.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(bandeau, text="JIBI", bg=FOND, fg=TEXTE,
                 font=(None, 17, "bold")).pack(side="left")
        self.statut = tk.Label(bandeau, text="…", bg=FOND, fg=GRIS)
        self.statut.pack(side="left", padx=(12, 0))
        tk.Button(bandeau, text="⟳ sessions", command=self.choisir_session,
                  bg=PANNEAU, fg=TEXTE, relief="flat", cursor="hand2",
                  activebackground=PANNEAU, activeforeground=ACCENT,
                  bd=0, padx=12, pady=5).pack(side="right", padx=(0, 8))
        tk.Button(bandeau, text="＋ nouvelle session", command=self.nouvelle_session,
                  bg=PANNEAU, fg=TEXTE, relief="flat", cursor="hand2",
                  activebackground=PANNEAU, activeforeground=ACCENT,
                  bd=0, padx=12, pady=5).pack(side="right")

        # ── la boule ────────────────────────────────────────────────────
        self.orbe = tk.Canvas(self.root, width=1000, height=260, bg=FOND,
                              highlightthickness=0)
        self.orbe.pack(fill="x")
        self.orbe.bind("<Button-1>", lambda e: self.micro())
        self.etiquette_etat = tk.Label(self.root, text="prêt — clique sur la boule pour parler",
                                       bg=FOND, fg=GRIS, font=(None, 10))
        self.etiquette_etat.pack()
        self.hint = tk.Label(self.root, text="", bg=FOND, fg=GRIS, font=(None, 1))
        self.hint.pack()

        # ── conversation ────────────────────────────────────────────────
        cadre_chat = tk.Frame(self.root, bg=PANNEAU)
        self.chat = tk.Text(cadre_chat, bg=PANNEAU, fg=TEXTE, wrap="word",
                            relief="flat", padx=16, pady=12, state="disabled",
                            cursor="arrow", spacing1=4, spacing3=5)
        ascenseur = tk.Scrollbar(cadre_chat, command=self.chat.yview,
                                 bg=PANNEAU, troughcolor=FOND, relief="flat")
        self.chat.configure(yscrollcommand=ascenseur.set)
        ascenseur.pack(side="right", fill="y")
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("jibi", foreground=TEXTE, font=(None, 11))
        self.chat.tag_configure("nom", foreground=ACCENT, font=(None, 10, "bold"))
        self.chat.tag_configure("toi", foreground="#b7d9ff")
        self.chat.tag_configure("action", foreground="#67e8b0", font=(None, 9))
        self.chat.tag_configure("heure", foreground=GRIS, font=(None, 8))

        # ── barre de saisie (réserve le bas AVANT d'étendre le chat) ────
        bas = tk.Frame(self.root, bg=FOND)
        bas.pack(side="bottom", fill="x", padx=18, pady=(6, 16))
        self.saisie = tk.Entry(bas, bg=PANNEAU, fg=TEXTE, relief="flat",
                               insertbackground=ACCENT, font=(None, 11))
        self.saisie.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 10))
        self.saisie.bind("<Return>", self._entree)
        a_un_micro = ecoute.micro_disponible()
        self.micro_bouton = tk.Button(bas, text="🎤", command=self.micro,
                                      bg=PANNEAU, fg=TEXTE, relief="flat", cursor="hand2",
                                      activebackground=PANNEAU, font=(None, 12),
                                      state="normal" if a_un_micro else "disabled",
                                      width=3)
        self.micro_bouton.pack(side="left", padx=(0, 8))
        self.dictee_bouton = tk.Button(bas, text="✍️ dicter", command=self.basculer_dictee,
                                       bg=PANNEAU, fg=TEXTE, relief="flat", cursor="hand2",
                                       activebackground=PANNEAU, activeforeground=ACCENT,
                                       state="normal" if a_un_micro else "disabled")
        self.dictee_bouton.pack(side="left", padx=(0, 8))
        self.en_dictee = False
        self.envoyer_bouton = tk.Button(bas, text="Envoyer ⏎", command=self.envoyer,
                                        bg=ACCENT, fg="white", relief="flat", cursor="hand2",
                                        activebackground="#6ba0ff", bd=0, padx=16, pady=7)
        self.envoyer_bouton.pack(side="left")
        self.case_voix = tk.Checkbutton(bas, text="voix", variable=self.var_voix,
                                        bg=FOND, fg=GRIS, activebackground=FOND,
                                        selectcolor=PANNEAU, relief="flat",
                                        highlightthickness=0)
        self.case_voix.pack(side="left", padx=(10, 0))

        cadre_chat.pack(fill="both", expand=True, padx=18, pady=(2, 0))

        self.ajouter_chat("jibi",
                          "Bonjour, je suis JIBI. Je tourne entièrement sur ton PC — "
                          "clique sur ma boule pour me parler, ou écris ici. "
                          "Essaie : « quelle heure est-il », « regarde mon écran », "
                          "« crée une routine du matin à 8 h », « prends note que… ».")
        self._afficher_statut_ollama()
        garde.confirmer = self.confirmer

    # ── statut Ollama ───────────────────────────────────────────────
    def _afficher_statut_ollama(self) -> None:
        from jibi2.llm import ClientLLM
        client = ClientLLM()
        ok, _, _version = client.etat(force=True)
        if ok:
            present = client.modele_present()
            self.statut.config(
                text=f"● {client.modele}" + ("" if present
                      else f" — modèle absent : ollama pull {client.modele}"),
                fg="#67e8b0" if present else "#ff9b9b")
        else:
            self.statut.config(text="● Ollama éteint", fg="#ff9b9b")

    # ── la boule ────────────────────────────────────────────────────
    def _animer(self) -> None:
        t = time.time() - self._t0
        halo, milieu, coeur = COULEURS[self.etat_orbe]
        rythme = RYTHME[self.etat_orbe]
        if self.etat_orbe == "reflexion":
            pouls = 1.0 + 0.05 * (1.0 + math.sin(t * rythme))      # battement nerveux
        else:
            pouls = 1.0 + 0.07 * math.sin(t * rythme)              # respiration douce
        centre_x, centre_y = 500, 128
        rayon = 78 * pouls
        canv = self.orbe
        canv.delete("tout")
        # ondes d'écoute
        if self.etat_orbe == "ecoute":
            for i in range(3):
                phase = (t * 0.9 + i / 3) % 1.0
                r = rayon + 18 + 70 * phase
                intensite = int(40 * (1 - phase))
                canv.create_oval(centre_x - r, centre_y - r, centre_x + r, centre_y + r,
                                 outline=f"#{intensite:02x}{intensite + 40:02x}{intensite + 60:02x}",
                                 width=2)
        canv.create_oval(centre_x - rayon * 1.95, centre_y - rayon * 1.95,
                         centre_x + rayon * 1.95, centre_y + rayon * 1.95,
                         fill=halo, width=0, stipple="gray25")
        canv.create_oval(centre_x - rayon * 1.55, centre_y - rayon * 1.55,
                         centre_x + rayon * 1.55, centre_y + rayon * 1.55, fill=halo, width=0)
        canv.create_oval(centre_x - rayon * 1.28, centre_y - rayon * 1.28,
                         centre_x + rayon * 1.28, centre_y + rayon * 1.28,
                         fill=milieu, width=0, stipple="gray50")
        canv.create_oval(centre_x - rayon * 1.22, centre_y - rayon * 1.22,
                         centre_x + rayon * 1.22, centre_y + rayon * 1.22, fill=milieu, width=0)
        canv.create_oval(centre_x - rayon, centre_y - rayon,
                         centre_x + rayon, centre_y + rayon, fill=coeur, width=0)
        reflet = "#ffffff"
        canv.create_oval(centre_x - rayon * 0.55, centre_y - rayon * 0.62,
                         centre_x + rayon * 0.10, centre_y - rayon * 0.05,
                         fill=reflet, width=0, stipple="gray50")
        canv.create_oval(centre_x - rayon * 0.30, centre_y + rayon * 0.05,
                         centre_x + rayon * 0.30, centre_y + rayon * 0.62,
                         fill=milieu, width=0, stipple="gray75")
        self.root.after(40, self._animer)

    LIBELLES = {"repos": "prêt — clique sur la boule pour parler",
                "ecoute": "je t'écoute…",
                "reflexion": "je réfléchis…",
                "parole": "je réponds…"}

    def _etat(self, nom: str) -> None:
        if nom in COULEURS:
            self.etat_orbe = nom
            self.etiquette_etat.config(text=self.LIBELLES[nom], fg=COULEURS[nom][2])

    # ── affichage conversation ──────────────────────────────────────
    def ajouter_chat(self, qui: str, texte: str) -> None:
        self.chat.config(state="normal")
        horodatage = time.strftime("%H:%M")
        if qui == "toi":
            self.chat.insert("end", f"  toi  {horodatage}\n", ("heure",))
            self.chat.insert("end", texte + "\n\n", ("toi",))
        else:
            self.chat.insert("end", f"  JIBI  {horodatage}\n", ("nom",))
            self.chat.insert("end", texte + "\n\n", ("jibi",))
        self.chat.see("end")
        self.chat.config(state="disabled")

    def ajouter_action(self, texte: str, ok: bool) -> None:
        self.chat.config(state="normal")
        self.chat.insert("end", f"        {'✅' if ok else '❌'} {texte}\n", ("action",))
        self.chat.see("end")
        self.chat.config(state="disabled")

    def _flux_ajouter(self, morceau: str) -> None:
        self.chat.config(state="normal")
        if not self._flux_mark:
            self.chat.insert("end", "\n")
            self.chat.mark_set("flux_start", "end-1c")
            self.chat.mark_gravity("flux_start", "left")
            self._flux_mark = True
        self.chat.insert("end", morceau, ("jibi",))
        self.chat.see("end")
        self.chat.config(state="disabled")

    # ── actions ─────────────────────────────────────────────────────
    def _entree(self, evenement) -> str:
        self.envoyer()
        return "break"

    def envoyer(self) -> None:
        if self.occupe:
            return
        texte = self.saisie.get().strip()
        if not texte:
            return
        self.saisie.delete(0, "end")
        self.ajouter_chat("toi", texte)
        self._lancer_travail(texte)

    def _lancer_travail(self, texte: str) -> None:
        self.occupe = True
        self._etat("reflexion")
        self.envoyer_bouton.config(state="disabled", text="…")
        voix = bool(self.var_voix.get()) and self.voix_module is not None
        threading.Thread(target=self._travail, args=(texte, voix), daemon=True).start()

    def _travail(self, texte: str, voix: bool = False) -> None:
        # FLUIDITÉ : quand la voix est active, chaque phrase complète est
        # DITE pendant que le modèle écrit la suite (LecteurPhrases).
        lecteur = None
        recu: list[str] = []
        if voix and self.flux_actif:
            lecteur = self.voix_module.LecteurPhrases(
                sur_debut=lambda: self.file.put(("etat", "parole")))
        sur_delta = None
        if self.flux_actif:
            def sur_delta(morceau: str) -> None:
                self.file.put(("flux", morceau))
                recu.append(morceau)
                if lecteur is not None:
                    lecteur.alimenter(morceau)
        try:
            reponse = self.assistant.repondre(texte, on_chunk=sur_delta)
        except Exception as e:  # noqa: BLE001 — la fenêtre doit survivre à tout
            reponse = {"reponse": f"Erreur interne : {e}", "actions": [], "ok": False}
        identique = True
        if lecteur is not None:
            lecteur.terminer()
            identique = "".join(recu).strip() == reponse["reponse"]
            threading.Thread(           # rend la parole à « repos » quand finie
                target=lambda: (lecteur.attendre(), self.file.put(("etat", "repos"))),
                daemon=True).start()
        self.file.put(("reponse", (reponse, lecteur, identique)))

    def micro(self) -> None:
        if self.occupe:
            return
        self._etat("ecoute")
        self.micro_bouton.config(state="disabled")

        def travail() -> None:
            entendu = self.ecoute.ecouter_phrase()
            self.file.put(("micro", entendu))

        threading.Thread(target=travail, daemon=True).start()

    def nouvelle_session(self) -> None:
        sid = self.assistant.nouvelle_session()
        self.chat.config(state="normal")
        self.chat.insert("end", f"— nouvelle session #{sid} —\n", ("heure",))
        self.chat.config(state="disabled")
        self.chat.see("end")

    def confirmer(self, nom_outil: str, detail: str) -> bool:
        evenement = threading.Event()
        conteneur = {"ok": False}
        self.file.put(("confirm", nom_outil, detail, evenement, conteneur))
        return evenement.wait(timeout=180) and bool(conteneur["ok"])

    # ── dictée en continu ───────────────────────────────────────────
    def basculer_dictee(self) -> None:
        if self.en_dictee:            # second clic = terminer sans envoyer
            self.file.put(("dictee_fin", ""))
            return
        if self.occupe:
            return
        self.en_dictee = True
        self.dictee_bouton.config(text="⏹ terminer", fg=ACCENT)
        self.saisie.delete(0, "end")
        threading.Thread(target=self._travail_dictee, daemon=True).start()

    def _travail_dictee(self) -> None:
        def sur_partiel(texte: str) -> None:
            self.file.put(("dictee", texte))
        texte = self.ecoute.dicter(mot_fin="envoie", on_partiel=sur_partiel)
        self.file.put(("dictee_fin", texte))

    def _traite_dictee(self, texte: str) -> None:
        self.saisie.delete(0, "end")
        self.saisie.insert(0, texte)

    def _traite_dictee_fin(self, texte: str) -> None:
        self.en_dictee = False
        self.dictee_bouton.config(text="✍️ dicter", fg=TEXTE)
        if texte:
            self._traite_dictee(texte)
            self.envoyer()            # « envoie » dit à la voix = envoi automatique

    # ── reprise de session ──────────────────────────────────────────
    def choisir_session(self) -> None:
        sessions = self.assistant.memoire.lister_sessions(20)
        fenetre = tk.Toplevel(self.root)
        fenetre.title("Reprendre une session")
        fenetre.configure(bg=FOND)
        fenetre.geometry("560x380")
        tk.Label(fenetre, text="Double-clique sur une session pour la reprendre :",
                 bg=FOND, fg=GRIS).pack(anchor="w", padx=14, pady=(12, 6))
        liste = tk.Listbox(fenetre, bg=PANNEAU, fg=TEXTE, relief="flat",
                           selectbackground=ACCENT, font=(None, 10), height=14)
        liste.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        for sid, titre, n in sessions:
            liste.insert("end", f"  #{sid}  —  {titre}  ({n} message{'s' if n > 1 else ''})")

        def reprendre(_evenement=None) -> None:
            selection = liste.curselection()
            if not selection:
                return
            sid = sessions[selection[0]][0]
            fenetre.destroy()
            self._reprendre(sid)

        liste.bind("<Double-Button-1>", reprendre)
        tk.Button(fenetre, text="Reprendre", command=reprendre, bg=ACCENT, fg="white",
                  relief="flat", cursor="hand2", padx=14, pady=6).pack(pady=(0, 14))

    def _reprendre(self, sid: int) -> None:
        message = self.assistant.reprendre(sid)
        if "introuvable" in message:
            self.ajouter_chat("jibi", message)
            return
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.config(state="disabled")
        for role, contenu in self.assistant.memoire.messages_de(sid):
            self.ajouter_chat("toi" if role == "utilisateur" else "jibi", contenu)
        self.ajouter_chat("jibi", message + " — continue, on était là.")

    def _parler(self, texte: str) -> None:
        self.file.put(("etat", "parole"))
        if self.voix_module:
            self.voix_module.parler(texte)
        self.file.put(("etat", "repos"))

    def _traite_etat(self, nom: str) -> None:
        self._etat(nom)

    def _traite_flux(self, morceau: str) -> None:
        self._flux_ajouter(morceau)

    def _traite_reponse(self, paquet) -> None:
        reponse, lecteur, identique = paquet
        if self._flux_mark:      # remplace l'aperçu du flux par la réponse finale
            self.chat.config(state="normal")
            self.chat.delete("flux_start", "end-1c")
            self.chat.config(state="disabled")
            self._flux_mark = False
        for a in reponse.get("actions", []):
            self.ajouter_action(f"{a.get('outil', '?')} : {a.get('texte', '')[:160]}",
                                a.get("ok", False))
        self.ajouter_chat("jibi", reponse["reponse"])
        self.occupe = False
        self.envoyer_bouton.config(state="normal", text="Envoyer ⏎")
        if lecteur is not None and identique:
            return               # la parole est déjà en cours, phrase par phrase
        if lecteur is not None:
            lecteur.couper()     # l'aperçu parlé ne correspondait pas → silence
        if self.var_voix.get() and self.voix_module:
            threading.Thread(target=self._parler, args=(reponse["reponse"],),
                             daemon=True).start()
        else:
            self._etat("repos")

    def _traite_micro(self, entendu: str) -> None:
        self.micro_bouton.config(state="normal" if self.ecoute.micro_disponible()
                                 else "disabled")
        if entendu:
            self.ajouter_chat("toi", entendu)
            self._lancer_travail(entendu)
            return
        if self.ecoute.ERREUR_DERNIERE:
            self.ajouter_chat("jibi", "(micro : " + self.ecoute.ERREUR_DERNIERE + ")")
        self._etat("repos")

    def _traite_confirm(self, nom_outil: str, detail: str, evenement, conteneur) -> None:
        conteneur["ok"] = messagebox.askyesno(
            "JIBI — action risquée",
            f"JIBI demande ton autorisation :\n\n{nom_outil}\n\n{detail}\n\nAutoriser ?")
        evenement.set()

    def _diffuser_annonces(self) -> None:
        """Affiche (et fait parler) les rappels et routines programmées."""
        if self.annonces is None:
            return
        try:
            while True:
                message = self.annonces.get_nowait()
                self.ajouter_chat("jibi", message)
                if self.var_voix.get() and self.voix_module:
                    threading.Thread(target=self.voix_module.parler,
                                     args=(message,), daemon=True).start()
        except queue.Empty:
            pass

    def _pompe(self) -> None:
        self._diffuser_annonces()
        try:
            while True:
                element = self.file.get_nowait()
                getattr(self, "_traite_" + str(element[0]))(*element[1:])
        except queue.Empty:
            pass
        self.root.after(120, self._pompe)

    def run(self) -> None:
        self.root.after(60, self._pompe)
        self.root.after(60, self._animer)
        self.root.mainloop()


def lancer(assistant, garde, voix_on: bool = False, annonces=None) -> None:
    FenetreJIBI(assistant, garde, voix_on=voix_on, annonces=annonces).run()

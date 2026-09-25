"""Interface « boule » de JIBI 2 — HUD futuriste inspiré de Jarvis.

L'orbe, les icônes, la jauge et la pastille de documents sont dessinés en
Canvas/Tkinter pur. Les threads, la file ``self.file`` et les appels
``root.after`` restent centralisés pour ne jamais toucher Tk hors du thread
principal.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import queue
import re
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog
from tkinter import font as tkfont
from tkinter import messagebox

try:  # Pillow est déjà une dépendance de l'interface (vision/imports).
    from PIL import Image, ImageDraw, ImageTk
    _PIL_DISPONIBLE = True
except Exception:  # pragma: no cover - repli Tk si l'installation est incomplète
    Image = ImageDraw = ImageTk = None
    _PIL_DISPONIBLE = False

from . import theme

FOND = theme.FOND
PANNEAU = theme.PANNEAU
TEXTE = theme.TEXTE
GRIS = theme.GRIS
ACCENT = theme.ACCENT
COULEURS = {nom: tuple(couleurs) for nom, couleurs in theme.COULEURS_ORBE.items()}
RYTHME = dict(theme.RYTHMES)

try:  # design personnalisé (donnees/design.json)
    _fichier_design = Path(__file__).parent.parent / "donnees" / "design.json"
    if _fichier_design.exists():
        for _etat, _couleurs in json.loads(
                _fichier_design.read_text(encoding="utf-8")).get("orbe", {}).items():
            if (_etat in COULEURS and isinstance(_couleurs, list)
                    and len(_couleurs) in (2, 3)):
                COULEURS[_etat] = (str(_couleurs[0]), str(_couleurs[-1]))
except Exception:  # noqa: BLE001
    pass
del _fichier_design


_DPI_ACTIVE = False


def _activer_dpi_windows() -> None:
    """Active le rendu DPI natif avant la création de la fenêtre Tk."""
    global _DPI_ACTIVE
    if _DPI_ACTIVE or os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            # -4 = DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        elif hasattr(ctypes.windll, "shcore") and hasattr(
                ctypes.windll.shcore, "SetProcessDpiAwareness"):
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        elif hasattr(user32, "SetProcessDPIAware"):
            user32.SetProcessDPIAware()
        _DPI_ACTIVE = True
    except Exception:
        # Le réglage DPI est une amélioration : ne doit jamais empêcher JIBI.
        _DPI_ACTIVE = True


def _normaliser_texte(texte) -> str:
    """Nettoie les sorties console avant de les afficher dans la conversation."""
    valeur = str(texte or "")
    # Les sorties Windows utilisent souvent des espaces insécables pour les
    # milliers ; ils doivent avoir la même largeur et le même rendu que l'espace.
    valeur = valeur.replace("\u00a0", " ").replace("\u202f", " ")
    # Si une décodification a déjà perdu un octet séparateur entre deux
    # nombres (3�176), le remplacer par un espace plutôt que laisser le glyphe.
    valeur = re.sub(r"(?<=\d)\ufffd(?=\d)", " ", valeur)
    return valeur.replace("\ufffd", "").replace("\x00", "")


def _est_sortie_systeme(texte: str) -> bool:
    """Reconnaît les blocs déjà formatés pour un affichage monospace."""
    valeur = _normaliser_texte(texte).lstrip().lower()
    if not valeur:
        return False
    if valeur.startswith(("signaux du pc", "signaux pc", "sortie système",
                           "sortie systeme", "processus", "tasklist", "ps aux",
                           "résultat de la commande", "resultat de la commande")):
        return True
    extrait = valeur[:800]
    return (("processus" in extrait or "tasklist" in extrait or "ps aux" in extrait)
            and "\n" in extrait) or (
        "signaux du pc" in extrait and "\n" in extrait)


def _icone(canvas: tk.Canvas, nom: str, x: float, y: float,
           taille: float, couleur: str) -> None:
    """Dessine une petite icône vectorielle, sans emoji ni police spéciale."""
    r = taille
    if nom == "telechargement":
        canvas.create_line(x, y - r * .55, x, y + r * .15, fill=couleur, width=2)
        canvas.create_polygon(x - r * .32, y - r * .02, x + r * .32, y - r * .02,
                              x, y + r * .38, fill=couleur, outline="")
        canvas.create_line(x - r * .48, y + r * .62, x + r * .48, y + r * .62,
                           fill=couleur, width=2)
    elif nom == "signal":
        canvas.create_line(x, y + r * .55, x, y - r * .45, fill=couleur, width=2)
        canvas.create_oval(x - r * .12, y - r * .62, x + r * .12, y - r * .38,
                           outline=couleur, width=2)
        canvas.create_arc(x - r * .42, y - r * .35, x + r * .42, y + r * .25,
                          start=205, extent=130, style="arc", outline=couleur, width=2)
        canvas.create_arc(x - r * .68, y - r * .52, x + r * .68, y + r * .42,
                          start=205, extent=130, style="arc", outline=couleur, width=2)
    elif nom == "rafraichir":
        canvas.create_arc(x - r * .55, y - r * .55, x + r * .55, y + r * .55,
                          start=35, extent=285, style="arc", outline=couleur, width=2)
        canvas.create_polygon(x + r * .22, y - r * .65, x + r * .67, y - r * .38,
                              x + r * .27, y - r * .12, fill=couleur, outline="")
    elif nom == "plus":
        canvas.create_line(x - r * .55, y, x + r * .55, y, fill=couleur, width=2)
        canvas.create_line(x, y - r * .55, x, y + r * .55, fill=couleur, width=2)
    elif nom == "micro":
        canvas.create_oval(x - r * .28, y - r * .58, x + r * .28, y + r * .12,
                           outline=couleur, width=2)
        canvas.create_arc(x - r * .52, y - r * .18, x + r * .52, y + r * .48,
                          start=200, extent=140, style="arc", outline=couleur, width=2)
        canvas.create_line(x, y + r * .48, x, y + r * .68, fill=couleur, width=2)
        canvas.create_line(x - r * .28, y + r * .68, x + r * .28, y + r * .68,
                           fill=couleur, width=2)
    elif nom == "stylo":
        canvas.create_line(x - r * .42, y + r * .48, x + r * .35, y - r * .42,
                           fill=couleur, width=3)
        canvas.create_polygon(x - r * .55, y + r * .62, x - r * .22, y + r * .3,
                              x - r * .38, y + r * .15, fill=couleur, outline="")
    elif nom == "envoyer":
        canvas.create_polygon(x - r * .5, y - r * .45, x + r * .58, y,
                              x - r * .5, y + r * .45, fill=couleur, outline="")
    elif nom == "bibliotheque":
        canvas.create_rectangle(x - r * .55, y - r * .42, x + r * .55, y + r * .5,
                               outline=couleur, width=2)
        canvas.create_line(x - r * .25, y - r * .42, x - r * .25, y + r * .5,
                           fill=couleur, width=2)
        canvas.create_line(x - r * .12, y - r * .42, x - r * .12, y + r * .5,
                           fill=couleur, width=2)
    elif nom == "check":
        canvas.create_line(x - r * .5, y, x - r * .12, y + r * .38,
                           fill=couleur, width=3)
        canvas.create_line(x - r * .12, y + r * .38, x + r * .55, y - r * .42,
                           fill=couleur, width=3)
    elif nom == "croix":
        canvas.create_line(x - r * .42, y - r * .42, x + r * .42, y + r * .42,
                           fill=couleur, width=3)
        canvas.create_line(x + r * .42, y - r * .42, x - r * .42, y + r * .42,
                           fill=couleur, width=3)
    elif nom == "cloche":
        canvas.create_arc(x - r * .48, y - r * .62, x + r * .48, y + r * .28,
                          start=180, extent=180, style="arc", outline=couleur, width=2)
        canvas.create_line(x - r * .58, y + r * .28, x + r * .58, y + r * .28,
                           fill=couleur, width=2)
        canvas.create_oval(x - r * .12, y + r * .42, x + r * .12, y + r * .66,
                           outline=couleur, width=2)
    elif nom == "arrete":
        canvas.create_rectangle(x - r * .35, y - r * .35, x + r * .35, y + r * .35,
                                fill=couleur, outline="")


def _rgba(couleur: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Convertit une couleur hexadécimale pour Pillow."""
    valeur = str(couleur or "#000000").lstrip("#")
    if len(valeur) == 3:
        valeur = "".join(c * 2 for c in valeur)
    if len(valeur) < 6:
        valeur = valeur.ljust(6, "0")
    try:
        return (int(valeur[0:2], 16), int(valeur[2:4], 16),
                int(valeur[4:6], 16), max(0, min(255, int(alpha))))
    except ValueError:
        return (0, 0, 0, max(0, min(255, int(alpha))))


def _melanger(couleur_a: str, couleur_b: str, proportion: float) -> tuple[int, int, int]:
    a, b = _rgba(couleur_a), _rgba(couleur_b)
    p = max(0.0, min(1.0, float(proportion)))
    return tuple(int(a[i] + (b[i] - a[i]) * p) for i in range(3))


def _points_arrondis(x0: float, y0: float, x1: float, y1: float,
                     rayon: float, segments: int = 6) -> list[float]:
    """Contour d'un rectangle arrondi en un seul polygone (sans cercles)."""
    r = max(0.0, min(float(rayon), (x1 - x0) / 2, (y1 - y0) / 2))
    if r <= 0:
        return [x0, y0, x1, y0, x1, y1, x0, y1]
    points: list[float] = []
    coins = ((x1 - r, y0 + r, -90, 0), (x1 - r, y1 - r, 0, 90),
             (x0 + r, y1 - r, 90, 180), (x0 + r, y0 + r, 180, 270))
    import math
    for cx, cy, debut, fin in coins:
        for i in range(segments + 1):
            angle = math.radians(debut + (fin - debut) * i / segments)
            points.extend((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def _icone_barre(canvas: tk.Canvas, nom: str, x: float, y: float,
                 taille: float, couleur: str) -> None:
    """Trait fin et cohérent pour les icônes de la capsule de saisie."""
    r = taille
    trait = 1.6
    if nom == "voix":
        canvas.create_oval(x - r * .22, y - r * .48, x + r * .22, y + r * .12,
                           outline=couleur, width=trait)
        canvas.create_arc(x - r * .38, y - r * .18, x + r * .38, y + r * .40,
                          start=200, extent=140, style="arc", outline=couleur, width=trait)
        canvas.create_line(x, y + r * .40, x, y + r * .62, fill=couleur,
                           width=trait, capstyle="round")
        canvas.create_line(x - r * .20, y + r * .62, x + r * .20, y + r * .62,
                           fill=couleur, width=trait, capstyle="round")
    elif nom == "dictee":
        canvas.create_oval(x - r * .18, y - r * .46, x + r * .18, y + r * .06,
                           outline=couleur, width=trait)
        canvas.create_arc(x - r * .32, y - r * .18, x + r * .32, y + r * .30,
                          start=200, extent=140, style="arc", outline=couleur, width=trait)
        canvas.create_line(x, y + r * .30, x, y + r * .48, fill=couleur,
                           width=trait, capstyle="round")
        canvas.create_arc(x - r * .58, y - r * .30, x - r * .28, y + r * .28,
                          start=115, extent=130, style="arc", outline=couleur, width=1.3)
        canvas.create_arc(x + r * .28, y - r * .30, x + r * .58, y + r * .28,
                          start=295, extent=130, style="arc", outline=couleur, width=1.3)
    elif nom == "trombone":
        canvas.create_line(x + r * .38, y - r * .48, x - r * .28, y + r * .18,
                           fill=couleur, width=trait, capstyle="round")
        canvas.create_arc(x - r * .68, y - r * .18, x + r * .18, y + r * .68,
                          start=270, extent=180, style="arc", outline=couleur, width=trait)
        canvas.create_line(x - r * .25, y + r * .43, x + r * .40, y - r * .22,
                           fill=couleur, width=trait, capstyle="round")
        canvas.create_arc(x - r * .18, y - r * .68, x + r * .68, y + r * .18,
                          start=90, extent=180, style="arc", outline=couleur, width=trait)
    elif nom == "envoi":
        canvas.create_line(x, y + r * .48, x, y - r * .48, fill=couleur,
                           width=1.9, capstyle="round")
        canvas.create_line(x - r * .30, y - r * .16, x, y - r * .48,
                           fill=couleur, width=1.9, capstyle="round")
        canvas.create_line(x + r * .30, y - r * .16, x, y - r * .48,
                           fill=couleur, width=1.9, capstyle="round")
    elif nom == "arrete":
        points = _points_arrondis(x - r * .32, y - r * .32, x + r * .32, y + r * .32,
                                  r * .10, 4)
        canvas.create_polygon(points, fill=couleur, outline="")
    elif nom == "verrou":
        # Cadenas : anse en arc + corps rectangulaire arrondi.
        # NB : create_arc n'accepte pas capstyle (crash Tk), on n'en met pas.
        canvas.create_arc(x - r * .30, y - r * .62, x + r * .30, y + r * .02,
                          start=0, extent=180, style="arc", outline=couleur,
                          width=trait)
        points = _points_arrondis(x - r * .42, y - r * .08, x + r * .42, y + r * .60,
                                  r * .12, 5)
        canvas.create_polygon(points, fill="", outline=couleur, width=trait,
                              smooth=True)
        canvas.create_oval(x - r * .07, y + r * .16, x + r * .07, y + r * .30,
                           fill=couleur, outline="")


def _texte_sans_boucle(texte: str) -> str:
    """Évite de lire ou d'afficher plusieurs fois un même sous-titre."""
    lignes: list[str] = []
    vus: dict[str, int] = {}
    for brute in str(texte or "").splitlines():
        ligne = brute.strip()
        if not ligne:
            if lignes and lignes[-1] != "":
                lignes.append("")
            continue
        if ligne == "Sous-titres réalisés par la communauté d'Amara.org":
            if vus.get(ligne, 0) >= 1:
                continue
        elif vus.get(ligne, 0) >= 2:
            continue
        vus[ligne] = vus.get(ligne, 0) + 1
        lignes.append(ligne)
    return "\n".join(lignes).strip()


class _BoutonIcone(tk.Frame):
    """Bouton Canvas avec une icône vectorielle et un libellé optionnel."""

    def __init__(self, parent, nom: str, texte: str, commande,
                 couleur: str = theme.ACCENT_CLAIR, taille: int = 22):
        super().__init__(parent, bg=theme.PANNEAU, cursor="hand2")
        self._nom = nom
        self._texte = texte
        self._actif = True
        self._commande = commande
        self._icone = tk.Canvas(self, width=taille, height=taille,
                                bg=theme.PANNEAU, highlightthickness=0)
        self._icone.pack(side="left", padx=(8, 0), pady=4)
        _icone(self._icone, nom, taille / 2, taille / 2, taille * .38, couleur)
        self._label = tk.Label(self, text=texte, bg=theme.PANNEAU, fg=theme.TEXTE,
                               font=(theme.POLICE, theme.TAILLE_BASE))
        self._label.pack(side="left", padx=(5, 9), pady=4)
        for widget in (self, self._icone, self._label):
            widget.bind("<Button-1>", lambda _event: self._cliquer())
            widget.bind("<Enter>", lambda _event: self._survol(True))
            widget.bind("<Leave>", lambda _event: self._survol(False))

    def _cliquer(self) -> None:
        if self._actif:
            self._commande()

    def _survol(self, actif: bool) -> None:
        couleur = theme.PANNEAU_CLAIR if actif else theme.PANNEAU
        self.configure(bg=couleur)
        self._icone.configure(bg=couleur)
        self._label.configure(bg=couleur)

    def set_texte(self, texte: str) -> None:
        self._texte = texte
        self._label.configure(text=texte)

    def set_etat(self, etat: str) -> None:
        self._actif = etat != "disabled"
        self._icone.configure(cursor="arrow" if etat == "disabled" else "hand2")
        for item in self._icone.find_all():
            self._icone.itemconfigure(item, state=etat)
        self._label.configure(fg=theme.GRIS if etat == "disabled" else theme.TEXTE)
        self.configure(cursor="arrow" if etat == "disabled" else "hand2")

    def set_couleur(self, couleur: str) -> None:
        self._icone.delete("all")
        _icone(self._icone, self._nom, 11, 11, 8.4, couleur)


class _ChampSaisieAuto(tk.Frame):
    """Champ multiligne qui grandit vers le haut, avec défilement interne."""

    def __init__(self, parent, on_change=None, on_return=None):
        super().__init__(parent, bg=theme.FOND, highlightthickness=0)
        self._on_change = on_change
        self._on_return = on_return
        self._lignes = 1
        self._scroll_visible = False
        self._focused = False
        self._police = tkfont.Font(family=theme.POLICE, size=theme.TAILLE_CHAT)
        self._police_metrics = self._police.metrics()
        # La hauteur est pilotée par _ajuster ; ne pas laisser le Canvas
        # de fond propager une taille arbitraire au layout de la fenêtre.
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.configure(width=1, height=self._police_metrics["linespace"] + 16)
        self.fond = tk.Canvas(self, bg=theme.FOND, highlightthickness=0, bd=0)
        self.fond.pack(fill="both", expand=True)
        self.text = tk.Text(
            self, height=1, width=1, bg=theme.CHAMP, fg=theme.TEXTE,
            insertbackground=theme.ACCENT_CLAIR, selectbackground=theme.ACCENT,
            selectforeground=theme.FOND, wrap="word", bd=0, highlightthickness=0,
            font=self._police, padx=0, pady=0, spacing1=2, spacing3=2,
            undo=True, cursor="xterm")
        self.defilement = tk.Scrollbar(self, orient="vertical", command=self.text.yview,
                                       width=11, bd=0, relief="flat", bg=theme.PANNEAU_CLAIR,
                                       troughcolor=theme.FOND, activebackground=theme.ACCENT)
        self.text.configure(yscrollcommand=self.defilement.set)
        self.text.bind("<<Modified>>", self._modifie)
        self.text.bind("<KeyRelease>", lambda _e: self._ajuster())
        self.text.bind("<ButtonRelease-1>", lambda _e: self._ajuster())
        self.text.bind("<Return>", self._retour)
        self.text.bind("<Shift-Return>", self._retour_ligne)
        self.text.bind("<FocusIn>", self._focus_in)
        self.text.bind("<FocusOut>", self._focus_out)
        self.bind("<Configure>", self._layout)
        self.fond.bind("<Configure>", self._layout)
        self.after_idle(self._layout)
        self.after(60, self._layout)

    def _focus_in(self, _event=None):
        self._focused = True
        self._dessiner()

    def _focus_out(self, _event=None):
        self._focused = False
        self._dessiner()

    def _dessiner(self):
        self.fond.delete("all")
        w = max(1, self.fond.winfo_width())
        h = max(1, self.fond.winfo_height())
        rayon = 15
        couleur = theme.ACCENT if self._focused else theme.CHAMP_BORD
        # Halo discret au focus, puis bordureFine.
        if self._focused:
            self.fond.create_oval(3, 3, w - 3, h - 3, outline=theme.ACCENT,
                                   width=2)
        self.fond.create_oval(1, 1, 1 + rayon * 2, 1 + rayon * 2,
                               fill=theme.CHAMP, outline=couleur, width=1)
        self.fond.create_oval(w - 1 - rayon * 2, 1, w - 1, 1 + rayon * 2,
                               fill=theme.CHAMP, outline=couleur, width=1)
        self.fond.create_oval(1, h - 1 - rayon * 2, 1 + rayon * 2, h - 1,
                               fill=theme.CHAMP, outline=couleur, width=1)
        self.fond.create_oval(w - 1 - rayon * 2, h - 1 - rayon * 2, w - 1, h - 1,
                               fill=theme.CHAMP, outline=couleur, width=1)
        self.fond.create_rectangle(1 + rayon, 1, w - 1 - rayon, h - 1,
                                   fill=theme.CHAMP, outline="")
        if self._focused:
            self.fond.create_line(18, 2, w - 18, 2, fill=theme.ACCENT, width=1)
            self.fond.create_line(18, h - 2, w - 18, h - 2, fill=theme.ACCENT, width=1)
        self._placer_enfants(w, h)

    def _placer_enfants(self, w=None, h=None):
        w = w or max(1, self.fond.winfo_width())
        h = h or max(1, self.fond.winfo_height())
        if self._scroll_visible:
            self.defilement.place(x=w - 16, y=9, height=max(1, h - 18))
            largeur_texte = max(20, w - 34)
        else:
            self.defilement.place_forget()
            largeur_texte = max(20, w - 28)
        self.text.place(x=14, y=8, width=largeur_texte, height=max(1, h - 16))

    def _layout(self, _event=None):
        if self.fond.winfo_width() <= 1:
            return
        self._dessiner()

    def _modifie(self, _event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self._ajuster()
        if self._on_change:
            self._on_change(self.get())

    def _compter_lignes_visuelles(self, contenu: str) -> int:
        """Estime le retour à la ligne même quand le Text est encore à une ligne."""
        if not contenu:
            return 1
        largeur = max(40, self.text.winfo_width() - 28)
        unite = max(1, self._police.measure("M"))
        total = 0
        for paragraphe in contenu.split("\n"):
            if not paragraphe:
                total += 1
                continue
            courant = 0
            lignes = 1
            for mot in paragraphe.split():
                largeur_mot = self._police.measure(mot + " ")
                if courant and courant + largeur_mot > largeur:
                    lignes += 1
                    courant = largeur_mot
                else:
                    courant += largeur_mot
                if largeur_mot > largeur:
                    lignes += max(0, int((largeur_mot - 1) // largeur))
            total += lignes
        return max(1, total)

    def _ajuster(self):
        self.update_idletasks()
        contenu = self.get()
        lignes = self._compter_lignes_visuelles(contenu)
        cible = max(1, min(6, lignes))
        if cible != self._lignes:
            self._lignes = cible
            self.text.configure(height=cible)
            hauteur = cible * self._police_metrics["linespace"] + 16
            self.configure(height=hauteur)
            self.update_idletasks()
            self._dessiner()
        if cible >= 6 and len(contenu) > 0:
            self._scroll_visible = True
        else:
            self._scroll_visible = False
        self._placer_enfants()

    def _retour_ligne(self, _evenement=None):
        self.text.insert("insert", "\n")
        self._ajuster()
        return "break"

    def _retour(self, evenement):
        if int(evenement.state) & 0x0001:  # Maj+Entrée
            self.text.insert("insert", "\n")
            self._ajuster()
            return "break"
        if self._on_return:
            self._on_return(evenement)
        return "break"

    def get(self):
        return self.text.get("1.0", "end-1c")

    def delete(self, debut, fin=None):
        if debut == 0 and fin == "end":
            self.text.delete("1.0", "end")
            self._lignes = 1
            self.text.configure(height=1)
            self.configure(height=self._police_metrics["linespace"] + 16)
            self._scroll_visible = False
            self._dessiner()
            if self._on_change:
                self._on_change(self.get())
        else:
            if debut == 0:
                debut = "1.0"
            if fin is None:
                self.text.delete(debut)
            else:
                self.text.delete(debut, fin)

    def insert(self, index, valeur):
        if index == 0:
            index = "1.0"
        self.text.insert(index, _normaliser_texte(valeur))
        self._ajuster()
        if self._on_change:
            self._on_change(self.get())

    def bind(self, sequence=None, command=None, add=None):
        return self.text.bind(sequence, command, add)

    def focus_set(self):
        return self.text.focus_set()


class _BoutonBarre(tk.Frame):
    """Bouton rond de la capsule, sans texte visible et avec infobulle."""

    def __init__(self, barre, nom: str, infobulle: str, commande) -> None:
        self._barre = barre
        self._nom = nom
        self._infobulle = infobulle
        self._commande = commande
        self._visible = True
        self._actif = True
        self._survol = False
        self._actif_voix = False
        self._fond_base = theme.CAPSULE_FOND
        self._fond_actuel = _melanger(theme.CAPSULE_FOND, theme.CAPSULE_FOND, 0)
        self._animation = None
        self._tip = None
        self._tip_after = None
        super().__init__(barre, width=theme.BARRE_ICONE, height=theme.BARRE_ICONE,
                         bg=theme.CAPSULE_FOND, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.canevas = tk.Canvas(self, width=theme.BARRE_ICONE, height=theme.BARRE_ICONE,
                                 bg=theme.CAPSULE_FOND, highlightthickness=0, bd=0,
                                 cursor="hand2")
        self.canevas.pack(fill="both", expand=True)
        for widget in (self, self.canevas):
            widget.bind("<Button-1>", lambda _e: self._cliquer())
            widget.bind("<Enter>", self._survol_entrer)
            widget.bind("<Leave>", self._survol_sortir)
            widget.bind("<Motion>", self._survol_deplacer)
        self._dessiner()

    @staticmethod
    def _vers_hex(couleur) -> str:
        return "#{:02x}{:02x}{:02x}".format(*couleur[:3])

    def _cliquer(self) -> None:
        if self._visible and self._actif:
            self._commande()

    def _survol_entrer(self, _event=None) -> None:
        self._survol = True
        self._animer_fond()
        self._annuler_infobulle()
        self._tip_after = self.after(450, self._afficher_infobulle)

    def _survol_sortir(self, _event=None) -> None:
        self._survol = False
        self._animer_fond()
        self._masquer_infobulle()

    def _survol_deplacer(self, _event=None) -> None:
        if self._tip is not None:
            self._placer_infobulle()

    def _annuler_infobulle(self) -> None:
        if self._tip_after is not None:
            try:
                self.after_cancel(self._tip_after)
            except Exception:
                pass
            self._tip_after = None

    def _afficher_infobulle(self) -> None:
        self._tip_after = None
        if not self._survol or not self._visible:
            return
        racine = self.winfo_toplevel()
        self._tip = tk.Label(racine, text=self._infobulle, bg=theme.PANNEAU_CLAIR,
                              fg=theme.TEXTE_PUR, font=(theme.POLICE, theme.TAILLE_PETIT),
                              padx=8, pady=4, bd=0, relief="flat")
        self._tip.update_idletasks()
        self._placer_infobulle()

    def _placer_infobulle(self) -> None:
        if self._tip is None:
            return
        racine = self.winfo_toplevel()
        largeur = self._tip.winfo_reqwidth()
        x = self.winfo_rootx() + self.winfo_width() // 2 - largeur // 2 - racine.winfo_rootx()
        y = self.winfo_rooty() - self._tip.winfo_reqheight() - 8 - racine.winfo_rooty()
        self._tip.place(x=max(4, x), y=max(4, y))

    def _masquer_infobulle(self) -> None:
        self._annuler_infobulle()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

    def _couleur_cible(self) -> tuple[int, int, int]:
        if not self._actif:
            return _melanger(theme.CAPSULE_FOND, theme.CAPSULE_FOND, 0)
        if self._nom == "envoi":
            if self._survol:
                return _melanger(theme.BOUTON_CLAIR, theme.TEXTE_PUR, .35)
            return _melanger(theme.BOUTON_CLAIR, theme.BOUTON_CLAIR, 0)
        if self._nom == "arrete":
            return _melanger(theme.ROUGE, theme.ROUGE, 0)
        if self._actif_voix:
            if self._survol:
                return _melanger(theme.ACCENT, theme.ACCENT_CLAIR, .45)
            return _melanger(theme.ACCENT, theme.ACCENT, 0)
        if self._survol:
            return _melanger(self._fond_base, theme.CAPSULE_FOND_SURVOL, 1)
        return _melanger(self._fond_base, self._fond_base, 0)

    def _icone_couleur(self) -> str:
        if not self._actif:
            return theme.GRIS
        if self._nom in ("envoi", "arrete") and self._actif:
            return theme.FOND
        if self._survol or self._actif_voix:
            return theme.TEXTE_PUR
        return theme.CAPSULE_TEXTE

    def _animer_fond(self) -> None:
        if self._animation is not None:
            try:
                self.after_cancel(self._animation)
            except Exception:
                pass
        depart = self._fond_actuel
        arrivee = self._couleur_cible()
        if all(abs(a - b) < 1 for a, b in zip(depart, arrivee)):
            self._fond_actuel = arrivee
            self._dessiner()
            return
        etapes = max(1, int(theme.TRANSITION_MS / 20))
        debut = time.monotonic()

        def pas(_=None):
            fraction = min(1.0, (time.monotonic() - debut) * 1000 / theme.TRANSITION_MS)
            self._fond_actuel = tuple(int(depart[i] + (arrivee[i] - depart[i]) * fraction)
                                      for i in range(3))
            self._dessiner()
            if fraction < 1:
                self._animation = self.after(20, pas)
            else:
                self._animation = None
                self._fond_actuel = arrivee
                self._dessiner()

        self._animation = self.after(20, pas)

    def _dessiner(self) -> None:
        couleur_fond = self._vers_hex(self._fond_actuel)
        self.configure(bg=couleur_fond)
        self.canevas.configure(bg=couleur_fond)
        c = self.canevas
        c.delete("all")
        n = theme.BARRE_ICONE
        if self._nom == "envoi":
            c.create_oval(1, 1, n - 1, n - 1, fill=couleur_fond, outline="")
        else:
            points = _points_arrondis(1, 1, n - 1, n - 1, 10, 6)
            c.create_polygon(points, fill=couleur_fond, outline="")
        _icone_barre(c, self._nom, n / 2, n / 2, 10, self._icone_couleur())
        c.configure(cursor="hand2" if self._actif and self._visible else "arrow")

    def set_fond(self, couleur: str, anime: bool = True) -> None:
        self._fond_base = couleur
        if not anime:
            # La capsule peut se redessiner pendant une transition ; ne pas
            # écraser la couleur active d'un bouton déjà animé.
            if (self._animation is None and self._nom not in ("envoi", "arrete")
                    and not self._survol and not self._actif_voix):
                self._fond_actuel = _melanger(couleur, couleur, 0)
            self._dessiner()
            return
        self._animer_fond()

    def set_etat(self, etat: str) -> None:
        self._actif = etat != "disabled"
        self.canevas.configure(cursor="hand2" if self._actif and self._visible else "arrow")
        if not self._actif:
            self._masquer_infobulle()
        self._animer_fond()

    def set_actif(self, actif: bool) -> None:
        self._actif_voix = bool(actif)
        self._animer_fond()

    def set_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self._visible:
            return
        self._visible = visible
        if not visible:
            self.place_forget()
            self._masquer_infobulle()
        self._barre._layout()

    def set_texte(self, texte: str) -> None:
        self._infobulle = texte
        if self._tip is not None:
            self._tip.configure(text=texte)


class _BarreSaisieCapsule(tk.Frame):
    """Capsule de saisie unique : texte intégré, icônes et défilement."""

    def __init__(self, parent, on_change=None, on_return=None) -> None:
        super().__init__(parent, bg=theme.FOND, highlightthickness=0, bd=0)
        self._on_change = on_change
        self._on_return = on_return
        self._police = tkfont.Font(family=theme.POLICE, size=theme.TAILLE_CHAT)
        self._metrics = self._police.metrics()
        self._ligne = max(1, int(self._metrics["linespace"]))
        self._hauteur_base = max(56, self._ligne + 28)
        self._hauteur_cible = self._hauteur_base
        self._hauteur_actuelle = float(self._hauteur_base)
        self._hauteur_after = None
        self._fond_after = None
        self._focus_progression = 0.0
        self._focus_cible = 0.0
        self._survol_progression = 0.0
        self._survol_cible = 0.0
        self._focused = False
        self._survol = False
        self._scroll_visible = False
        self._lignes = 1
        self._boutons: list[_BoutonBarre] = []
        self._photo = None
        self.configure(height=self._hauteur_base, highlightthickness=0, bd=0)
        self.pack_propagate(False)
        self.fond = tk.Canvas(self, bg=theme.FOND, highlightthickness=0, bd=0)
        self.fond.pack(fill="both", expand=True)
        self.text = tk.Text(
            self, height=1, width=1, bg=theme.CAPSULE_FOND, fg=theme.CAPSULE_TEXTE,
            insertbackground=theme.ACCENT_CLAIR, selectbackground=theme.ACCENT,
            selectforeground=theme.FOND, wrap="word", bd=0, relief="flat",
            highlightthickness=0, font=self._police, padx=0, pady=0,
            spacing1=2, spacing3=2, undo=True, cursor="xterm")
        self.defilement = tk.Scrollbar(self, orient="vertical", command=self.text.yview,
                                       width=9, bd=0, relief="flat",
                                       bg=theme.CAPSULE_FOND, troughcolor=theme.CAPSULE_FOND,
                                       activebackground=theme.ACCENT,
                                       highlightthickness=0)
        self.text.configure(yscrollcommand=self.defilement.set)
        self.placeholder = tk.Label(self, text="Écris à JIBI…", bg=theme.CAPSULE_FOND,
                                     fg=theme.CAPSULE_AIDE,
                                     font=(theme.POLICE, theme.TAILLE_CHAT), anchor="w")
        self.placeholder.bind("<Button-1>", lambda _e: self.text.focus_set())
        self.text.bind("<<Modified>>", self._modifie)
        self.text.bind("<KeyRelease>", lambda _e: self._ajuster())
        self.text.bind("<ButtonRelease-1>", lambda _e: self._ajuster())
        self.text.bind("<Return>", self._retour)
        self.text.bind("<Shift-Return>", self._retour_ligne)
        self.text.bind("<FocusIn>", self._focus_in)
        self.text.bind("<FocusOut>", self._focus_out)
        self.fond.bind("<Button-1>", lambda _e: self.text.focus_set())
        self.fond.bind("<Enter>", self._survol_entrer)
        self.fond.bind("<Leave>", self._survol_sortir)
        self.bind("<Configure>", self._layout)
        self.fond.bind("<Configure>", self._layout)
        self.after_idle(self._layout)
        self.after(60, self._layout)

    def ajouter_bouton(self, nom: str, infobulle: str, commande) -> _BoutonBarre:
        bouton = _BoutonBarre(self, nom, infobulle, commande)
        self._boutons.append(bouton)
        self._layout()
        return bouton

    @staticmethod
    def _hex(couleur) -> str:
        return "#{:02x}{:02x}{:02x}".format(*couleur[:3])

    def _focus_in(self, _event=None) -> None:
        self._focused = True
        self._focus_cible = 1.0
        self._animer_fond()

    def _focus_out(self, _event=None) -> None:
        self._focused = False
        self._focus_cible = 0.0
        self._animer_fond()

    def _survol_entrer(self, _event=None) -> None:
        self._survol = True
        self._survol_cible = 1.0
        self._animer_fond()

    def _survol_sortir(self, _event=None) -> None:
        self._survol = False
        self._survol_cible = 0.0
        self._animer_fond()

    def _animer_fond(self) -> None:
        if self._fond_after is not None:
            try:
                self.after_cancel(self._fond_after)
            except Exception:
                pass
        depart_focus, depart_survol = self._focus_progression, self._survol_progression
        debut = time.monotonic()

        def pas(_=None):
            fraction = min(1.0, (time.monotonic() - debut) * 1000 / theme.TRANSITION_MS)
            self._focus_progression = depart_focus + (self._focus_cible - depart_focus) * fraction
            self._survol_progression = depart_survol + (self._survol_cible - depart_survol) * fraction
            self._rendre_fond()
            if fraction < 1:
                self._fond_after = self.after(20, pas)
            else:
                self._fond_after = None
                self._focus_progression = self._focus_cible
                self._survol_progression = self._survol_cible
                self._rendre_fond()

        self._fond_after = self.after(20, pas)

    def _rendre_fond(self) -> None:
        largeur = max(1, self.winfo_width())
        hauteur = max(1, int(round(self._hauteur_actuelle)))
        if largeur <= 3 or hauteur <= 3:
            return
        self.fond.delete("all")
        if _PIL_DISPONIBLE:
            echelle = 4
            image = Image.new("RGBA", (largeur * echelle, hauteur * echelle), (0, 0, 0, 0))
            dessin = ImageDraw.Draw(image)
            p = self._survol_progression
            f = self._focus_progression
            remplissage = self._hex(_melanger(theme.CAPSULE_FOND,
                                               theme.CAPSULE_FOND_SURVOL, p))
            rayon = theme.CAPSULE_RAYON * echelle
            if f > 0:
                dessin.rounded_rectangle(
                    (echelle, echelle, (largeur - 2) * echelle, (hauteur - 2) * echelle),
                    radius=rayon, outline=_rgba(theme.ACCENT, int(105 * f)), width=3 * echelle)
            dessin.rounded_rectangle(
                (3 * echelle, 3 * echelle, (largeur - 4) * echelle, (hauteur - 4) * echelle),
                radius=max(4, rayon - 2 * echelle), fill=_rgba(remplissage),
                outline=_rgba(theme.CAPSULE_BORD if f < .5 else theme.ACCENT),
                width=echelle)
            redimensionner = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            self._photo = ImageTk.PhotoImage(image.resize((largeur, hauteur), redimensionner))
            self.fond.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            # Repli sans dépendance : un seul polygone arrondi, sans cercles.
            points = _points_arrondis(1, 1, largeur - 2, hauteur - 2,
                                      theme.CAPSULE_RAYON, 8)
            couleur = self._hex(_melanger(theme.CAPSULE_FOND,
                                          theme.CAPSULE_FOND_SURVOL,
                                          self._survol_progression))
            self.fond.create_polygon(points, fill=couleur,
                                     outline=theme.ACCENT if self._focused else theme.CAPSULE_BORD,
                                     width=2 if self._focused else 1, smooth=True)
        for bouton in self._boutons:
            bouton.set_fond(couleur if not _PIL_DISPONIBLE else
                            self._hex(_melanger(theme.CAPSULE_FOND,
                                                theme.CAPSULE_FOND_SURVOL, p)),
                            anime=False)
        self.text.configure(bg=couleur if not _PIL_DISPONIBLE else
                            self._hex(_melanger(theme.CAPSULE_FOND,
                                                theme.CAPSULE_FOND_SURVOL, p)))
        self.placeholder.configure(bg=self.text.cget("bg"))
        self.defilement.configure(bg=self.text.cget("bg"), troughcolor=self.text.cget("bg"))

    def _layout(self, _event=None) -> None:
        if self.winfo_width() <= 1:
            return
        self._placer_enfants()
        self._rendre_fond()

    def _placer_enfants(self) -> None:
        largeur = max(1, self.winfo_width())
        hauteur = max(self._hauteur_base, int(round(self._hauteur_actuelle)))
        visibles = [b for b in self._boutons if b._visible]
        gap = 6
        marge_droite = 10
        x = largeur - marge_droite
        for bouton in reversed(visibles):
            x -= theme.BARRE_ICONE
            bouton.place(x=x, y=hauteur - 10 - theme.BARRE_ICONE,
                         width=theme.BARRE_ICONE, height=theme.BARRE_ICONE)
            x -= gap
        zone_boutons = max(105, x)
        if self._scroll_visible:
            self.defilement.place(x=zone_boutons - 17, y=13,
                                  width=9, height=max(1, hauteur - 26))
            largeur_texte = max(20, zone_boutons - 30)
        else:
            self.defilement.place_forget()
            largeur_texte = max(20, zone_boutons - 22)
        self.text.place(x=20, y=12, width=largeur_texte, height=max(1, hauteur - 24))
        if self.get().strip():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=20, y=14)

    def _compter_lignes_visuelles(self, contenu: str) -> int:
        if not contenu:
            return 1
        largeur = max(40, self.text.winfo_width() - 4)
        total = 0
        for paragraphe in contenu.split("\n"):
            if not paragraphe:
                total += 1
                continue
            courant = 0
            lignes = 1
            for mot in paragraphe.split():
                largeur_mot = self._police.measure(mot + " ")
                if courant and courant + largeur_mot > largeur:
                    lignes += 1
                    courant = largeur_mot
                else:
                    courant += largeur_mot
                if largeur_mot > largeur:
                    lignes += max(0, int((largeur_mot - 1) // largeur))
            total += lignes
        return max(1, total)

    def _animer_hauteur(self, lignes: int) -> None:
        cible = max(self._hauteur_base, self._ligne * max(1, lignes) + 28)
        if abs(cible - self._hauteur_cible) < 1:
            return
        if self._hauteur_after is not None:
            try:
                self.after_cancel(self._hauteur_after)
            except Exception:
                pass
        depart = self._hauteur_actuelle
        debut = time.monotonic()
        etapes = max(1, int(theme.TRANSITION_MS / 20))

        def pas(_=None):
            fraction = min(1.0, (time.monotonic() - debut) * 1000 / theme.TRANSITION_MS)
            self._hauteur_actuelle = depart + (cible - depart) * fraction
            self.configure(height=max(1, int(round(self._hauteur_actuelle))))
            self._placer_enfants()
            self._rendre_fond()
            if fraction < 1:
                self._hauteur_after = self.after(20, pas)
            else:
                self._hauteur_after = None
                self._hauteur_actuelle = float(cible)
                self._hauteur_cible = cible
                self.configure(height=cible)
                self._placer_enfants()

        self._hauteur_cible = cible
        self._hauteur_after = self.after(20, pas)

    def _ajuster(self) -> None:
        self.update_idletasks()
        contenu = self.get()
        cible = max(1, min(6, self._compter_lignes_visuelles(contenu)))
        if cible != self._lignes:
            self._lignes = cible
            self.text.configure(height=cible)
        self._scroll_visible = cible >= 6 and bool(contenu)
        self._animer_hauteur(cible)
        self._placer_enfants()
        if not contenu.strip():
            self.placeholder.place(x=20, y=14)
        else:
            self.placeholder.place_forget()
        if self._on_change:
            self._on_change(contenu)

    def _modifie(self, _event=None) -> None:
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self._ajuster()

    def _retour_ligne(self, _evenement=None) -> str:
        self.text.insert("insert", "\n")
        self._ajuster()
        return "break"

    def _retour(self, evenement) -> str:
        if int(evenement.state) & 0x0001:
            self.text.insert("insert", "\n")
            self._ajuster()
            return "break"
        if self._on_return:
            self._on_return(evenement)
        return "break"

    def get(self) -> str:
        return self.text.get("1.0", "end-1c")

    def delete(self, debut, fin=None) -> None:
        if debut == 0 and fin == "end":
            self.text.delete("1.0", "end")
            self._lignes = 1
            self._scroll_visible = False
            self.text.configure(height=1)
            self._animer_hauteur(1)
            self._placer_enfants()
            self.placeholder.place(x=20, y=14)
            if self._on_change:
                self._on_change("")
        else:
            if debut == 0:
                debut = "1.0"
            if fin is None:
                self.text.delete(debut)
            else:
                self.text.delete(debut, fin)

    def insert(self, index, valeur) -> None:
        if index == 0:
            index = "1.0"
        self.text.insert(index, _normaliser_texte(valeur))
        self._ajuster()

    def focus_set(self):
        return self.text.focus_set()

    def bind(self, sequence=None, command=None, add=None):
        return self.text.bind(sequence, command, add)


class _BoutonFleche(tk.Frame):
    """Bouton d'envoi carré arrondi, dessiné sans caractère Unicode."""

    def __init__(self, parent, commande, taille=52, icone="envoi"):
        super().__init__(parent, bg=theme.FOND, width=taille, height=taille)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._taille = taille
        self._icone = icone
        self._commande = commande
        self._actif = True
        self._survol = False
        self.canevas = tk.Canvas(self, width=taille, height=taille, bg=theme.FOND,
                                  highlightthickness=0, bd=0)
        self.canevas.pack(fill="both", expand=True)
        self.canevas.bind("<Button-1>", lambda _e: self._cliquer())
        self.canevas.bind("<Enter>", self._enter)
        self.canevas.bind("<Leave>", self._leave)
        self._dessiner()

    def _cliquer(self):
        if self._actif:
            self._commande()

    def _enter(self, _event=None):
        self._survol = True
        self._dessiner()

    def _leave(self, _event=None):
        self._survol = False
        self._dessiner()

    def _dessiner(self):
        c = self.canevas
        c.delete("all")
        n = self._taille
        rayon = 14
        fond = theme.ACCENT_CLAIR if self._survol and self._actif else theme.BOUTON_CLAIR
        if not self._actif:
            fond = theme.PANNEAU
        fleche = theme.FOND if self._actif else theme.GRIS
        c.create_oval(2, 2, 2 + rayon * 2, 2 + rayon * 2, fill=fond, outline=theme.CHAMP_BORD)
        c.create_oval(n - 2 - rayon * 2, 2, n - 2, 2 + rayon * 2, fill=fond, outline=theme.CHAMP_BORD)
        c.create_oval(2, n - 2 - rayon * 2, 2 + rayon * 2, n - 2, fill=fond, outline=theme.CHAMP_BORD)
        c.create_oval(n - 2 - rayon * 2, n - 2 - rayon * 2, n - 2, n - 2, fill=fond, outline=theme.CHAMP_BORD)
        c.create_rectangle(2 + rayon, 2, n - 2 - rayon, n - 2, fill=fond, outline="")
        x = n // 2
        if self._icone == "import":
            c.create_line(x, n - 19, x, 15, fill=fleche, width=3)
            c.create_polygon(x, 9, x - 8, 21, x + 8, 21, fill=fleche, outline="")
            c.create_line(x - 11, n - 11, x + 11, n - 11, fill=fleche, width=2)
        else:
            c.create_line(x, n - 13, x, 15, fill=fleche, width=3)
            c.create_polygon(x, 9, x - 8, 21, x + 8, 21, fill=fleche, outline="")
        c.configure(cursor="hand2" if self._actif else "arrow")

    def set_etat(self, etat: str):
        self._actif = etat != "disabled"
        self._dessiner()


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
        self._ecoute_en_cours = False   # évite deux écoutes simultanées

        # Doit précéder la création de toute fenêtre Tk pour éviter le
        # redimensionnement et le flou Windows à fort DPI.
        _activer_dpi_windows()
        self.root = tk.Tk()
        self.root.title("JIBI — assistant personnel")
        self.root.geometry("1280x800")
        self.root.configure(bg=theme.FOND)
        self.root.minsize(980, 650)
        try:
            base = tkfont.nametofont("TkDefaultFont")
            base.configure(size=theme.TAILLE_BASE, family=theme.POLICE)
            self.root.option_add("*Font", base)
        except Exception:
            pass

        self.file: queue.Queue = queue.Queue()
        self.var_voix = tk.BooleanVar(value=voix_on)
        self.occupe = False
        self.etat_orbe = "repos"
        self._flux_mark = False
        self._flux_dernier = ""
        self._t0 = time.time()
        self._rayon_actuel = theme.RAYON_ORBE
        self._rayon_cible = theme.RAYON_ORBE
        self._dernier_progression = 0.0
        self._nb_documents_connu = self._compter_documents()
        self._dernier_badge = 0.0
        self._badge_flash = 0.0
        self._lecteur_courant = None
        self._jeton_travail = 0
        self._document_chemins: list[Path] = []
        self._bibliotheque = None
        self._bib_pages: dict[str, tk.Frame] = {}
        self._bib_onglet = ""
        self._bib_session_ids: list[int] = []
        self._bib_doc_paths: list[Path] = []
        self._bib_doc_visibles: list[Path] = []
        self._sidebar_width = 260
        self._sidebar_collapsed = False
        self._zoom = 1.0
        self._zoom_base = float(self.root.tk.call("tk", "scaling"))
        self._sidebar_session_ids: list[int] = []
        self._sidebar_nav_widgets: dict[str, tk.Frame] = {}

        # Layout principal : barre latérale + zone de travail
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=0, minsize=self._sidebar_width)
        self.root.grid_columnconfigure(1, weight=0, minsize=6)
        self.root.grid_columnconfigure(2, weight=1)
        self.sidebar = tk.Frame(self.root, bg=theme.PANNEAU, width=self._sidebar_width,
                                highlightthickness=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._sidebar_resizer = tk.Frame(self.root, bg=theme.BORD, width=6,
                                         cursor="sb_h_double_arrow")
        self._sidebar_resizer.grid(row=0, column=1, sticky="ns")
        self._sidebar_resizer.bind("<Button-1>", self._resize_sidebar)
        self._sidebar_resizer.bind("<B1-Motion>", self._resize_sidebar)
        self.main_area = tk.Frame(self.root, bg=theme.FOND)
        self.main_area.grid(row=0, column=2, sticky="nsew")
        self.main_header = tk.Frame(self.main_area, bg=theme.FOND, height=42)
        self.main_header.pack(fill="x", padx=theme.ESPACEMENT_GRAND, pady=(8, 0))
        self.main_page_title = tk.Label(self.main_header, text="Assistant", bg=theme.FOND,
                                        fg=theme.TEXTE_PUR, font=(theme.POLICE, theme.TAILLE_BASE, "bold"))
        self.main_page_title.pack(side="left")
        self.statut = tk.Label(self.main_header, text="Initialisation", bg=theme.FOND,
                               fg=theme.GRIS, font=(theme.POLICE, theme.TAILLE_PETIT))
        self.statut.pack(side="left", padx=(12, 0))
        self.progression_texte = tk.Label(self.main_header, text="Prêt", bg=theme.FOND,
                                          fg=theme.GRIS, font=(theme.POLICE, theme.TAILLE_PETIT))
        self.progression_texte.pack(side="right")
        self.page_accueil = tk.Frame(self.main_area, bg=theme.FOND)
        self.page_accueil.pack(fill="both", expand=True)
        self.page_bibliotheque = tk.Frame(self.main_area, bg=theme.FOND)
        self.page_bibliotheque.pack_forget()
        self._construire_sidebar()

        # Orbe et conversation
        self.orbe = tk.Canvas(self.page_accueil, width=1100, height=300, bg=theme.FOND,
                              highlightthickness=0)
        self.orbe.pack(fill="x")
        # La boule reste le raccourci d'écoute principal ; le bouton Micro
        # dédié est également visible dans la barre de saisie.
        self.orbe.bind("<Button-1>", lambda _e: self.micro())
        self.etiquette_etat = tk.Label(self.page_accueil, text="Prêt — clique sur la boule pour parler",
                                       bg=theme.FOND, fg=theme.ACCENT_CLAIR,
                                       font=(theme.POLICE, theme.TAILLE_BASE, "bold"))
        self.etiquette_etat.pack(pady=(0, 2))
        self.hint = tk.Label(self.page_accueil, text="", bg=theme.FOND, fg=theme.GRIS,
                             font=(theme.POLICE, 1))
        self.hint.pack()

        cadre_chat = tk.Frame(self.page_accueil, bg=theme.FOND)
        self.chat = tk.Text(cadre_chat, bg=theme.FOND, fg=theme.TEXTE, wrap="word",
                            relief="flat", padx=22, pady=18, state="disabled",
                            cursor="arrow", spacing1=2, spacing3=14,
                            insertbackground=theme.ACCENT_CLAIR,
                            font=(theme.POLICE, theme.TAILLE_CHAT))
        ascenseur = tk.Scrollbar(cadre_chat, command=self.chat.yview,
                                 bg=theme.PANNEAU, troughcolor=theme.FOND,
                                 activebackground=theme.ACCENT, relief="flat", width=12)
        self.chat.configure(yscrollcommand=ascenseur.set)
        ascenseur.pack(side="right", fill="y")
        self.chat.pack(fill="both", expand=True)
        police_chat = (theme.POLICE, theme.TAILLE_CHAT)
        police_code = (theme.POLICE_CODE, theme.TAILLE_CODE)
        # Les marges des tags donnent aux messages utilisateur un alignement
        # et un fond légèrement différents, sans réduire la colonne de lecture.
        self.chat.tag_configure("jibi", foreground=theme.TEXTE,
                                background=theme.PANNEAU, font=police_chat,
                                lmargin1=24, lmargin2=24, rmargin=24,
                                spacing1=10, spacing3=14)
        self.chat.tag_configure("nom", foreground=theme.TEXTE_PUR,
                                background=theme.PANNEAU, font=(theme.POLICE, theme.TAILLE_BASE, "bold"),
                                lmargin1=24, lmargin2=24, rmargin=24,
                                spacing1=4, spacing3=2)
        self.chat.tag_configure("toi", foreground=theme.TEXTE,
                                background=theme.PANNEAU_CLAIR, font=police_chat,
                                lmargin1=80, lmargin2=80, rmargin=24,
                                spacing1=10, spacing3=14)
        self.chat.tag_configure("toi_nom", foreground=theme.TEXTE_PUR,
                                background=theme.PANNEAU_CLAIR,
                                font=(theme.POLICE, theme.TAILLE_BASE, "bold"),
                                lmargin1=80, lmargin2=80, rmargin=24,
                                spacing1=4, spacing3=2)
        self.chat.tag_configure("heure", foreground=theme.GRIS,
                                background=theme.PANNEAU,
                                font=(theme.POLICE, theme.TAILLE_PETIT),
                                lmargin1=24, lmargin2=24, rmargin=24,
                                spacing1=4, spacing3=2)
        self.chat.tag_configure("heure_toi", foreground=theme.GRIS,
                                background=theme.PANNEAU_CLAIR,
                                font=(theme.POLICE, theme.TAILLE_PETIT),
                                lmargin1=80, lmargin2=80, rmargin=24,
                                spacing1=4, spacing3=2)
        self.chat.tag_configure("action", foreground=theme.TEXTE_PUR,
                                background=theme.PANNEAU_CLAIR,
                                font=police_chat, lmargin1=28, lmargin2=28, rmargin=28,
                                spacing1=8, spacing3=8)
        self.chat.tag_configure("systeme", foreground=theme.TEXTE,
                                background=theme.CHAMP, font=police_code,
                                lmargin1=28, lmargin2=28, rmargin=28,
                                spacing1=10, spacing3=10)
        self.chat.tag_configure("systeme_entete", foreground=theme.TEXTE_PUR,
                                background=theme.CHAMP,
                                font=(theme.POLICE_CODE, theme.TAILLE_CODE, "bold"),
                                lmargin1=28, lmargin2=28, rmargin=28,
                                spacing1=4, spacing3=2)

        # La liste Documents est désormais un onglet de la bibliothèque intégrée.
        self.documents_frame = self.page_bibliotheque
        self.documents_list = None

        # Une seule capsule flottante au bas : texte intégré à gauche,
        # actions symboliques à droite. Aucune ligne de séparation.
        self._barre_saisie = _BarreSaisieCapsule(
            self.page_accueil, on_change=self._saisie_change, on_return=self._entree)
        self._barre_saisie.pack(side="bottom", fill="x",
                                padx=theme.BARRE_MARGE, pady=(4, theme.BARRE_MARGE))
        self.saisie_zone = self._barre_saisie
        self.saisie = self.saisie_zone
        self.voix_bouton = self._barre_saisie.ajouter_bouton(
            "voix", "Me parler", self._basculer_voix)
        self.case_voix = self.voix_bouton
        self.stop_bouton = self._barre_saisie.ajouter_bouton(
            "arrete", "Arrêter", self.stop_travail)
        self.stop_bouton.set_visible(False)
        self.dictee_bouton = self._barre_saisie.ajouter_bouton(
            "dictee", "Dicter", self.basculer_dictee)
        self.import_bouton = self._barre_saisie.ajouter_bouton(
            "trombone", "Importer un document ou une image", self._importer_fichiers)
        self.envoyer_bouton = self._barre_saisie.ajouter_bouton(
            "envoi", "Envoyer", self.envoyer)
        # Bouton de verrouillage/déverrouillage du noyau
        self.noyau_bouton = self._barre_saisie.ajouter_bouton(
            "verrou", "Verrouiller/Déverrouiller le noyau",
            self.basculer_verrou_noyau)
        self._maj_noyau_bouton()
        # Bouton gestionnaire de fichiers
        self.fichier_bouton = self._barre_saisie.ajouter_bouton(
            "bibliotheque", "Gestionnaire de fichiers",
            self.gestionnaire_fichiers)
        self._maj_fichier_bouton()
        # Bouton configuration déplacement
        self.deplacement_bouton = self._barre_saisie.ajouter_bouton(
            "check", "Confirmation déplacement",
            self.configurer_deplacement)
        self._maj_deplacement_bouton()
        self.en_dictee = False
        micro_disponible = ecoute.micro_disponible()
        if not micro_disponible:
            self.dictee_bouton.set_etat("disabled")
        self.var_voix.trace_add("write", self._voix_change)
        self._maj_voix_bouton()
        self.envoyer_bouton.set_etat("disabled")
        self._barre_saisie._layout()
        cadre_chat.pack(fill="both", expand=True, padx=theme.ESPACEMENT_GRAND, pady=(2, 0))

        # La pastille de téléchargement est masquée dans la conversation ;
        # les documents restent accessibles dans la navigation de gauche.
        self.badge = tk.Canvas(self.main_area, width=58, height=58, bg=theme.FOND,
                               highlightthickness=0, cursor="hand2")
        self.badge.bind("<Button-1>", lambda _e: self.ouvrir_documents())
        self.badge.bind("<Enter>", lambda _e: self.badge.configure(bg=theme.PANNEAU))
        self.badge.bind("<Leave>", lambda _e: self.badge.configure(bg=theme.FOND))
        self.badge.place_forget()
        self._dessiner_badge(False)

        self.ajouter_chat("jibi",
                          "Bonjour, je suis JIBI. Je tourne entièrement sur ton PC — "
                          "clique sur la boule pour me parler, ou écris ici. "
                          "Essaie : « quelle heure est-il », « regarde mon écran », "
                          "« crée une routine du matin à 8 h », « prends note que… ».")
        self._afficher_statut_ollama()
        self._actualiser_badge_documents()
        garde.confirmer = self.confirmer

    # ── barre latérale ──────────────────────────────────────────────
    def _set_sidebar_active(self, actif: str | None = None) -> None:
        for nom, widgets in getattr(self, "_sidebar_nav_widgets", {}).items():
            couleur = theme.PANNEAU_CLAIR if nom == actif else theme.PANNEAU
            widgets["frame"].configure(bg=couleur)
            widgets["canvas"].configure(bg=couleur)
            widgets["label"].configure(
                bg=couleur, fg=theme.TEXTE if nom == actif else theme.GRIS)

    def _sidebar_ligne(self, icone: str, libelle: str, commande, cle: str) -> None:
        cadre = tk.Frame(self.sidebar, bg=theme.PANNEAU, cursor="hand2", height=38)
        cadre.pack(fill="x", padx=10, pady=2)
        cadre.pack_propagate(False)
        canevas = tk.Canvas(cadre, width=24, height=24, bg=theme.PANNEAU,
                            highlightthickness=0)
        canevas.pack(side="left", padx=(9, 4), pady=5)
        _icone(canevas, icone, 12, 12, 9, theme.ACCENT_CLAIR)
        texte = tk.Label(cadre, text=libelle, bg=theme.PANNEAU, fg=theme.GRIS,
                         font=(theme.POLICE, theme.TAILLE_BASE), anchor="w")
        texte.pack(side="left", fill="x", expand=True, padx=(3, 8))
        widgets = {"frame": cadre, "canvas": canevas, "label": texte}
        self._sidebar_nav_widgets[cle] = widgets
        for widget in (cadre, canevas, texte):
            widget.bind("<Button-1>", lambda _e, c=commande: c())
            widget.bind("<Enter>", lambda _e, k=cle: self._set_sidebar_active(k))
            widget.bind("<Leave>", lambda _e: self._set_sidebar_active(getattr(self, "_sidebar_active", None)))

    def _construire_sidebar(self) -> None:
        for enfant in self.sidebar.winfo_children():
            enfant.destroy()
        entete = tk.Frame(self.sidebar, bg=theme.PANNEAU, height=58)
        entete.pack(fill="x", padx=14, pady=(10, 5))
        entete.pack_propagate(False)
        # Marque : pastille jade + nom, alignée avec l'orbe de l'accueil.
        pastille = tk.Canvas(entete, width=18, height=18, bg=theme.PANNEAU,
                             highlightthickness=0)
        pastille.pack(side="left")
        pastille.create_oval(1, 1, 17, 17, fill=theme.ACCENT, outline="")
        tk.Label(entete, text="  JIBI", bg=theme.PANNEAU, fg=theme.TEXTE_PUR,
                 font=(theme.POLICE, theme.TAILLE_TITRE, "bold")).pack(side="left")
        self._collapse_button = tk.Button(entete, text="Réduire", command=self._basculer_sidebar,
                                          bg=theme.PANNEAU, fg=theme.GRIS,
                                          activebackground=theme.PANNEAU_CLAIR,
                                          activeforeground=theme.TEXTE, relief="flat",
                                          bd=0, cursor="hand2", font=(theme.POLICE, theme.TAILLE_PETIT),
                                          padx=4, pady=4)
        self._collapse_button.pack(side="right")
        self._sidebar_toggle_main = tk.Button(self.main_header, text="Menu",
                                               command=self._basculer_sidebar,
                                               bg=theme.PANNEAU, fg=theme.TEXTE,
                                               activebackground=theme.ACCENT,
                                               activeforeground=theme.FOND, relief="flat",
                                               bd=0, cursor="hand2", font=(theme.POLICE, theme.TAILLE_PETIT),
                                               padx=10, pady=5)
        nouvelle = _BoutonIcone(self.sidebar, "plus", "Nouvelle session", self.nouvelle_session,
                                couleur=theme.ACCENT)
        nouvelle.pack(fill="x", padx=10, pady=(4, 12))
        tk.Label(self.sidebar, text="NAVIGATION", bg=theme.PANNEAU, fg=theme.GRIS,
                 font=(theme.POLICE, theme.TAILLE_PETIT, "bold"), anchor="w").pack(
                     fill="x", padx=16, pady=(0, 4))
        self._sidebar_nav_widgets = {}
        self._sidebar_ligne("bibliotheque", "Bibliothèque", lambda: self.ouvrir_bibliotheque("sessions"), "bibliotheque")
        self._sidebar_ligne("telechargement", "Documents", self.ouvrir_documents, "documents")
        self._sidebar_ligne("signal", "Signaux", self.afficher_signaux, "signaux")
        tk.Label(self.sidebar, text="SESSIONS RÉCENTES", bg=theme.PANNEAU, fg=theme.GRIS,
                 font=(theme.POLICE, theme.TAILLE_PETIT, "bold"), anchor="w").pack(
                     fill="x", padx=16, pady=(16, 4))
        self._sidebar_sessions = tk.Listbox(self.sidebar, bg=theme.PANNEAU, fg=theme.TEXTE,
                                            relief="flat", highlightthickness=0,
                                            selectbackground=theme.ACCENT, selectforeground=theme.FOND,
                                            font=(theme.POLICE, theme.TAILLE_PETIT), height=8)
        self._sidebar_sessions.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._sidebar_sessions.bind("<<ListboxSelect>>", self._sidebar_session_selection)
        self._sidebar_sessions.bind("<Double-Button-1>", self._sidebar_session_selection)
        self._sidebar_sessions.bind("<Button-3>", lambda e: self._popup_session("sidebar", e))
        self._sidebar_sessions.bind("<Delete>", lambda _e: (self._supprimer_session(
            self._session_selectionnee_sidebar(), sidebar_si_absent=False), "break")[1])
        tk.Button(self.sidebar, text="Supprimer la session",
                  command=lambda: self._supprimer_session(
                      self._session_selectionnee_sidebar(), sidebar_si_absent=False),
                  bg=theme.PANNEAU, fg=theme.ROUGE, activebackground=theme.ROUGE,
                  activeforeground=theme.FOND, relief="flat", cursor="hand2", bd=0,
                  font=(theme.POLICE, theme.TAILLE_PETIT), padx=8, pady=5).pack(
                      fill="x", padx=10, pady=(0, 8))
        zoom = tk.Frame(self.sidebar, bg=theme.PANNEAU, height=42)
        zoom.pack(fill="x", side="bottom", padx=10, pady=(4, 10))
        zoom.pack_propagate(False)
        tk.Label(zoom, text="Zoom", bg=theme.PANNEAU, fg=theme.GRIS,
                 font=(theme.POLICE, theme.TAILLE_PETIT)).pack(side="left", padx=5)
        self._zoom_label = tk.Label(zoom, text="100 %", bg=theme.PANNEAU, fg=theme.TEXTE,
                                    font=(theme.POLICE, theme.TAILLE_PETIT, "bold"))
        self._zoom_label.pack(side="left", padx=(0, 7))
        tk.Button(zoom, text="−", command=lambda: self._ajuster_zoom(-1), bg=theme.PANNEAU,
                  fg=theme.TEXTE, relief="flat", bd=0, cursor="hand2",
                  font=(theme.POLICE, theme.TAILLE_BASE)).pack(side="right", padx=2)
        tk.Button(zoom, text="+", command=lambda: self._ajuster_zoom(1), bg=theme.PANNEAU,
                  fg=theme.TEXTE, relief="flat", bd=0, cursor="hand2",
                  font=(theme.POLICE, theme.TAILLE_BASE)).pack(side="right", padx=2)
        self._rafraichir_sidebar_sessions()

    def _rafraichir_sidebar_sessions(self) -> None:
        if not hasattr(self, "_sidebar_sessions"):
            return
        self._sidebar_sessions.delete(0, "end")
        self._sidebar_session_ids.clear()
        try:
            sessions = self.assistant.memoire.lister_sessions(8)
        except Exception:
            sessions = []
        for sid, titre, nombre in sessions:
            self._sidebar_session_ids.append(int(sid))
            self._sidebar_sessions.insert("end", f"{str(titre)[:32]}{'…' if len(str(titre)) > 32 else ''}")

    def _sidebar_session_selection(self, _event=None) -> None:
        selection = self._sidebar_sessions.curselection()
        if not selection or selection[0] >= len(self._sidebar_session_ids):
            return
        self._reprendre(self._sidebar_session_ids[selection[0]])
        self._retour_accueil()
        self._rafraichir_sidebar_sessions()

    def _basculer_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        if self._sidebar_collapsed:
            self.sidebar.grid_remove()
            self._sidebar_resizer.grid_remove()
            self.root.grid_columnconfigure(0, weight=0, minsize=0)
            self.root.grid_columnconfigure(1, weight=0, minsize=0)
            self._sidebar_toggle_main.pack(side="left", padx=(0, 8), before=self.main_page_title)
        else:
            self.root.grid_columnconfigure(0, weight=0, minsize=self._sidebar_width)
            self.root.grid_columnconfigure(1, weight=0, minsize=6)
            self.sidebar.grid(row=0, column=0, sticky="nsew")
            self._sidebar_resizer.grid(row=0, column=1, sticky="ns")
            self._sidebar_toggle_main.pack_forget()

    def _resize_sidebar(self, evenement) -> None:
        if self._sidebar_collapsed:
            return
        largeur = max(210, min(430, int(evenement.x_root - self.root.winfo_rootx())))
        self._sidebar_width = largeur
        self.sidebar.configure(width=largeur)
        self.root.grid_columnconfigure(0, weight=0, minsize=largeur)

    def _ajuster_zoom(self, direction: int) -> None:
        self._zoom = max(0.8, min(1.25, round(self._zoom + direction * 0.1, 2)))
        self.root.tk.call("tk", "scaling", self._zoom_base * self._zoom)
        if hasattr(self, "_zoom_label"):
            self._zoom_label.config(text=f"{round(self._zoom * 100)} %")

    def _retour_accueil(self) -> None:
        if hasattr(self, "page_bibliotheque"):
            self.page_bibliotheque.pack_forget()
            self.page_accueil.pack(fill="both", expand=True)
            self.main_page_title.config(text="Assistant")
        self._set_sidebar_active(None)

    # ── statut Ollama ───────────────────────────────────────────────
    def _afficher_statut_ollama(self) -> None:
        from jibi2.llm import ClientLLM
        client = ClientLLM()
        ok, _, _version = client.etat(force=True)
        if ok:
            present = client.modele_present()
            self.statut.config(
                text=(f"Prêt — {client.modele}" if present else
                      f"Modèle absent — {client.modele}"),
                fg=theme.GRIS if present else theme.ORANGE)
        else:
            self.statut.config(text="Ollama éteint", fg=theme.ROUGE)

    def _actualiser_progression(self) -> None:
        if time.time() - self._dernier_progression < 0.8:
            return
        self._dernier_progression = time.time()
        try:
            from jibi2 import progression
            etat = progression.lire()
            valeur = max(0, min(100, int(etat.get("pourcent", 0))))
            self.progression_texte.config(
                text=f"{valeur} % — {etat.get('titre', 'Prêt')}",
                fg=theme.ACCENT_CLAIR if etat.get("actif") else theme.GRIS)
        except Exception:
            self.progression_texte.config(text="Prêt", fg=theme.GRIS)

    def _compter_documents(self) -> int:
        try:
            from jibi2 import config
            return sum(1 for chemin in config.DOSSIER_FICHIERS.rglob("*")
                       if chemin.is_file() and chemin.suffix.lower() in
                       (".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv", ".json",
                        ".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))
        except Exception:
            return 0

    def _dessiner_badge(self, nouveau: bool) -> None:
        self.badge.delete("all")
        couleur = theme.VERT if nouveau or time.time() < self._badge_flash else theme.ACCENT
        centre = 29
        rayon = 24 + (2 if time.time() < self._badge_flash else 0)
        self.badge.create_oval(centre - rayon, centre - rayon, centre + rayon, centre + rayon,
                               fill=theme.PANNEAU_CLAIR, outline=couleur, width=2)
        _icone(self.badge, "telechargement", centre, 24, 18, couleur)
        self.badge.create_text(centre, 44, text=str(self._nb_documents_connu),
                               fill=theme.TEXTE, font=(theme.POLICE, theme.TAILLE_PETIT, "bold"))

    def _positionner_badge(self, _event=None) -> None:
        # La pastille de téléchargement est volontairement masquée dans la
        # conversation ; les documents restent accessibles dans la barre laterale.
        if hasattr(self, "badge"):
            self.badge.place_forget()

    def _actualiser_badge_documents(self) -> None:
        if time.time() - self._dernier_badge < 1.0:
            return
        self._dernier_badge = time.time()
        nombre = self._compter_documents()
        nouveau = nombre > self._nb_documents_connu
        if nouveau:
            self._badge_flash = time.time() + 1.5
            if (hasattr(self, "page_bibliotheque")
                    and self.page_bibliotheque.winfo_ismapped()
                    and hasattr(self, "_bib_doc_list")):
                self._bib_rafraichir_documents()
        self._nb_documents_connu = nombre
        self._dessiner_badge(nouveau)

    def _basculer_voix(self) -> None:
        """Bascule simplement la parole : cochée = parle, décochée = muet."""
        self.var_voix.set(not bool(self.var_voix.get()))

    def _maj_voix_bouton(self) -> None:
        if not hasattr(self, "voix_bouton"):
            return
        actif = bool(self.var_voix.get())
        if self.etat_orbe == "parole" and actif:
            self.voix_bouton.set_actif(True)
        else:
            self.voix_bouton.set_actif(actif)
        self.voix_bouton.set_texte("Me parler — désactiver" if actif
                                       else "Me parler — activer")

    def basculer_verrou_noyau(self) -> None:
        """Basculer le verrouillage du noyau (confirmation requise)."""
        try:
            from jibi2 import config as _config
            ancien = _config.valeur_bool("JIBI_AUTONOMIE_NOYAU")
            nouvelle = _config.basculer_noyau()
            self._maj_noyau_bouton()
            if nouvelle == "0":
                self.ajouter_chat("jibi",
                                  "[VERROUILLÉ] Noyau verrouillé — toute modification du code demande une confirmation.")
            else:
                self.ajouter_chat("jibi",
                                  "[DÉVERROUILLÉ] Noyau déverrouillé — les modifications du code sont autorisées (avec confirmation à chaque fois).")
        except Exception as e:
            self.ajouter_chat("jibi",
                              f"Erreur lors de la bascule du noyau : {e}")

    def _maj_noyau_bouton(self) -> None:
        if not hasattr(self, "noyau_bouton"):
            return
        try:
            from jibi2 import config as _config
            deverrouille = _config.valeur_bool("JIBI_AUTONOMIE_NOYAU")
            self.noyau_bouton.set_texte(
                "[DÉVERROUILLÉ] Noyau DÉVERROUILLÉ" if deverrouille
                else "[VERROUILLÉ] Noyau VERROUILLÉ")
        except Exception:
            pass

    def gestionnaire_fichiers(self) -> None:
        """Affiche le gestionnaire de fichiers."""
        try:
            from outils.fichiers import gestionnaire_fichiers
            texte = gestionnaire_fichiers("lister")
            self.ajouter_chat("jibi", texte)
        except Exception as e:
            self.ajouter_chat("jibi",
                              "Erreur gestionnaire de fichiers : " + str(e))

    def _maj_fichier_bouton(self) -> None:
        if not hasattr(self, "fichier_bouton"):
            return
        self.fichier_bouton.set_texte("[FICHIERS] Gestionnaire")

    def configurer_deplacement(self) -> None:
        """Bascule la confirmation des déplacements de fichiers (0 ↔ 1)."""
        try:
            from jibi2 import config as _config
            nouvelle = _config.basculer_deplacement()
            self._maj_deplacement_bouton()
            if nouvelle == "0":
                self.ajouter_chat("jibi",
                                  "[AUTO] Déplacement/copie sans confirmation activé.")
            else:
                self.ajouter_chat("jibi",
                                  "[CONFIRMATION] Chaque déplacement/copie demandera ton accord.")
        except Exception as e:
            self.ajouter_chat("jibi",
                              "Erreur configuration déplacement : " + str(e))

    def _maj_deplacement_bouton(self) -> None:
        if not hasattr(self, "deplacement_bouton"):
            return
        try:
            from jibi2 import config as _c
            confirmation = _c.valeur_bool("CONFIRMER_DEPLACEMENT")
            self.deplacement_bouton.set_texte(
                "[CONFIRMATION] Déplacement" if confirmation
                else "[AUTO] Déplacement sans confirmation")
        except Exception:
            pass

    def _voix_change(self, *_args) -> None:
        if not self.var_voix.get():
            self._arreter_voix()
        self._maj_voix_bouton()
        self._maj_bouton_envoi()

    def _arreter_voix(self) -> None:
        lecteur = self._lecteur_courant
        self._lecteur_courant = None
        if lecteur is not None:
            try:
                lecteur.couper()
            except Exception:
                pass
        if self.voix_module is not None:
            try:
                arreter = getattr(self.voix_module, "arreter", None)
                if callable(arreter):
                    arreter()
            except Exception:
                pass

    def _documents_workspace(self) -> list[Path]:
        from outils.fichiers import _racine
        try:
            return sorted((p for p in _racine().rglob("*") if p.is_file()),
                          key=lambda p: p.stat().st_mtime if p.exists() else 0,
                          reverse=True)[:100]
        except OSError:
            return []

    def _rafraichir_documents(self) -> None:
        self._document_chemins = self._documents_workspace()
        if hasattr(self, "_bib_doc_list"):
            self._bib_rafraichir_documents()

    def afficher_documents(self) -> None:
        self.ouvrir_bibliotheque("documents")

    def masquer_documents(self) -> None:
        self._retour_accueil()

    def _importer_fichiers(self) -> None:
        """Ouvre le sélecteur Windows pour importer documents et images."""
        chemins = filedialog.askopenfilenames(
            title="Importer des documents ou images dans JIBI",
            filetypes=[("Documents et images", "*.pdf *.docx *.xlsx *.csv *.txt *.md *.json *.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                       ("Tous les fichiers", "*.*")])
        if not chemins:
            return
        from outils import importer_fichier
        resultats = []
        for chemin in chemins:
            try:
                resultats.append(importer_fichier(str(chemin)))
            except Exception as exc:  # noqa: BLE001
                resultats.append(str(exc))
        self._bib_rafraichir_documents()
        self.ajouter_chat("jibi", "\n".join(resultats))

    def _ouvrir_dossier_documents(self) -> None:
        from outils.fichiers import _racine
        dossier = _racine()
        dossier.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(dossier))  # noqa: S606 - ouverture par l'utilisateur
            else:
                webbrowser.open(dossier.as_uri())
        except Exception as e:
            self.ajouter_chat("jibi", f"Impossible d'ouvrir le dossier des documents : {e}")

    def _ouvrir_document_selectionne(self) -> None:
        if hasattr(self, "_bib_doc_list"):
            self._bib_ouvrir_document()

    def ouvrir_documents(self) -> None:
        """Ouvre l'onglet Documents de la bibliothèque unifiée."""
        self.ouvrir_bibliotheque("documents")

    def _fermer_bibliotheque(self) -> None:
        self._bibliotheque = None
        if hasattr(self, "page_bibliotheque"):
            self.page_bibliotheque.pack_forget()
            self.page_accueil.pack(fill="both", expand=True)
            self.main_page_title.config(text="Assistant")
        self._set_sidebar_active(None)

    def _bib_actualiser_stats(self) -> None:
        if not hasattr(self, "_bib_stats"):
            return
        try:
            sessions = len(self.assistant.memoire.lister_sessions(500))
            notes = len(self.assistant.memoire.lister_notes(500))
        except Exception:
            sessions = notes = 0
        documents = len(self._documents_workspace())
        self._bib_stats.config(text=f"{sessions} session(s)  ·  {documents} document(s)  ·  {notes} note(s)")

    def _bib_afficher_onglet(self, nom: str) -> None:
        if nom not in self._bib_pages:
            nom = "sessions"
        for page in self._bib_pages.values():
            page.pack_forget()
        self._bib_pages[nom].pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._bib_onglet = nom
        for nom_bouton, bouton in getattr(self, "_bib_nav_buttons", {}).items():
            actif = nom_bouton == nom
            bouton.configure(bg=theme.ACCENT if actif else theme.PANNEAU,
                             fg=theme.FOND if actif else theme.GRIS)
        if nom == "sessions":
            self._bib_rafraichir_sessions()
        else:
            self._bib_rafraichir_documents()

    def _bib_rafraichir_sessions(self) -> None:
        if not hasattr(self, "_bib_session_list"):
            return
        self._bib_session_list.delete(0, "end")
        self._bib_session_ids.clear()
        try:
            sessions = self.assistant.memoire.lister_sessions(200)
        except Exception:
            sessions = []
        for sid, titre, nombre in sessions:
            self._bib_session_ids.append(int(sid))
            self._bib_session_list.insert("end", f"#{sid}  ·  {titre}  ({nombre} message(s))")
        self._bib_detail.config(state="normal")
        self._bib_detail.delete("1.0", "end")
        self._bib_detail.insert("end", "Sélectionne une session pour voir ses messages.")
        self._bib_detail.config(state="disabled")
        self._bib_actualiser_stats()

    def _bib_afficher_session(self, _event=None) -> None:
        if not hasattr(self, "_bib_session_list"):
            return
        selection = self._bib_session_list.curselection()
        if not selection or selection[0] >= len(self._bib_session_ids):
            return
        sid = self._bib_session_ids[selection[0]]
        try:
            messages = self.assistant.memoire.messages_de(sid)
        except Exception as e:
            messages = [("jibi", f"Session illisible : {e}")]
        self._bib_detail.config(state="normal")
        self._bib_detail.delete("1.0", "end")
        self._bib_detail.insert("end", f"Session #{sid}\n")
        self._bib_detail.insert("end", "=" * 36 + "\n\n")
        for role, contenu in messages[-100:]:
            nom = "Vous" if role == "utilisateur" else "JIBI"
            self._bib_detail.insert("end", f"{nom}\n", "role_jibi" if role == "jibi" else "role_user")
            self._bib_detail.insert("end", str(contenu)[:4000] + "\n\n")
        self._bib_detail.config(state="disabled")

    def _bib_ouvrir_session(self) -> None:
        if not getattr(self, "_bib_session_ids", None):
            return
        selection = self._bib_session_list.curselection()
        if not selection or selection[0] >= len(self._bib_session_ids):
            return
        self._reprendre(self._bib_session_ids[selection[0]])
        self._fermer_bibliotheque()

    def _bib_supprimer_session(self) -> None:
        session_id = self._session_selectionnee_bibliotheque()
        if session_id is not None:
            self._supprimer_session(session_id, sidebar_si_absent=False)

    def _bib_exporter_session(self) -> None:
        if not getattr(self, "_bib_session_ids", None):
            return
        selection = self._bib_session_list.curselection()
        if not selection or selection[0] >= len(self._bib_session_ids):
            return
        sid = self._bib_session_ids[selection[0]]
        try:
            messages = [{"role": role, "contenu": contenu}
                        for role, contenu in self.assistant.memoire.messages_de(sid)]
            from outils.fichiers import _chemin_espace
            chemin = _chemin_espace(f"session_{sid}.json")
            chemin.write_text(json.dumps({"session": sid, "messages": messages},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
            self._bib_actualiser_stats()
            messagebox.showinfo("Session exportée", f"Fichier créé :\n{chemin.name}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Export impossible", str(e)[:220])

    def _session_selectionnee_bibliotheque(self) -> int | None:
        if not hasattr(self, "_bib_session_list"):
            return None
        selection = self._bib_session_list.curselection()
        if not selection or selection[0] >= len(self._bib_session_ids):
            return None
        return self._bib_session_ids[selection[0]]

    def _session_selectionnee_sidebar(self) -> int | None:
        if not hasattr(self, "_sidebar_sessions"):
            return None
        selection = self._sidebar_sessions.curselection()
        if not selection or selection[0] >= len(self._sidebar_session_ids):
            return None
        return self._sidebar_session_ids[selection[0]]

    def _rafraichir_sessions_ui(self) -> None:
        self._rafraichir_sidebar_sessions()
        if hasattr(self, "_bib_session_list"):
            self._bib_rafraichir_sessions()

    def _supprimer_session(self, session_id: int | None = None, *,
                           sidebar_si_absent: bool = True) -> bool:
        """Demande confirmation puis supprime une session et son historique."""
        if session_id is None and sidebar_si_absent:
            session_id = self._session_selectionnee_bibliotheque()
        if session_id is None and sidebar_si_absent:
            session_id = self._session_selectionnee_sidebar()
        if session_id is None:
            return False
        if self.occupe:
            messagebox.showwarning(
                "Suppression impossible",
                "Attends la fin de la réponse en cours avant de supprimer une session.",
                parent=self.root)
            return False
        try:
            session_id = int(session_id)
            sessions = self.assistant.memoire.lister_sessions(500)
            info = next(((sid, titre) for sid, titre, _ in sessions
                         if int(sid) == session_id), None)
            courant = self.assistant.memoire.session_id
            etait_courante = (courant is not None and int(courant) == session_id)
        except (TypeError, ValueError, AttributeError):
            self._rafraichir_sessions_ui()
            messagebox.showerror("Suppression impossible", "Cette session n'existe plus.",
                                 parent=self.root)
            return False
        except Exception as exc:  # noqa: BLE001 — une erreur ne doit pas casser la fenêtre
            self._rafraichir_sessions_ui()
            messagebox.showerror("Suppression impossible", str(exc)[:220], parent=self.root)
            return False
        if info is None:
            self._rafraichir_sessions_ui()
            messagebox.showinfo("Suppression annulée", "Cette session a déjà été supprimée.",
                                parent=self.root)
            return False
        titre = str(info[1])
        precision = ("\n\nC'est la session active : une nouvelle session vide sera créée."
                     if etait_courante else "")
        if not messagebox.askyesno(
                "Supprimer la session",
                f"Supprimer définitivement la session #{session_id} ?\n\n"
                f"{titre}\n\nTous les messages de cette session seront perdus.{precision}",
                icon="warning", default=messagebox.NO, parent=self.root):
            return False
        if etait_courante:
            self._arreter_voix()
        try:
            supprimee = self.assistant.supprimer_session(session_id)
        except Exception as exc:  # noqa: BLE001 — une erreur ne doit pas casser la fenêtre
            self._rafraichir_sessions_ui()
            messagebox.showerror("Suppression impossible", str(exc)[:220], parent=self.root)
            return False
        if not supprimee:
            self._rafraichir_sessions_ui()
            messagebox.showinfo("Suppression annulée", "Cette session a déjà été supprimée.",
                                parent=self.root)
            return False
        if etait_courante:
            try:
                nouveau_id = self.assistant.nouvelle_session()
            except Exception as exc:  # noqa: BLE001
                self.chat.config(state="normal")
                self.chat.delete("1.0", "end")
                self.chat.config(state="disabled")
                self._rafraichir_sessions_ui()
                messagebox.showerror("Nouvelle session impossible", str(exc)[:220],
                                     parent=self.root)
                return False
            self.chat.config(state="normal")
            self.chat.delete("1.0", "end")
            self.chat.config(state="disabled")
            self.ajouter_chat("jibi", f"Session #{session_id} supprimée. "
                                      f"Nouvelle session #{nouveau_id}.")
            self._etat("repos")
        else:
            self.ajouter_chat("jibi", f"Session #{session_id} supprimée.")
        self._rafraichir_sessions_ui()
        self._maj_bouton_envoi()
        return True

    def _popup_session(self, source: str, event) -> str:
        """Menu contextuel discret pour les sessions récentes et Bibliothèque."""
        if source == "bibliotheque":
            widget = getattr(self, "_bib_session_list", None)
            identifiants = getattr(self, "_bib_session_ids", [])
        else:
            widget = getattr(self, "_sidebar_sessions", None)
            identifiants = getattr(self, "_sidebar_session_ids", [])
        if widget is None:
            return "break"
        try:
            if event.y < 0 or event.y > widget.winfo_height():
                return "break"
            index = int(widget.nearest(event.y))
            if index < 0 or index >= len(identifiants):
                return "break"
            widget.selection_clear(0, "end")
            widget.selection_set(index)
            widget.activate(index)
            sid = int(identifiants[index])
        except (tk.TclError, TypeError, ValueError):
            return "break"
        menu = tk.Menu(self.root, tearoff=False, bg=theme.PANNEAU,
                       fg=theme.TEXTE, activebackground=theme.ACCENT,
                       activeforeground=theme.FOND, font=(theme.POLICE, theme.TAILLE_BASE))
        menu.add_command(label="Ouvrir la session", command=lambda: self._ouvrir_session_id(sid))
        menu.add_command(label="Supprimer la session", command=lambda: self._supprimer_session(sid))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _ouvrir_session_id(self, session_id: int) -> None:
        self._reprendre(session_id)
        self._retour_accueil()
        self._rafraichir_sidebar_sessions()

    def _bib_rafraichir_documents(self) -> None:
        if not hasattr(self, "_bib_doc_list"):
            return
        self._bib_doc_list.delete(0, "end")
        self._bib_doc_paths = self._documents_workspace()
        self._bib_doc_visibles = []
        filtre = self._bib_doc_search.get().strip().lower()
        visibles = 0
        for chemin in self._bib_doc_paths:
            if filtre and filtre not in chemin.name.lower():
                continue
            try:
                stat = chemin.stat()
                poids = (f"{stat.st_size / 1024:.0f} Ko" if stat.st_size < 1024 * 1024
                         else f"{stat.st_size / 1024 / 1024:.1f} Mo")
                modifie = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
                self._bib_doc_list.insert("end", f"{chemin.name}  ·  {poids}  ·  {modifie}")
                self._bib_doc_visibles.append(chemin)
                visibles += 1
            except OSError:
                continue
        if not visibles:
            self._bib_doc_list.insert("end", "Aucun document trouvé")
        self._bib_actualiser_stats()

    def _bib_filtrer_documents(self, _event=None) -> None:
        self._bib_rafraichir_documents()

    def _bib_ouvrir_document(self) -> None:
        selection = self._bib_doc_list.curselection()
        if not selection:
            return
        # La liste affichée ne contient que les chemins visibles après filtrage.
        index = selection[0]
        if index >= len(getattr(self, "_bib_doc_visibles", [])):
            return
        chemin = self._bib_doc_visibles[index]
        try:
            if os.name == "nt":
                os.startfile(str(chemin))  # noqa: S606 - ouverture par l'utilisateur
            else:
                webbrowser.open(chemin.as_uri())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Document impossible", str(e)[:220])

    def _bib_bouton(self, parent, texte: str, commande, principal: bool = False,
                    danger: bool = False) -> tk.Button:
        """Bouton harmonisé de la bibliothèque (un seul style partout)."""
        if principal:
            couleurs = (theme.ACCENT, theme.FOND, theme.ACCENT_CLAIR)
        elif danger:
            couleurs = (theme.PANNEAU_CLAIR, theme.ROUGE, theme.ROUGE)
        else:
            couleurs = (theme.PANNEAU_CLAIR, theme.TEXTE, theme.ACCENT)
        return tk.Button(parent, text=texte, command=commande,
                         bg=couleurs[0], fg=couleurs[1],
                         activebackground=couleurs[2],
                         activeforeground=theme.FOND, relief="flat",
                         cursor="hand2", bd=0,
                         font=(theme.POLICE, theme.TAILLE_BASE), padx=12, pady=6)

    def _bib_entete_page(self, parent, titre: str) -> tk.Frame:
        """Bandeau titre + Actualiser, commun aux deux pages."""
        barre = tk.Frame(parent, bg=theme.FOND)
        barre.pack(fill="x", pady=(0, 10))
        tk.Label(barre, text=titre, bg=theme.FOND, fg=theme.TEXTE_PUR,
                 font=(theme.POLICE, theme.TAILLE_TITRE, "bold")).pack(side="left")
        return barre

    def _construire_bibliotheque_sessions(self, parent: tk.Frame) -> None:
        page = tk.Frame(parent, bg=theme.FOND)
        barre = self._bib_entete_page(page, "Sessions passées")
        tk.Button(barre, text="Actualiser", command=self._bib_rafraichir_sessions,
                  bg=theme.PANNEAU, fg=theme.TEXTE, relief="flat", cursor="hand2", bd=0,
                  font=(theme.POLICE, theme.TAILLE_PETIT), padx=10, pady=5).pack(side="right")
        corps = tk.Frame(page, bg=theme.FOND)
        corps.pack(fill="both", expand=True)
        gauche = tk.Frame(corps, bg=theme.PANNEAU, width=340)
        gauche.pack(side="left", fill="y")
        gauche.pack_propagate(False)
        self._bib_session_list = tk.Listbox(gauche, bg=theme.PANNEAU, fg=theme.TEXTE,
                                            relief="flat", selectbackground=theme.ACCENT,
                                            selectforeground=theme.FOND, highlightthickness=0,
                                            font=(theme.POLICE, theme.TAILLE_BASE), activestyle="none")
        self._bib_session_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._bib_session_list.bind("<<ListboxSelect>>", self._bib_afficher_session)
        self._bib_session_list.bind("<Double-Button-1>", lambda _e: self._bib_ouvrir_session())
        self._bib_session_list.bind("<Button-3>", lambda e: self._popup_session("bibliotheque", e))
        self._bib_session_list.bind("<Delete>", lambda _e: (self._bib_supprimer_session(), "break")[1])
        droite = tk.Frame(corps, bg=theme.PANNEAU)
        droite.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self._bib_detail = tk.Text(droite, bg=theme.FOND, fg=theme.TEXTE, wrap="word",
                                   relief="flat", padx=14, pady=12, state="disabled",
                                   font=(theme.POLICE, theme.TAILLE_BASE), spacing1=5, spacing3=7)
        self._bib_detail.pack(fill="both", expand=True)
        self._bib_detail.tag_configure("role_user", foreground=theme.BLEU,
                                       font=(theme.POLICE, theme.TAILLE_BASE, "bold"))
        self._bib_detail.tag_configure("role_jibi", foreground=theme.ACCENT_CLAIR,
                                       font=(theme.POLICE, theme.TAILLE_BASE, "bold"))
        actions = tk.Frame(droite, bg=theme.PANNEAU)
        actions.pack(fill="x", pady=(8, 0))
        self._bib_bouton(actions, "Ouvrir la session", self._bib_ouvrir_session,
                         principal=True).pack(side="left")
        self._bib_bouton(actions, "Exporter", self._bib_exporter_session).pack(
            side="left", padx=(8, 0))
        self._bib_bouton(actions, "Supprimer", self._bib_supprimer_session,
                         danger=True).pack(side="left", padx=(8, 0))
        self._bib_pages["sessions"] = page

    def _construire_bibliotheque_documents(self, parent: tk.Frame) -> None:
        page = tk.Frame(parent, bg=theme.FOND)
        barre = self._bib_entete_page(page, "Tous les documents")
        self._bib_doc_search = tk.StringVar()
        recherche = tk.Entry(barre, textvariable=self._bib_doc_search, width=26,
                             bg=theme.PANNEAU, fg=theme.TEXTE, relief="flat",
                             insertbackground=theme.ACCENT_CLAIR,
                             font=(theme.POLICE, theme.TAILLE_BASE))
        recherche.pack(side="right", padx=(8, 0))
        recherche.bind("<KeyRelease>", self._bib_filtrer_documents)
        tk.Button(barre, text="Actualiser", command=self._bib_rafraichir_documents,
                  bg=theme.PANNEAU, fg=theme.TEXTE, relief="flat", cursor="hand2", bd=0,
                  font=(theme.POLICE, theme.TAILLE_PETIT), padx=10, pady=5).pack(side="right")
        self._bib_doc_list = tk.Listbox(page, bg=theme.PANNEAU, fg=theme.TEXTE, relief="flat",
                                       selectbackground=theme.ACCENT, selectforeground=theme.FOND,
                                       highlightthickness=0, font=(theme.POLICE, theme.TAILLE_BASE),
                                       activestyle="none")
        self._bib_doc_list.pack(fill="both", expand=True)
        self._bib_doc_list.bind("<Double-Button-1>", lambda _e: self._bib_ouvrir_document())
        self._bib_doc_list.bind("<Button-3>", lambda e: self._popup_document(e))
        actions = tk.Frame(page, bg=theme.FOND)
        actions.pack(fill="x", pady=(10, 0))
        self._bib_bouton(actions, "Importer document / image", self._importer_fichiers,
                         principal=True).pack(side="left")
        self._bib_bouton(actions, "Ouvrir", self._bib_ouvrir_document).pack(
            side="left", padx=(8, 0))
        self._bib_bouton(actions, "Ouvrir le dossier", self._ouvrir_dossier_documents).pack(
            side="left", padx=(8, 0))
        self._bib_bouton(actions, "Supprimer (corbeille)", self._supprimer_document_selectionne,
                         danger=True).pack(side="left", padx=(8, 0))
        self._bib_pages["documents"] = page

    def _supprimer_document_selectionne(self) -> None:
        """Déplace le document sélectionné vers la corbeille JIBI (récupérable)."""
        selection = self._bib_doc_list.curselection()
        if not selection or selection[0] >= len(getattr(self, "_bib_doc_visibles", [])):
            return
        chemin = self._bib_doc_visibles[selection[0]]
        if not messagebox.askyesno("Supprimer le document",
                                   f"Déplacer « {chemin.name} » vers la corbeille JIBI ?",
                                   parent=self.root):
            return
        try:
            corbeille = Path(__import__("jibi2.config", fromlist=["DOSSIER_CORBEILLE"]).DOSSIER_CORBEILLE)
            corbeille.mkdir(parents=True, exist_ok=True)
            destination = corbeille / f"{chemin.name}.{int(time.time())}"
            import shutil
            shutil.move(str(chemin), str(destination))
            self._bib_rafraichir_documents()
            self.ajouter_chat("jibi", f"« {chemin.name} » déplacé vers la corbeille (récupérable).")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Suppression impossible", str(e)[:220], parent=self.root)

    def _popup_document(self, event) -> str:
        """Menu contextuel de la liste des documents."""
        widget = getattr(self, "_bib_doc_list", None)
        if widget is None:
            return "break"
        try:
            if event.y < 0 or event.y > widget.winfo_height():
                return "break"
            index = int(widget.nearest(event.y))
            if index < 0 or index >= len(getattr(self, "_bib_doc_visibles", [])):
                return "break"
            widget.selection_clear(0, "end")
            widget.selection_set(index)
            widget.activate(index)
        except (tk.TclError, TypeError, ValueError):
            return "break"
        menu = tk.Menu(self.root, tearoff=False, bg=theme.PANNEAU,
                       fg=theme.TEXTE, activebackground=theme.ACCENT,
                       activeforeground=theme.FOND, font=(theme.POLICE, theme.TAILLE_BASE))
        menu.add_command(label="Ouvrir", command=self._bib_ouvrir_document)
        menu.add_command(label="Supprimer (corbeille)",
                         command=self._supprimer_document_selectionne)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def ouvrir_bibliotheque(self, onglet: str = "sessions") -> None:
        """Affiche la bibliothèque dans la zone principale, sans popup."""
        if not self._bib_pages:
            entete = tk.Frame(self.page_bibliotheque, bg=theme.FOND)
            entete.pack(fill="x", padx=18, pady=(10, 2))
            tk.Label(entete, text="Bibliothèque", bg=theme.FOND, fg=theme.TEXTE_PUR,
                     font=(theme.POLICE, theme.TAILLE_TITRE, "bold")).pack(side="left")
            self._bib_stats = tk.Label(entete, text="", bg=theme.FOND, fg=theme.GRIS,
                                        font=(theme.POLICE, theme.TAILLE_PETIT))
            self._bib_stats.pack(side="right")
            # Onglets segmentés : une seule rangée, l'onglet actif en jade.
            navigation = tk.Frame(self.page_bibliotheque, bg=theme.FOND)
            navigation.pack(fill="x", padx=18, pady=(2, 8))
            cadre_onglets = tk.Frame(navigation, bg=theme.PANNEAU)
            cadre_onglets.pack(side="left")
            self._bib_nav_buttons = {}
            for nom, libelle in (("sessions", "  Sessions  "), ("documents", "  Documents  ")):
                bouton = tk.Button(
                    cadre_onglets, text=libelle,
                    command=lambda n=nom: self._bib_afficher_onglet(n),
                    bg=theme.PANNEAU, fg=theme.GRIS, activebackground=theme.ACCENT,
                    activeforeground=theme.FOND, relief="flat", cursor="hand2", bd=0,
                    font=(theme.POLICE, theme.TAILLE_BASE, "bold"), padx=14, pady=7)
                bouton.pack(side="left")
                self._bib_nav_buttons[nom] = bouton
            contenu = tk.Frame(self.page_bibliotheque, bg=theme.FOND)
            contenu.pack(fill="both", expand=True)
            self._construire_bibliotheque_sessions(contenu)
            self._construire_bibliotheque_documents(contenu)
        self.page_accueil.pack_forget()
        self.page_bibliotheque.pack(fill="both", expand=True)
        self._bibliotheque = self.page_bibliotheque
        self.main_page_title.config(text="Bibliothèque")
        self._set_sidebar_active("bibliotheque" if onglet == "sessions" else "documents")
        self._bib_afficher_onglet(onglet)

    def afficher_signaux(self) -> None:
        if self.occupe:
            return
        self._retour_accueil()
        self._set_sidebar_active("signaux")
        self.occupe = True
        self.stop_bouton.set_etat("normal")
        self.stop_bouton.set_visible(True)
        self._etat("reflexion")

        def travail() -> None:
            try:
                from outils import signaux
                self.file.put(("signaux", signaux.tableau_signaux()))
            except Exception as e:
                self.file.put(("signaux", f"Signaux indisponibles : {e}"))

        threading.Thread(target=travail, daemon=True).start()

    # ── la boule ────────────────────────────────────────────────────
    def _dessiner_lumiere_bas(self) -> None:
        if not hasattr(self, "lumiere_bas"):
            return
        self.lumiere_bas.delete("all")
        largeur = max(1, self.lumiere_bas.winfo_width())
        hauteur = max(1, self.lumiere_bas.winfo_height())
        if self.etat_orbe == "parole":
            cible = (5, 6, 13)
        elif self.etat_orbe == "ecoute":
            cible = (18, 45, 75)
        else:
            cible = (18, 22, 40)
        bandes = 14
        for i in range(bandes):
            portion = i / max(1, bandes - 1)
            r = int(theme.FOND_RGB[0] + (cible[0] - theme.FOND_RGB[0]) * portion)
            g = int(theme.FOND_RGB[1] + (cible[1] - theme.FOND_RGB[1]) * portion)
            b = int(theme.FOND_RGB[2] + (cible[2] - theme.FOND_RGB[2]) * portion)
            y0 = hauteur * i / bandes
            y1 = hauteur * (i + 1) / bandes + 1
            self.lumiere_bas.create_rectangle(0, y0, largeur, y1,
                                              fill=f"#{r:02x}{g:02x}{b:02x}", outline="")

    def _animer(self) -> None:
        t = time.time() - self._t0
        halo, coeur = COULEURS[self.etat_orbe]
        self._rayon_cible = theme.RAYON_ORBE * (theme.FACTEUR_ORBE_PAROLE
                                                  if self.etat_orbe == "parole" else 1.0)
        self._rayon_actuel += (self._rayon_cible - self._rayon_actuel) * theme.LISSAGE_ORBE
        respiration = 1.0 + 0.035 * math.sin(t * RYTHME[self.etat_orbe])
        rayon = self._rayon_actuel * respiration
        largeur = max(1, self.orbe.winfo_width())
        centre_x, centre_y = largeur / 2, 145
        self.orbe.delete("all")
        # Deux couches seulement : halo doux + cœur. Aucun anneau concentrique.
        self.orbe.create_oval(centre_x - rayon * 1.20, centre_y - rayon * 1.20,
                              centre_x + rayon * 1.20, centre_y + rayon * 1.20,
                              fill=halo, width=0, stipple="gray50", tags="tout")
        self.orbe.create_oval(centre_x - rayon, centre_y - rayon,
                              centre_x + rayon, centre_y + rayon,
                              fill=coeur, width=0, tags="tout")
        # Ondes concentriques : visibilité du niveau sonore de la voix.
        # - parole  : 3 ondes régulières (JIBI est en train de parler)
        # - ecoute  : 2 ondes lentes (il capte ta voix)
        if self.etat_orbe in ("parole", "ecoute"):
            nombre = 3 if self.etat_orbe == "parole" else 2
            vitesse = 2.2 if self.etat_orbe == "parole" else 1.1
            for i in range(nombre):
                phase = (t * vitesse + i / nombre) % 1.0
                rayon_onde = rayon * (1.05 + phase * 0.85)
                # L'onde s'estompe en s'éloignant : Tk n'a que 3 trames,
                # on choisit la plus proche de l'opacité voulue.
                stipple = "gray75" if phase < 0.33 else ("gray50" if phase < 0.66 else "gray25")
                self.orbe.create_oval(
                    centre_x - rayon_onde, centre_y - rayon_onde,
                    centre_x + rayon_onde, centre_y + rayon_onde,
                    outline=coeur, width=2, stipple=stipple, tags="onde")
        self._actualiser_progression()
        self._actualiser_badge_documents()
        if time.time() < self._badge_flash:
            self._dessiner_badge(False)
        self.root.after(40, self._animer)

    LIBELLES = {"repos": "Prêt — clique sur la boule pour parler",
                "ecoute": "Je t'écoute",
                "reflexion": "Je réfléchis",
                "parole": "Je réponds"}

    def _etat(self, nom: str) -> None:
        if nom in COULEURS:
            self.etat_orbe = nom
            couleur = theme.ACCENT_CLAIR if nom == "repos" else COULEURS[nom][1]
            self.etiquette_etat.config(text=self.LIBELLES[nom], fg=couleur)
            self._maj_voix_bouton()
            if hasattr(self, "stop_bouton"):
                if nom in ("reflexion", "parole"):
                    self.stop_bouton.set_visible(True)
                elif nom == "repos" and not self.occupe:
                    self.stop_bouton.set_visible(False)

    # ── affichage conversation ──────────────────────────────────────
    def ajouter_chat(self, qui: str, texte: str) -> None:
        self.chat.config(state="normal")
        texte = _normaliser_texte(texte)
        horodatage = time.strftime("%H:%M")
        if qui == "toi":
            self.chat.insert("end", f"toi  {horodatage}\n", ("heure_toi",))
            self.chat.insert("end", texte + "\n\n", ("toi",))
        elif _est_sortie_systeme(texte):
            # Les listings de processus et autres sorties console restent
            # alignés et lisibles grâce à la police à chasse fixe.
            self.chat.insert("end", f"JIBI  {horodatage}\n", ("systeme_entete",))
            self.chat.insert("end", texte + "\n\n", ("systeme",))
        else:
            self.chat.insert("end", f"JIBI  {horodatage}\n", ("nom",))
            self.chat.insert("end", texte + "\n\n", ("jibi",))
        self.chat.see("end")
        self.chat.config(state="disabled")

    def ajouter_action(self, texte: str, ok: bool) -> None:
        self.chat.config(state="normal")
        libelle = "Action terminée" if ok else "Action impossible"
        self.chat.insert("end", f"{libelle} : {_normaliser_texte(texte)}\n", ("action",))
        self.chat.see("end")
        self.chat.config(state="disabled")

    def _flux_ajouter(self, morceau: str) -> None:
        propre = _texte_sans_boucle(_normaliser_texte(morceau))
        if not propre:
            return
        self._flux_dernier = propre
        self.chat.config(state="normal")
        if not self._flux_mark:
            self.chat.insert("end", "\n")
            self.chat.mark_set("flux_start", "end-1c")
            self.chat.mark_gravity("flux_start", "left")
            self._flux_mark = True
        self.chat.insert("end", _normaliser_texte(morceau), ("jibi",))
        self.chat.see("end")
        self.chat.config(state="disabled")

    # ── actions ─────────────────────────────────────────────────────
    def _saisie_change(self, texte: str) -> None:
        """Active le bouton d'envoi uniquement quand du texte est présent."""
        if not hasattr(self, "envoyer_bouton"):
            return
        self._maj_bouton_envoi(texte)

    def _maj_bouton_envoi(self, texte: str | None = None) -> None:
        if not hasattr(self, "envoyer_bouton"):
            return
        if texte is None and hasattr(self, "saisie"):
            texte = self.saisie.get()
        actif = (not bool(getattr(self, "occupe", False))
                 and bool(str(texte or "").strip()))
        self.envoyer_bouton.set_etat("normal" if actif else "disabled")

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
        self._jeton_travail += 1
        jeton = self._jeton_travail
        self.occupe = True
        # Signale l'activité : les modes autonomes « seuls » attendent le silence.
        try:
            from jibi2 import exploration
            exploration.noter_activite()
        except Exception:
            pass
        try:
            from jibi2 import autonomie as _autonomie
            _autonomie.noter_activite()
        except Exception:
            pass
        self._etat("reflexion")
        self.envoyer_bouton.set_etat("disabled")
        self.stop_bouton.set_etat("normal")
        self.stop_bouton.set_visible(True)
        voix = bool(self.var_voix.get()) and self.voix_module is not None
        threading.Thread(target=self._travail, args=(texte, voix, jeton), daemon=True).start()

    def stop_travail(self) -> None:
        if (not self.occupe and self._lecteur_courant is None
                and self.etat_orbe != "parole"):
            return
        self._jeton_travail += 1
        self._arreter_voix()
        if self.occupe:
            self.ajouter_chat("jibi", "Traitement arrêté. Tu peux me redemander.")
        self.occupe = False
        self.stop_bouton.set_visible(False)
        self._maj_bouton_envoi()
        self._etat("repos")

    def _travail(self, texte: str, voix: bool = False, jeton: int = 0) -> None:
        lecteur = None
        recu: list[str] = []
        if voix and self.flux_actif:
            lecteur = self.voix_module.LecteurPhrases(
                sur_debut=lambda: self.file.put(("etat", "parole")))
            self._lecteur_courant = lecteur
        sur_delta = None
        if self.flux_actif:
            def sur_delta(morceau: str) -> None:
                if jeton != self._jeton_travail:
                    return
                self.file.put(("flux", morceau))
                recu.append(morceau)
                if lecteur is not None and self.var_voix.get():
                    lecteur.alimenter(morceau)
        try:
            reponse = self.assistant.repondre(texte, on_chunk=sur_delta)
        except Exception as e:  # noqa: BLE001
            reponse = {"reponse": f"Erreur interne : {e}", "actions": [], "ok": False}
        if isinstance(reponse.get("reponse"), str):
            reponse["reponse"] = _texte_sans_boucle(reponse["reponse"])
        if jeton != self._jeton_travail:
            if lecteur is not None:
                try:
                    lecteur.couper()
                except Exception:
                    pass
            return
        identique = True
        if lecteur is not None:
            if self.var_voix.get():
                lecteur.terminer()
            else:
                lecteur.couper()
            identique = "".join(recu).strip() == reponse["reponse"]
            threading.Thread(target=lambda: (lecteur.attendre(), self.file.put(("etat", "repos"))),
                             daemon=True).start()
        self.file.put(("reponse", (reponse, lecteur, identique, jeton)))

    def micro(self) -> None:
        """Écoute une phrase via la boule, sans bouton Micro dédié."""
        if self.occupe or self._ecoute_en_cours:
            return
        self._ecoute_en_cours = True
        self._etat("ecoute")

        def travail() -> None:
            try:
                entendu = self.ecoute.ecouter_phrase()
            except Exception:
                entendu = ""
            self.file.put(("micro", entendu))

        threading.Thread(target=travail, daemon=True).start()

    def nouvelle_session(self) -> None:
        self.stop_travail()
        self._retour_accueil()
        sid = self.assistant.nouvelle_session()
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.insert("end", f"Nouvelle session #{sid}\n\n", ("heure",))
        self.chat.config(state="disabled")
        self.ajouter_chat("jibi", "On repart d'une conversation propre. Que veux-tu faire ?")

    def confirmer(self, nom_outil: str, detail: str) -> bool:
        evenement = threading.Event()
        conteneur = {"ok": False}
        self.file.put(("confirm", nom_outil, detail, evenement, conteneur))
        return evenement.wait(timeout=180) and bool(conteneur["ok"])

    def basculer_dictee(self) -> None:
        if self.en_dictee:
            self.file.put(("dictee_fin", ""))
            return
        if self.occupe:
            return
        self.en_dictee = True
        self.dictee_bouton.set_texte("Terminer la dictée")
        self.dictee_bouton.set_actif(True)
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
        self.dictee_bouton.set_texte("Dicter")
        self.dictee_bouton.set_actif(False)
        if texte:
            self._traite_dictee(texte)
            self.envoyer()

    def choisir_session(self) -> None:
        """Ouvre la bibliothèque sur l'onglet des sessions."""
        self.ouvrir_bibliotheque("sessions")

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
        self.ajouter_chat("jibi", message + " — on continue.")

    def _parler(self, texte: str) -> None:
        texte = _texte_sans_boucle(texte)
        if not texte:
            return
        self.file.put(("etat", "parole"))
        if self.voix_module:
            self.voix_module.parler(texte)
        self.file.put(("etat", "repos"))

    def _resume_action(self, action: dict) -> str:
        if not action.get("ok"):
            return "l'opération n'a pas abouti"
        outil = str(action.get("outil", ""))
        if outil == "copier_document":
            return "le fichier a été copié vers le dossier demandé"
        if outil == "deplacer_document":
            return "le fichier a été déplacé vers le dossier demandé"
        if outil == "ouvrir_application":
            return "le document a été ouvert"
        if "document" in outil or "pdf" in outil or "word" in outil or "excel" in outil:
            return "le document est prêt dans le panneau Documents"
        if "image" in outil or "photo" in outil or "visuel" in outil:
            return "les images et leurs sources sont disponibles"
        if "visiter" in outil or "chrome" in outil or "onglet" in outil:
            return "la page demandée est ouverte"
        if "recherche" in outil or "web" in outil:
            return "la recherche et ses sources sont disponibles"
        if "analyse" in outil:
            return "l'analyse est terminée"
        return "l'action est terminée"

    def _traite_signaux(self, texte: str) -> None:
        self.ajouter_chat("jibi", texte)
        self.occupe = False
        self._etat("repos")

    def _traite_etat(self, nom: str) -> None:
        self._etat(nom)

    def _traite_flux(self, morceau: str) -> None:
        if self.occupe:
            self._flux_ajouter(morceau)

    def _traite_reponse(self, paquet) -> None:
        reponse, lecteur, identique, jeton = paquet
        if jeton != self._jeton_travail:
            if lecteur is not None:
                try:
                    lecteur.couper()
                except Exception:
                    pass
            return
        if self._flux_mark:
            self.chat.config(state="normal")
            self.chat.delete("flux_start", "end-1c")
            self.chat.config(state="disabled")
            self._flux_mark = False
        self._flux_dernier = ""
        for action in reponse.get("actions", []):
            self.ajouter_action(self._resume_action(action), action.get("ok", False))
        self.ajouter_chat("jibi", reponse["reponse"])
        self.occupe = False
        self._maj_bouton_envoi()
        if lecteur is not None and identique:
            self._lecteur_courant = None
            return
        if lecteur is not None:
            lecteur.couper()
        self._lecteur_courant = None
        if self.var_voix.get() and self.voix_module:
            threading.Thread(target=self._parler, args=(reponse["reponse"],), daemon=True).start()
        else:
            self._etat("repos")

    def _traite_micro(self, entendu: str) -> None:
        self._ecoute_en_cours = False
        if entendu:
            self.ajouter_chat("toi", entendu)
            self._lancer_travail(entendu)
            return
        if self.ecoute.ERREUR_DERNIERE:
            self.ajouter_chat("jibi", "(micro : " + self.ecoute.ERREUR_DERNIERE + ")")
        self._etat("repos")

    def _traite_confirm(self, nom_outil: str, detail: str, evenement, conteneur) -> None:
        conteneur["ok"] = messagebox.askyesno(
            "JIBI — action sensible",
            f"JIBI demande ton autorisation :\n\n{detail}\n\nAutoriser ?")
        evenement.set()

    def _diffuser_annonces(self) -> None:
        if self.annonces is None:
            return
        try:
            while True:
                message = self.annonces.get_nowait()
                for ancien, nouveau in ((chr(0x23F0), "Routine —"),
                                         (chr(0x1F9E0), "Autonomie —"),
                                         (chr(0x1F4E1), "Signaux —")):
                    message = message.replace(ancien, nouveau)
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

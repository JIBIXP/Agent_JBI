"""Mémoire de JIBI 2 — une base SQLite locale, aucun serveur requis.

Trois tables : sessions/messages (conversations), notes (pense-bête),
faits (ce que JIBI retient durablement sur toi).
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import config


def _maintenant() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Memoire:
    def __init__(self, chemin: Path | None = None) -> None:
        self.chemin = Path(chemin) if chemin else config.FICHIER_BD
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.verrou = threading.Lock()
        self.bd = sqlite3.connect(self.chemin, check_same_thread=False)
        self.bd.execute("PRAGMA journal_mode=WAL")
        self._creer_tables()
        self.session_id: int | None = None

    # ------------------------------------------------------------------ base
    def _creer_tables(self) -> None:
        with self.verrou, self.bd:
            self.bd.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titre TEXT NOT NULL DEFAULT '',
                    debut TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    contenu TEXT NOT NULL,
                    horodatage TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texte TEXT NOT NULL,
                    horodatage TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS faits (
                    cle TEXT PRIMARY KEY,
                    valeur TEXT NOT NULL,
                    horodatage TEXT NOT NULL
                );
                """
            )

    # -------------------------------------------------------------- sessions
    def nouvelle_session(self, titre: str = "") -> int:
        with self.verrou, self.bd:
            cur = self.bd.execute(
                "INSERT INTO sessions (titre, debut) VALUES (?, ?)", (titre, _maintenant())
            )
            self.session_id = int(cur.lastrowid)
            return self.session_id

    def session_courante(self) -> int:
        if self.session_id is None:
            return self.nouvelle_session()
        return self.session_id

    def ajouter_message(self, role: str, contenu: str) -> None:
        sid = self.session_courante()
        with self.verrou, self.bd:
            self.bd.execute(
                "INSERT INTO messages (session_id, role, contenu, horodatage) VALUES (?, ?, ?, ?)",
                (sid, role, contenu, _maintenant()),
            )
            if role == "utilisateur":
                n = self.bd.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'utilisateur'",
                    (sid,),
                ).fetchone()[0]
                if n == 1:
                    self.bd.execute(
                        "UPDATE sessions SET titre = ? WHERE id = ?",
                        (contenu[:60], sid),
                    )

    def lister_sessions(self, nombre: int = 15) -> list[tuple[int, str, str]]:
        with self.verrou:
            return self.bd.execute(
                "SELECT s.id, COALESCE(NULLIF(s.titre, ''), '(sans titre)'), "
                "       (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) "
                "FROM sessions s ORDER BY s.id DESC LIMIT ?",
                (nombre,),
            ).fetchall()

    def messages_de(self, session_id: int) -> list[tuple[str, str]]:
        with self.verrou:
            return self.bd.execute(
                "SELECT role, contenu FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

    def charger_session(self, session_id: int) -> list[tuple[str, str]] | None:
        """Devient la session courante et renvoie ses messages (ou None)."""
        with self.verrou:
            existe = self.bd.execute("SELECT 1 FROM sessions WHERE id = ?",
                                     (session_id,)).fetchone()
        if not existe:
            return None
        messages = self.messages_de(session_id)
        self.session_id = int(session_id)
        return messages

    # ----------------------------------------------------------------- notes
    def ajouter_note(self, texte: str) -> int:
        with self.verrou, self.bd:
            cur = self.bd.execute(
                "INSERT INTO notes (texte, horodatage) VALUES (?, ?)", (texte, _maintenant())
            )
            return int(cur.lastrowid)

    def lister_notes(self, nombre: int = 10) -> list[tuple[int, str, str]]:
        with self.verrou:
            return self.bd.execute(
                "SELECT id, texte, horodatage FROM notes ORDER BY id DESC LIMIT ?", (nombre,)
            ).fetchall()

    def chercher_notes(self, mot: str) -> list[tuple[int, str, str]]:
        with self.verrou:
            return self.bd.execute(
                "SELECT id, texte, horodatage FROM notes "
                "WHERE texte LIKE ? ORDER BY id DESC LIMIT 20",
                (f"%{mot}%",),
            ).fetchall()

    def supprimer_note(self, numero: int) -> bool:
        with self.verrou, self.bd:
            cur = self.bd.execute("DELETE FROM notes WHERE id = ?", (numero,))
            return cur.rowcount > 0

    # ----------------------------------------------------------------- faits
    def retenir(self, cle: str, valeur: str) -> None:
        with self.verrou, self.bd:
            self.bd.execute(
                "INSERT INTO faits (cle, valeur, horodatage) VALUES (?, ?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur, "
                "horodatage = excluded.horodatage",
                (cle.lower(), valeur, _maintenant()),
            )

    def rappeler(self, mot: str = "") -> list[tuple[str, str]]:
        if mot:
            motif = f"%{mot}%"
            req = ("SELECT cle, valeur FROM faits WHERE cle LIKE ? OR valeur LIKE ? "
                   "ORDER BY horodatage DESC LIMIT 10")
            params: tuple = (motif, motif)
        else:
            req = "SELECT cle, valeur FROM faits ORDER BY horodatage DESC LIMIT 10"
            params = ()
        with self.verrou:
            return self.bd.execute(req, params).fetchall()

    def fermer(self) -> None:
        with self.verrou:
            self.bd.close()

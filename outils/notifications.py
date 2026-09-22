"""Notifications système de JIBI 2 — Windows 10/11 (toasts) + replis.

Sous Windows : notification native dans le centre de notifications via
les toasts PowerShell (aucun paquet à installer). Ailleurs : notification
de terminal. Utilisée par les rappels, les routines programmées et
l'outil notifier.
"""
from __future__ import annotations

import sys

from outils import outil

derniere: list[str] = []


def notifier_systeme(titre: str, message: str) -> bool:
    """Envoie une notification OS. Renvoie True si un canal a fonctionné."""
    titre = titre.replace('"', "'").replace("\n", " ")[:80]
    message = message.replace('"', "'").replace("\n", " ")[:200]
    if sys.platform == "win32":
        try:
            import subprocess
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, "
                "Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n"
                "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
                "ContentType = WindowsRuntime] | Out-Null\n"
                f"$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
                "$xml.LoadXml(\"<toast><visual><binding template='ToastText02'>"
                f"<text id='1'>{titre}</text>"
                f"<text id='2'>{message}</text></binding></visual></toast>\")\n"
                "$toast = New-Object Windows.UI.Notifications.ToastNotification $xml\n"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JIBI').Show($toast)"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, timeout=15)
            return True
        except Exception:
            return False
    print(f"\r🔔 {titre} — {message}")
    return False


@outil("notifier",
       "Affiche une NOTIFICATION Windows (comme une alerte système) avec ton message. "
       "À utiliser pour prévenir l'utilisateur d'une fin de tâche, d'un rappel important…",
       {"titre": {"type": "str", "obligatoire": True, "description": "titre court de la notification"},
        "message": {"type": "str", "obligatoire": True, "description": "le contenu de la notification"}},
       categorie="systeme",
       exemple='{"outil": "notifier", "parametres": {"titre": "JIBI", "message": "C\'est l\'heure de la pause !"}}')
def notifier(titre: str, message: str) -> str:
    ok = notifier_systeme(titre, message)
    derniere[:] = [titre, message]
    return ("Notification envoyée." if ok
            else "Notification affichée dans le terminal (canal système indisponible).")

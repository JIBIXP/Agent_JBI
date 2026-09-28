package com.focusguard.app

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.view.accessibility.AccessibilityEvent

/**
 * Détecte le changement de fenêtre au niveau système.
 * Si la fenêtre au premier plan appartient à une app bloquée et qu'une
 * session est active, on affiche l'écran de blocage par-dessus.
 * AUCUN contenu de fenêtre n'est lu (canRetrieveWindowContent=false).
 */
class FocusAccessibilityService : AccessibilityService() {

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null || event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        if (pkg == "com.focusguard.app" || pkg == "com.android.systemui") return

        val context = applicationContext
        if (!BlockStateStore.isActive(context)) return
        if (pkg !in BlockStateStore.blockedPackages(context)) return

        val intent = Intent(this, BlockActivity::class.java).apply {
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or
                    Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
            )
            putExtra("package", pkg)
        }
        startActivity(intent)
    }

    override fun onInterrupt() {
        // Rien à faire.
    }
}

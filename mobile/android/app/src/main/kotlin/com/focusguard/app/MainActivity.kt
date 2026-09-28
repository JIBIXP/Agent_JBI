package com.focusguard.app

import android.app.AlertDialog
import android.app.AppOpsManager
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.provider.Settings
import android.widget.Toast
import com.focusguard.app.widget.FocusWidgetProvider
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channelName = "focusguard/native"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "startBlocking" -> {
                        val packages = call.argument<List<String>>("packages") ?: emptyList()
                        val endsAtMs = call.argument<Long>("endsAtMs") ?: 0L
                        val strict = call.argument<Boolean>("strict") ?: false
                        BlockStateStore.setBlocking(this, packages, endsAtMs, strict)
                        val minutes = ((endsAtMs - System.currentTimeMillis()) / 60000).toInt()
                        SessionAlarm.schedule(this, endsAtMs, minutes)
                        FocusWidgetProvider.refresh(this)
                        result.success(true)
                    }
                    "stopBlocking" -> {
                        SessionAlarm.cancel(this)
                        BlockStateStore.clear(this)
                        FocusWidgetProvider.refresh(this)
                        result.success(true)
                    }
                    "hasBlockingPermission" -> {
                        result.success(hasUsageAccess() && hasAccessibilityEnabled())
                    }
                    "requestBlockingPermission" -> {
                        if (!hasUsageAccess()) {
                            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
                        } else if (!hasAccessibilityEnabled()) {
                            Toast.makeText(
                                this,
                                "Active FocusGuard dans Accessibilité",
                                Toast.LENGTH_LONG,
                            ).show()
                            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                        }
                        result.success(true)
                    }
                    "openAppPicker" -> {
                        // Android : le catalogue d'apps est géré côté Dart.
                        result.success(emptyList<String>())
                    }
                    "showFrictionDialog" -> showFrictionDialog(result)
                    "updateWidget" -> {
                        FocusWidgetProvider.refresh(this)
                        result.success(true)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /** Friction « urgence » : 10 secondes obligatoires avant de pouvoir confirmer. */
    private fun showFrictionDialog(result: MethodChannel.Result) {
        val handler = Handler(Looper.getMainLooper())
        val dialog = AlertDialog.Builder(this)
            .setTitle("Respire un coup 😮‍💨")
            .setMessage("Respire… 10")
            .setCancelable(false)
            .setNegativeButton("Non, je continue") { d, _ ->
                handler.removeCallbacksAndMessages(null)
                d.dismiss()
                result.success(false)
            }
            .setPositiveButton("Arrêter la session") { d, _ ->
                handler.removeCallbacksAndMessages(null)
                d.dismiss()
                result.success(true)
            }
            .create()

        dialog.show()
        // Le bouton OK est verrouillé pendant les 10 premières secondes.
        dialog.getButton(AlertDialog.BUTTON_POSITIVE)?.isEnabled = false

        var secondsLeft = 10
        val tick = object : Runnable {
            override fun run() {
                secondsLeft--
                if (secondsLeft > 0) {
                    dialog.setMessage("Respire… $secondsLeft")
                    handler.postDelayed(this, 1000)
                } else {
                    dialog.setMessage("Tu peux arrêter si tu en as vraiment besoin.")
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE)?.isEnabled = true
                }
            }
        }
        handler.postDelayed(tick, 1000)
    }

    private fun hasUsageAccess(): Boolean = try {
        val manager = getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        manager.checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            packageName,
        ) == AppOpsManager.MODE_ALLOWED
    } catch (e: Exception) {
        false
    }

    private fun hasAccessibilityEnabled(): Boolean {
        val expected = "$packageName/${FocusAccessibilityService::class.java.canonicalName}"
        val enabled = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ) ?: return false
        val parts = if (enabled.contains(":")) enabled.split(":") else enabled.split(" ")
        return parts.any { it.equals(expected, ignoreCase = true) }
    }
}

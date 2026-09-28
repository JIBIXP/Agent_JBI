package com.focusguard.app

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.focusguard.app.widget.FocusWidgetProvider

/** Déclenché par AlarmManager à la fin d'une session, même app fermée. */
class SessionAlarmReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        BlockStateStore.clear(context)
        FocusWidgetProvider.refresh(context)

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            "session_end",
            "Fin de session",
            NotificationManager.IMPORTANCE_HIGH,
        )
        manager.createNotificationChannel(channel)

        val openApp = PendingIntent.getActivity(
            context, 0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val minutes = intent.getLongExtra("minutes", 0).toInt()
        val notification = NotificationCompat.Builder(context, "session_end")
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("Bravo ! 🎉")
            .setContentText("Tu as tenu $minutes min sans réseaux sociaux.")
            .setContentIntent(openApp)
            .setAutoCancel(true)
            .build()
        manager.notify(1001, notification)
    }
}

/** Helper pour programmer l'alarme au démarrage d'une session. */
object SessionAlarm {
    fun schedule(context: Context, endsAtMs: Long, minutes: Int) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val intent = Intent(context, SessionAlarmReceiver::class.java).apply {
            putExtra("minutes", minutes.toLong())
        }
        val pending = PendingIntent.getBroadcast(
            context,
            1001,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        // setExactAndAllowWhileIdle : précis même en doze.
        am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, endsAtMs, pending)
    }

    fun cancel(context: Context) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pending = PendingIntent.getBroadcast(
            context, 1001,
            Intent(context, SessionAlarmReceiver::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        am.cancel(pending)
    }
}

package com.focusguard.app

import android.content.Context
import android.content.SharedPreferences

/** État de blocage partagé entre Flutter et le natif. */
object BlockStateStore {
    private const val PREFS = "focusguard_block"

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun setBlocking(context: Context, packages: List<String>, endsAtMs: Long, strict: Boolean) {
        prefs(context).edit()
            .putStringSet("packages", packages.toSet())
            .putLong("endsAtMs", endsAtMs)
            .putBoolean("strict", strict)
            .putBoolean("active", true)
            .apply()
    }

    fun clear(context: Context) {
        prefs(context).edit()
            .putBoolean("active", false)
            .putStringSet("packages", emptySet())
            .putLong("endsAtMs", 0)
            .putBoolean("strict", false)
            .apply()
    }

    fun isActive(context: Context): Boolean {
        val p = prefs(context)
        if (!p.getBoolean("active", false)) return false
        val endsAt = p.getLong("endsAtMs", 0)
        return System.currentTimeMillis() < endsAt
    }

    fun blockedPackages(context: Context): Set<String> =
        prefs(context).getStringSet("packages", emptySet()) ?: emptySet()

    fun isStrict(context: Context): Boolean = prefs(context).getBoolean("strict", false)

    fun endsAtMs(context: Context): Long = prefs(context).getLong("endsAtMs", 0)
}

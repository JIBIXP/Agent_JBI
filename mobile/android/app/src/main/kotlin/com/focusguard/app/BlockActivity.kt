package com.focusguard.app

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.TextView

/**
 * Écran affiché par-dessus une app bloquée.
 * En mode strict : aucun bouton de sortie. Sinon : bouton « Retour ».
 */
class BlockActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private var tickRunnable: Runnable? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_block)

        val title = findViewById<TextView>(R.id.block_title)
        val message = findViewById<TextView>(R.id.block_message)
        val countdown = findViewById<TextView>(R.id.block_countdown)
        val back = findViewById<TextView>(R.id.block_back)

        title.text = getString(R.string.block_title)
        message.text = getString(R.string.block_message)

        val strict = BlockStateStore.isStrict(this)
        back.visibility = if (strict) View.GONE else View.VISIBLE
        back.setOnClickListener { finish() }

        tickRunnable = object : Runnable {
            override fun run() {
                if (!BlockStateStore.isActive(applicationContext)) {
                    finish()
                    return
                }
                val left = BlockStateStore.endsAtMs(applicationContext) - System.currentTimeMillis()
                val minutes = left / 60000
                val seconds = (left / 1000) % 60
                countdown.text = "Fin dans %02d:%02d".format(minutes, seconds)
                handler.postDelayed(this, 1000)
            }
        }
        tickRunnable?.let { handler.post(it) }
    }

    override fun onDestroy() {
        tickRunnable?.let { handler.removeCallbacks(it) }
        super.onDestroy()
    }

    // Empêche le retour arrière pendant une session stricte.
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (!BlockStateStore.isStrict(this)) super.onBackPressed()
        // Sinon : l'utilisateur reste sur l'écran de blocage.
    }
}

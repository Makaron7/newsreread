package com.example.newsreread

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity

/**
 * This activity acts as an entry point for the Share Target feature.
 * It receives the shared content (URL) and forwards it to the MainActivity
 * before finishing itself. It has no UI (Theme.NoDisplay).
 */
class ShareActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Handle the incoming SEND intent
        if (intent?.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            intent.getStringExtra(Intent.EXTRA_TEXT)?.let { url ->
                // Create an intent to launch MainActivity and pass the URL
                val mainActivityIntent = Intent(this, MainActivity::class.java).apply {
                    action = Intent.ACTION_SEND // Set a custom action to identify the source
                    putExtra("shared_url", url)
                    // Flags to bring an existing instance of MainActivity to the front
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                }
                startActivity(mainActivityIntent)
            }
        }

        // Finish this intermediate activity
        finish()
    }
}

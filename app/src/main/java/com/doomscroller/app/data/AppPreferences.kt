package com.doomscroller.app.data

import android.content.Context
import android.content.SharedPreferences

class AppPreferences(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var isAutoScrollEnabled: Boolean
        get() = prefs.getBoolean(KEY_AUTO_SCROLL_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_SCROLL_ENABLED, value).apply()

    var pauseOnComments: Boolean
        get() = prefs.getBoolean(KEY_PAUSE_ON_COMMENTS, true)
        set(value) = prefs.edit().putBoolean(KEY_PAUSE_ON_COMMENTS, value).apply()

    var loopCountRequired: Int
        get() = prefs.getInt(KEY_LOOP_COUNT_REQUIRED, 1)
        set(value) = prefs.edit().putInt(KEY_LOOP_COUNT_REQUIRED, value).apply()

    var fallbackTimeoutSeconds: Int
        get() = prefs.getInt(KEY_FALLBACK_TIMEOUT, 65)
        set(value) = prefs.edit().putInt(KEY_FALLBACK_TIMEOUT, value).apply()

    var enableInstagram: Boolean
        get() = prefs.getBoolean(KEY_ENABLE_INSTAGRAM, true)
        set(value) = prefs.edit().putBoolean(KEY_ENABLE_INSTAGRAM, value).apply()

    var enableTikTok: Boolean
        get() = prefs.getBoolean(KEY_ENABLE_TIKTOK, true)
        set(value) = prefs.edit().putBoolean(KEY_ENABLE_TIKTOK, value).apply()

    companion object {
        private const val PREFS_NAME = "doom_scroller_prefs"
        private const val KEY_AUTO_SCROLL_ENABLED = "auto_scroll_enabled"
        private const val KEY_PAUSE_ON_COMMENTS = "pause_on_comments"
        private const val KEY_LOOP_COUNT_REQUIRED = "loop_count_required"
        private const val KEY_FALLBACK_TIMEOUT = "fallback_timeout"
        private const val KEY_ENABLE_INSTAGRAM = "enable_instagram"
        private const val KEY_ENABLE_TIKTOK = "enable_tiktok"
    }
}

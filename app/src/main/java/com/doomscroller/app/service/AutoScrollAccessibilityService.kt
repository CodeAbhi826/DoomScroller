package com.doomscroller.app.service

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import com.doomscroller.app.data.AppPreferences
import com.doomscroller.app.detector.ShortsProgressDetector

class AutoScrollAccessibilityService : AccessibilityService() {

    private val tag = "DoomScroller-Service"
    private lateinit var preferences: AppPreferences
    private lateinit var detector: ShortsProgressDetector
    private lateinit var gestureEngine: GestureEngine

    override fun onCreate() {
        super.onCreate()
        preferences = AppPreferences(applicationContext)
        detector = ShortsProgressDetector(preferences)
        gestureEngine = GestureEngine(this)
        isServiceRunning = true
        notifyStatusChanged()
        Log.i(tag, "DoomScroller Accessibility Service Created and Active")
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        isServiceRunning = true
        notifyStatusChanged()
        Log.i(tag, "DoomScroller Connected to System Accessibility Framework")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        try {
            val rootNode = rootInActiveWindow ?: return
            val shouldScroll = detector.shouldTriggerScroll(rootNode, event)

            if (shouldScroll) {
                Log.i(tag, "Video completion event detected! Triggering upward scroll...")
                gestureEngine.performScrollUp {
                    Log.i(tag, "Scroll completed, ready for next video")
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "Error processing accessibility event", e)
        }
    }

    override fun onInterrupt() {
        Log.w(tag, "DoomScroller service interrupted by system")
    }

    override fun onDestroy() {
        super.onDestroy()
        isServiceRunning = false
        notifyStatusChanged()
        Log.i(tag, "DoomScroller service destroyed")
    }

    companion object {
        var isServiceRunning: Boolean = false
            private set

        private val statusListeners = mutableListOf<(Boolean) -> Unit>()

        fun registerStatusListener(listener: (Boolean) -> Unit) {
            statusListeners.add(listener)
            listener.invoke(isServiceRunning)
        }

        fun unregisterStatusListener(listener: (Boolean) -> Unit) {
            statusListeners.remove(listener)
        }

        private fun notifyStatusChanged() {
            statusListeners.forEach { it.invoke(isServiceRunning) }
        }
    }
}

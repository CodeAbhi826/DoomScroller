package com.doomscroller.app.detector

import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.doomscroller.app.data.AppPreferences

class ShortsProgressDetector(private val preferences: AppPreferences) {

    private val tag = "DoomScroller-Detector"

    // State tracking
    private var lastObservedProgress = 0f
    private var currentLoopCount = 0
    private var currentShortSessionId = 0
    private var shortSessionStartTime = 0L
    private var lastScrollTriggerTime = 0L
    private var isCommentsOpen = false
    private var isVideoPaused = false

    // Debounce window (900ms) for snappy auto-advancing without duplicate swipes
    private val scrollCooldownMs = 900L

    fun shouldTriggerScroll(rootNode: AccessibilityNodeInfo?, event: AccessibilityEvent?): Boolean {
        if (!preferences.isAutoScrollEnabled) return false
        if (rootNode == null) return false

        val packageName = event?.packageName?.toString() ?: rootNode.packageName?.toString() ?: ""
        if (!isSupportedTarget(packageName)) return false

        val now = System.currentTimeMillis()
        if (now - lastScrollTriggerTime < scrollCooldownMs) {
            return false
        }

        // 1. Verify we are actively on the Shorts player screen
        if (!isShortsScreenActive(rootNode, packageName)) {
            return false
        }

        // 2. Check if comments or bottom drawers are visible
        isCommentsOpen = checkCommentsDrawerOpen(rootNode, packageName)
        if (preferences.pauseOnComments && isCommentsOpen) {
            Log.d(tag, "Comments drawer open, auto-scroll paused")
            shortSessionStartTime = now // Freeze / reset watchdog during comments
            return false
        }

        // 3. Check if the user paused the video
        isVideoPaused = checkVideoPaused(rootNode, packageName)
        if (isVideoPaused) {
            Log.d(tag, "Video is paused by user, auto-scroll paused")
            shortSessionStartTime = now // Freeze / reset watchdog during manual pause
            return false
        }

        // 4. Measure live playback progress
        val progressResult = extractPlaybackProgress(rootNode)
        if (progressResult != null) {
            val progress = progressResult.progressRatio

            if (shortSessionStartTime == 0L) {
                shortSessionStartTime = now
            }

            Log.d(tag, "Live Progress: ${(progress * 100).toInt()}% (last: ${(lastObservedProgress * 100).toInt()}%)")

            // End Detection: Near-complete (>= 98.0%) or Loop-wraparound (was > 80%, now < 15%)
            val isNearEnd = progress >= 0.980f
            val isLoopWraparound = lastObservedProgress >= 0.80f && progress <= 0.15f

            lastObservedProgress = progress

            if (isNearEnd || isLoopWraparound) {
                currentLoopCount++
                Log.i(tag, "Short completion detected! (Loops watched: $currentLoopCount / Required: ${preferences.loopCountRequired})")

                if (currentLoopCount >= preferences.loopCountRequired) {
                    resetSessionState(now)
                    return true
                }
            }
        } else {
            // Fallback watchdog for ads or progress-barless video layouts
            if (shortSessionStartTime == 0L) {
                shortSessionStartTime = now
            }
            val elapsedSec = (now - shortSessionStartTime) / 1000
            val maxAllowed = preferences.fallbackTimeoutSeconds

            if (elapsedSec >= maxAllowed) {
                Log.w(tag, "Watchdog triggered: Video elapsed $elapsedSec s without progress bar, auto-advancing")
                resetSessionState(now)
                return true
            }
        }

        return false
    }

    private fun isSupportedTarget(packageName: String): Boolean {
        return packageName.contains("youtube")
    }

    private fun isShortsScreenActive(root: AccessibilityNodeInfo, packageName: String): Boolean {
        if (!packageName.contains("youtube")) return false

        // Check known YouTube Shorts fragment root, recycler, and time bar IDs
        val rootMatches = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_watch_fragment_root")
        if (!rootMatches.isNullOrEmpty()) return true

        val recyclerMatches = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_recycler")
        if (!recyclerMatches.isNullOrEmpty()) return true

        val timeBarMatches = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_time_bar")
        if (!timeBarMatches.isNullOrEmpty()) return true

        val playerMatches = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_player_progress_bar")
        if (!playerMatches.isNullOrEmpty()) return true

        return false
    }

    private fun checkCommentsDrawerOpen(root: AccessibilityNodeInfo, packageName: String): Boolean {
        val commentIds = listOf(
            "com.google.android.youtube:id/comment_sheet",
            "com.google.android.youtube:id/comments_header",
            "com.google.android.youtube:id/design_bottom_sheet",
            "com.google.android.youtube:id/panel_header"
        )

        for (id in commentIds) {
            val nodes = root.findAccessibilityNodeInfosByViewId(id)
            if (!nodes.isNullOrEmpty()) {
                return true
            }
        }
        return false
    }

    private fun checkVideoPaused(root: AccessibilityNodeInfo, packageName: String): Boolean {
        // When video is playing, YouTube displays a "Pause video" button.
        // When video is paused, the button flips to "Play video".
        val playButtons = root.findAccessibilityNodeInfosByText("Play video")
        if (!playButtons.isNullOrEmpty()) {
            return true
        }

        return hasNodeWithContentDescription(root, "Play video")
    }

    private fun hasNodeWithContentDescription(node: AccessibilityNodeInfo?, target: String): Boolean {
        if (node == null) return false
        val desc = node.contentDescription?.toString()
        if (desc != null && desc.equals(target, ignoreCase = true)) {
            return true
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            if (hasNodeWithContentDescription(child, target)) {
                return true
            }
        }
        return false
    }

    private data class ProgressData(val progressRatio: Float, val isAccurate: Boolean)

    private fun extractPlaybackProgress(root: AccessibilityNodeInfo): ProgressData? {
        // 1. Check reel_time_bar (modern YouTube Shorts seekbar container)
        val timeBarNodes = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_time_bar")
        if (!timeBarNodes.isNullOrEmpty()) {
            val data = parseNodeProgress(timeBarNodes[0])
            if (data != null) return data
            // Also inspect child elements of reel_time_bar
            val container = timeBarNodes[0]
            for (i in 0 until container.childCount) {
                val child = container.getChild(i) ?: continue
                val childData = parseNodeProgress(child)
                if (childData != null) return childData
            }
        }

        // 2. Legacy check: reel_player_progress_bar
        val pbNodes = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_player_progress_bar")
        if (!pbNodes.isNullOrEmpty()) {
            val data = parseNodeProgress(pbNodes[0])
            if (data != null) return data
        }

        // 3. Fallback: Search for any node with RangeInfo or natural time description
        return findProgressNodeRecursive(root)
    }

    private fun findProgressNodeRecursive(node: AccessibilityNodeInfo?): ProgressData? {
        if (node == null) return null

        val parsed = parseNodeProgress(node)
        if (parsed != null) return parsed

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val childResult = findProgressNodeRecursive(child)
            if (childResult != null) return childResult
        }
        return null
    }

    private fun parseNodeProgress(node: AccessibilityNodeInfo): ProgressData? {
        // Primary: rangeInfo (exact float calculation)
        val rangeInfo = node.rangeInfo
        if (rangeInfo != null && rangeInfo.max > 0f) {
            val range = rangeInfo.max - rangeInfo.min
            if (range > 0f) {
                val ratio = (rangeInfo.current - rangeInfo.min) / range
                return ProgressData(ratio.coerceIn(0f, 1f), isAccurate = true)
            }
        }

        // Secondary: Parse time descriptions (supports both colon and spoken TalkBack strings)
        val desc = node.contentDescription?.toString()
        if (desc != null && (desc.contains("of", ignoreCase = true) || desc.contains("/"))) {
            val ratio = parseTimeDescription(desc)
            if (ratio != null) {
                return ProgressData(ratio.coerceIn(0f, 1f), isAccurate = true)
            }
        }

        return null
    }

    /**
     * Parses time strings such as:
     * - "0 minutes 15 seconds of 0 minutes 22 seconds"
     * - "15 seconds of 22 seconds"
     * - "0:15 of 0:22"
     * - "1:05 / 2:30"
     */
    private fun parseTimeDescription(text: String): Float? {
        try {
            val parts = if (text.contains("of", ignoreCase = true)) {
                text.split(Regex("(?i)\\bof\\b"))
            } else {
                text.split("/")
            }

            if (parts.size >= 2) {
                val currentSec = parseSeconds(parts[0].trim())
                val totalSec = parseSeconds(parts[1].trim())

                if (totalSec > 0 && currentSec >= 0) {
                    return currentSec.toFloat() / totalSec.toFloat()
                }
            }
        } catch (e: Exception) {
            Log.d(tag, "Error parsing time description: $text", e)
        }
        return null
    }

    private fun parseSeconds(text: String): Int {
        // Format 1: colon syntax (e.g. 0:15 or 1:20:05)
        val colonMatch = Regex("""(\d+):(\d+)""").find(text)
        if (colonMatch != null) {
            val m = colonMatch.groupValues[1].toInt()
            val s = colonMatch.groupValues[2].toInt()
            return (m * 60) + s
        }

        // Format 2: spoken natural language (e.g. "0 minutes 15 seconds", "15 seconds")
        var total = 0
        var foundAny = false

        val minMatch = Regex("""(\d+)\s*m""").find(text)
        if (minMatch != null) {
            total += minMatch.groupValues[1].toInt() * 60
            foundAny = true
        }

        val secMatch = Regex("""(\d+)\s*s""").find(text)
        if (secMatch != null) {
            total += secMatch.groupValues[1].toInt()
            foundAny = true
        }

        if (!foundAny) {
            val numMatch = Regex("""\b(\d+)\b""").find(text)
            if (numMatch != null) {
                total = numMatch.groupValues[1].toInt()
            }
        }

        return total
    }

    private fun resetSessionState(now: Long) {
        lastScrollTriggerTime = now
        lastObservedProgress = 0f
        currentLoopCount = 0
        shortSessionStartTime = now
        currentShortSessionId++
    }
}

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

    // Debounce window (800ms) for snappy auto-advancing without duplicate swipes
    private val scrollCooldownMs = 800L

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

            // End Detection: Near-complete (>= 98.0%) or Loop-wraparound (was >= 75%, now <= 15%)
            val isNearEnd = progress >= 0.980f
            val isLoopWraparound = lastObservedProgress >= 0.75f && progress <= 0.15f

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
            "com.google.android.youtube:id/panel_header",
            "com.google.android.youtube:id/engagement_panel"
        )

        for (id in commentIds) {
            val nodes = root.findAccessibilityNodeInfosByViewId(id)
            if (!nodes.isNullOrEmpty()) {
                for (node in nodes) {
                    if (node.isVisibleToUser) {
                        return true
                    }
                }
            }
        }
        return false
    }

    private fun checkVideoPaused(root: AccessibilityNodeInfo, packageName: String): Boolean {
        // When video is playing, YouTube displays a "Pause video" button.
        // When video is paused, the button flips to "Play video".
        val playButtons = root.findAccessibilityNodeInfosByText("Play video")
        if (!playButtons.isNullOrEmpty()) {
            for (btn in playButtons) {
                if (btn.isVisibleToUser) {
                    return true
                }
            }
        }

        return hasVisibleNodeWithContentDescription(root, "Play video")
    }

    private fun hasVisibleNodeWithContentDescription(node: AccessibilityNodeInfo?, target: String): Boolean {
        if (node == null) return false
        val desc = node.contentDescription?.toString()
        if (desc != null && desc.equals(target, ignoreCase = true) && node.isVisibleToUser) {
            return true
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            if (hasVisibleNodeWithContentDescription(child, target)) {
                return true
            }
        }
        return false
    }

    private data class ProgressData(val progressRatio: Float, val isAccurate: Boolean)

    private fun extractPlaybackProgress(root: AccessibilityNodeInfo): ProgressData? {
        // 1. Direct discovery: Look up reel_time_bar first, then locate child SeekBar
        val timeBarNodes = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_time_bar")
        if (!timeBarNodes.isNullOrEmpty()) {
            for (node in timeBarNodes) {
                val data = findSeekBarOrProgress(node)
                if (data != null) return data
            }
        }

        // 2. Legacy check: reel_player_progress_bar
        val pbNodes = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_player_progress_bar")
        if (!pbNodes.isNullOrEmpty()) {
            for (node in pbNodes) {
                val data = parseNodeProgress(node)
                if (data != null) return data
            }
        }

        // 3. Fallback: Search for any node with RangeInfo or natural time description
        return findProgressNodeRecursive(root)
    }

    private fun findSeekBarOrProgress(node: AccessibilityNodeInfo): ProgressData? {
        // Direct container progress check
        val direct = parseNodeProgress(node)
        if (direct != null) return direct

        // Priority 1: Check children specifically for SeekBar class
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            if (child.className?.contains("SeekBar", ignoreCase = true) == true) {
                val data = parseNodeProgress(child)
                if (data != null) return data
            }
        }

        // Priority 2: Check all direct children
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val data = parseNodeProgress(child)
            if (data != null) return data
        }

        // Priority 3: Recursive traversal under container
        return findProgressNodeRecursive(node)
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
        try {
            node.refresh()
        } catch (_: Exception) {}

        // Priority 1: Parse live TalkBack / accessibility time descriptions.
        // YouTube Shorts SeekBar continuously updates its contentDescription (e.g. "0 minutes 15 seconds of 0 minutes 22 seconds"),
        // while its rangeInfo.current remains frozen at 0.0f unless manually scrubbed.
        val desc = node.contentDescription?.toString()
        if (!desc.isNullOrEmpty()) {
            val ratio = parseTimeDescription(desc)
            if (ratio != null) {
                Log.d(tag, "Parsed progress from desc '$desc': ${(ratio * 100).toInt()}%")
                return ProgressData(ratio.coerceIn(0f, 1f), isAccurate = true)
            }
        }

        val text = node.text?.toString()
        if (!text.isNullOrEmpty()) {
            val ratio = parseTimeDescription(text)
            if (ratio != null) {
                Log.d(tag, "Parsed progress from text '$text': ${(ratio * 100).toInt()}%")
                return ProgressData(ratio.coerceIn(0f, 1f), isAccurate = true)
            }
        }

        // Priority 2: rangeInfo fallback (only if current > 0f, avoiding false 0.0f lock)
        val rangeInfo = node.rangeInfo
        if (rangeInfo != null && rangeInfo.max > 0f && rangeInfo.current > 0f) {
            val range = rangeInfo.max - rangeInfo.min
            if (range > 0f) {
                val ratio = (rangeInfo.current - rangeInfo.min) / range
                return ProgressData(ratio.coerceIn(0f, 1f), isAccurate = true)
            }
        }

        return null
    }

    /**
     * Parses time strings such as:
     * - "0 minutes 15 seconds of 0 minutes 22 seconds"
     * - "15 seconds of 22 seconds"
     * - "0 minutes 40 seconds of 1 minute 25 seconds"
     * - "1 minute of 2 minutes"
     * - "0:15 of 0:22"
     * - "1:05 / 2:30"
     * - "98%"
     */
    private fun parseTimeDescription(text: String): Float? {
        try {
            val clean = text.trim()

            // Handle percentage strings e.g. "98%" or "Seek bar at 98%"
            val percentMatch = Regex("""(\d+(?:\.\d+)?)\s*%""").find(clean)
            if (percentMatch != null) {
                val p = percentMatch.groupValues[1].toFloatOrNull()
                if (p != null) return (p / 100f).coerceIn(0f, 1f)
            }

            // Split into current and total parts using "of" or "/"
            val parts = if (clean.contains("of", ignoreCase = true)) {
                clean.split(Regex("""(?i)\s+of\s+|\bof\b"""))
            } else if (clean.contains("/")) {
                clean.split("/")
            } else {
                null
            }

            if (parts != null && parts.size >= 2) {
                val currentSec = parseSeconds(parts[0])
                val totalSec = parseSeconds(parts[1])

                if (currentSec != null && totalSec != null && totalSec > 0f && currentSec >= 0f) {
                    return (currentSec / totalSec).coerceIn(0f, 1f)
                }
            }
        } catch (e: Exception) {
            Log.d(tag, "Error parsing time description: $text", e)
        }
        return null
    }

    private fun parseSeconds(text: String): Float? {
        val clean = text.trim().removeSuffix(".")

        // Format 1: colon syntax (e.g. 0:15, 1:05, 1:02:15)
        val colonMatch = Regex("""(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)""").find(clean)
        if (colonMatch != null) {
            val h = colonMatch.groupValues[1].toIntOrNull() ?: 0
            val m = colonMatch.groupValues[2].toIntOrNull() ?: 0
            val s = colonMatch.groupValues[3].toFloatOrNull() ?: 0f
            return (h * 3600f) + (m * 60f) + s
        }

        // Format 2: spoken natural language (e.g. "0 minutes 15 seconds", "1 minute 25 seconds")
        var total = 0f
        var foundAny = false

        val hrMatch = Regex("""(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b""", RegexOption.IGNORE_CASE).find(clean)
        if (hrMatch != null) {
            val hrs = hrMatch.groupValues[1].toFloatOrNull() ?: 0f
            total += hrs * 3600f
            foundAny = true
        }

        val minMatch = Regex("""(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b""", RegexOption.IGNORE_CASE).find(clean)
        if (minMatch != null) {
            val mins = minMatch.groupValues[1].toFloatOrNull() ?: 0f
            total += mins * 60f
            foundAny = true
        }

        val secMatch = Regex("""(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b""", RegexOption.IGNORE_CASE).find(clean)
        if (secMatch != null) {
            val secs = secMatch.groupValues[1].toFloatOrNull() ?: 0f
            total += secs
            foundAny = true
        }

        if (foundAny) {
            return total
        }

        // Format 3: bare number
        val numMatch = Regex("""\b(\d+(?:\.\d+)?)\b""").find(clean)
        if (numMatch != null) {
            return numMatch.groupValues[1].toFloatOrNull()
        }

        return null
    }

    private fun resetSessionState(now: Long) {
        lastScrollTriggerTime = now
        lastObservedProgress = 0f
        currentLoopCount = 0
        shortSessionStartTime = now
        currentShortSessionId++
    }
}

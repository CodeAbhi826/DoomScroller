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

    // Debounce window to prevent double-swiping
    private val scrollCooldownMs = 1500L

    fun shouldTriggerScroll(rootNode: AccessibilityNodeInfo?, event: AccessibilityEvent?): Boolean {
        if (!preferences.isAutoScrollEnabled) return false
        if (rootNode == null) return false

        val packageName = event?.packageName?.toString() ?: rootNode.packageName?.toString() ?: ""
        if (!isSupportedTarget(packageName)) return false

        val now = System.currentTimeMillis()
        if (now - lastScrollTriggerTime < scrollCooldownMs) {
            return false
        }

        // 1. Verify we are actively on the Shorts / Reels player screen
        if (!isShortsScreenActive(rootNode, packageName)) {
            return false
        }

        // 2. Check if comments or bottom drawers are visible
        isCommentsOpen = checkCommentsDrawerOpen(rootNode, packageName)
        if (preferences.pauseOnComments && isCommentsOpen) {
            Log.d(tag, "Comments drawer open, auto-scroll paused")
            return false
        }

        // 3. Check if the user paused the video
        isVideoPaused = checkVideoPaused(rootNode, packageName)
        if (isVideoPaused) {
            Log.d(tag, "Video is paused by user, auto-scroll paused")
            return false
        }

        // 4. Measure live playback progress
        val progressResult = extractPlaybackProgress(rootNode)
        if (progressResult != null) {
            val progress = progressResult.progressRatio
            val durationKnown = progressResult.isAccurate

            if (shortSessionStartTime == 0L) {
                shortSessionStartTime = now
            }

            Log.d(tag, "Live Progress: ${(progress * 100).toInt()}% (last: ${(lastObservedProgress * 100).toInt()}%)")

            // End Detection: Near-complete (>= 98.5%) or Loop-wraparound (was > 88%, now < 12%)
            val isNearEnd = progress >= 0.985f
            val isLoopWraparound = lastObservedProgress >= 0.88f && progress <= 0.12f

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
        return when {
            packageName.contains("youtube") -> true
            packageName.contains("instagram") && preferences.enableInstagram -> true
            packageName.contains("musically") && preferences.enableTikTok -> true
            else -> false
        }
    }

    private fun isShortsScreenActive(root: AccessibilityNodeInfo, packageName: String): Boolean {
        if (packageName.contains("youtube")) {
            // Check known YouTube Shorts fragment root and recycler IDs
            val rootMatches = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_watch_fragment_root")
            if (!rootMatches.isNullOrEmpty()) return true

            val recyclerMatches = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_recycler")
            if (!recyclerMatches.isNullOrEmpty()) return true

            val playerMatches = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_player_progress_bar")
            if (!playerMatches.isNullOrEmpty()) return true
        } else if (packageName.contains("instagram")) {
            val reels = root.findAccessibilityNodeInfosByViewId("com.instagram.android:id/reel_viewer_container")
            if (!reels.isNullOrEmpty()) return true
            val clips = root.findAccessibilityNodeInfosByViewId("com.instagram.android:id/clips_video_container")
            if (!clips.isNullOrEmpty()) return true
        } else if (packageName.contains("musically")) {
            val pager = root.findAccessibilityNodeInfosByViewId("com.zhiliaoapp.musically:id/viewpager")
            if (!pager.isNullOrEmpty()) return true
        }
        return false
    }

    private fun checkCommentsDrawerOpen(root: AccessibilityNodeInfo, packageName: String): Boolean {
        val commentIds = listOf(
            "com.google.android.youtube:id/comment_sheet",
            "com.google.android.youtube:id/comments_header",
            "com.google.android.youtube:id/design_bottom_sheet",
            "com.google.android.youtube:id/panel_header",
            "com.instagram.android:id/comment_sheet_container"
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

        // Also check by content description in tree
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
        // 1. Try finding YouTube Shorts progress bar by resource ID
        val pbNodes = root.findAccessibilityNodeInfosByViewId("com.google.android.youtube:id/reel_player_progress_bar")
        if (!pbNodes.isNullOrEmpty()) {
            val data = parseNodeProgress(pbNodes[0])
            if (data != null) return data
        }

        // 2. Recursive search for ProgressBar or nodes with RangeInfo
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
        val rangeInfo = node.rangeInfo
        if (rangeInfo != null && rangeInfo.max > 0f) {
            val range = rangeInfo.max - rangeInfo.min
            if (range > 0f) {
                val ratio = (rangeInfo.current - rangeInfo.min) / range
                return ProgressData(ratio.coerceIn(0f, 1f), isAccurate = true)
            }
        }

        // Secondary: Parse time descriptions like "12 seconds of 35 seconds" or "0:15 of 0:45"
        val desc = node.contentDescription?.toString()
        if (desc != null) {
            val timeRegex = Regex("""(\d+):?(\d*)\s+(?:of|/)\s+(\d+):?(\d*)""")
            val match = timeRegex.find(desc)
            if (match != null) {
                try {
                    val currentSec = parseSeconds(match.groupValues[1], match.groupValues[2])
                    val totalSec = parseSeconds(match.groupValues[3], match.groupValues[4])
                    if (totalSec > 0) {
                        val ratio = currentSec.toFloat() / totalSec.toFloat()
                        return ProgressData(ratio.coerceIn(0f, 1f), isAccurate = true)
                    }
                } catch (_: Exception) {}
            }
        }

        return null
    }

    private fun parseSeconds(part1: String, part2: String): Int {
        return if (part2.isEmpty()) {
            part1.toInt()
        } else {
            val minutes = part1.toInt()
            val seconds = part2.toInt()
            (minutes * 60) + seconds
        }
    }

    private fun resetSessionState(now: Long) {
        lastScrollTriggerTime = now
        lastObservedProgress = 0f
        currentLoopCount = 0
        shortSessionStartTime = now
        currentShortSessionId++
    }
}

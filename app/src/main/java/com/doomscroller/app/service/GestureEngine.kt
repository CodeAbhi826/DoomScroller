package com.doomscroller.app.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.util.Log
import kotlin.random.Random

class GestureEngine(private val service: AccessibilityService) {

    private val tag = "DoomScroller-Gesture"
    private var isDispatching = false

    fun performScrollUp(onComplete: (() -> Unit)? = null): Boolean {
        if (isDispatching) {
            Log.d(tag, "Swipe in progress, skipping duplicate request")
            return false
        }

        val displayMetrics = service.resources.displayMetrics
        val width = displayMetrics.widthPixels.toFloat()
        val height = displayMetrics.heightPixels.toFloat()

        if (width <= 0f || height <= 0f) {
            Log.w(tag, "Invalid display dimensions: ${width}x${height}")
            return false
        }

        // Straight vertical flick coordinates centered on screen
        // Start at 75% height and end at 25% height to clear Android 14 gesture navigation bar
        val x = width * 0.5f
        val startY = height * 0.75f
        val endY = height * 0.25f

        val swipePath = Path().apply {
            moveTo(x, startY)
            lineTo(x, endY)
        }

        // Snappy duration (150 - 180ms) for high-velocity flick with zero gesture cancellation
        val duration = Random.nextLong(150, 181)
        val stroke = GestureDescription.StrokeDescription(swipePath, 0, duration)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()

        isDispatching = true
        Log.i(tag, "Dispatching upward scroll gesture: (${x.toInt()}, ${startY.toInt()}) -> (${x.toInt()}, ${endY.toInt()}) in ${duration}ms")

        val dispatched = service.dispatchGesture(
            gesture,
            object : AccessibilityService.GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    super.onCompleted(gestureDescription)
                    isDispatching = false
                    Log.i(tag, "Scroll gesture completed successfully")
                    onComplete?.invoke()
                }

                override fun onCancelled(gestureDescription: GestureDescription?) {
                    super.onCancelled(gestureDescription)
                    isDispatching = false
                    Log.w(tag, "Scroll gesture was cancelled by system")
                    onComplete?.invoke()
                }
            },
            null
        )

        if (!dispatched) {
            isDispatching = false
            Log.e(tag, "dispatchGesture returned false")
        }

        return dispatched
    }
}

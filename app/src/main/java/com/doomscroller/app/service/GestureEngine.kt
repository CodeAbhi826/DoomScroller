package com.doomscroller.app.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.util.Log
import kotlin.random.Random

class GestureEngine(private val service: AccessibilityService) {

    private val tag = "DoomScroller-Gesture"
    private var isDispatching = false

    fun performScrollUp(onComplete: (() -> Unit)? = null) {
        if (isDispatching) {
            Log.d(tag, "Swipe in progress, skipping duplicate request")
            return
        }

        val displayMetrics = service.resources.displayMetrics
        val width = displayMetrics.widthPixels.toFloat()
        val height = displayMetrics.heightPixels.toFloat()

        if (width <= 0f || height <= 0f) {
            Log.w(tag, "Invalid display dimensions: ${width}x${height}")
            return
        }

        // Fast, authentic thumb flick coordinates tailored for vertical Short paging
        val jitterX = (Random.nextFloat() - 0.5f) * 12f
        val startX = (width * 0.5f) + jitterX
        val startY = height * 0.76f
        val endX = (width * 0.5f) + (jitterX * 0.4f)
        val endY = height * 0.22f

        val swipePath = Path().apply {
            moveTo(startX, startY)
            val controlX = startX + (Random.nextFloat() - 0.5f) * 16f
            val controlY = (startY + endY) * 0.5f
            quadTo(controlX, controlY, endX, endY)
        }

        // Snappy duration (160 - 200ms) to ensure instant, crisp page transition
        val duration = Random.nextLong(160, 200)
        val stroke = GestureDescription.StrokeDescription(swipePath, 0, duration)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()

        isDispatching = true
        Log.i(tag, "Dispatching upward scroll gesture: (${startX.toInt()}, ${startY.toInt()}) -> (${endX.toInt()}, ${endY.toInt()}) in ${duration}ms")

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
    }
}

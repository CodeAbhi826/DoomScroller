# DoomScroller

**DoomScroller** is a native, hands-free automated scroller for **YouTube Shorts** (and Instagram Reels) on Android, designed to mimic Meta's native "Auto-Advance" feature.

Unlike naive timer-based scrollers that use static intervals (e.g. 15s), **DoomScroller automatically adapts to uneven video lengths** (whether a Short is 4 seconds, 22 seconds, or 59 seconds) by inspecting YouTube's live playback progress bar via Android's Accessibility Framework.

---

## 🚀 Key Features

* **100% Fully Automated Hands-Free Scrolling**: Advances to the next Short as soon as playback concludes without touching the screen.
* **Dynamic / Uneven Video Length Support**:
  * Reads the live normalized progress ($current / max$) directly from YouTube's player node hierarchy.
  * Detects both **near-end completion** ($\ge 98.5\%$) and **instant loop-wraparound** ($>90\% \rightarrow <10\%$).
* **Smart Pause**:
  * Automatically halts scrolling if you open the **Comments** drawer.
  * Pauses auto-advancing if you manually pause the video.
* **Natural Gesture Engine**:
  * Programmatically dispatches fluid upward flick gestures (`dispatchGesture`) using Bezier interpolation and subtle micro-jitter.
* **Watchdog Safety Timer**:
  * If an ad or promotional Short lacks a visible progress bar, a safety watchdog auto-scrolls after a configurable maximum duration to ensure the feed never hangs.
* **Zero Root & Non-Modded**:
  * Works on the official, unmodified YouTube app from the Google Play Store.

---

## 🛠️ Architecture Overview

```
YouTube App (Foreground)
       │
       ▼
[ExoPlayer / UI Surface]
       │
       ▼
[Accessibility Tree Nodes]
  • className: android.widget.ProgressBar
  • id: com.google.android.youtube:id/reel_player_progress_bar
  • rangeInfo: { min, max, current }
       │
       ▼
DoomScroller AccessibilityService
       │
       ├── ShortsProgressDetector (Calculates ratio, checks comments & pause state)
       │
       └── GestureEngine (Performs natural dispatchGesture swipe-up)
```

---

## 📱 How to Install and Run

### 1. Build the APK
```bash
./gradlew assembleDebug
```
The output APK will be generated at:
`app/build/outputs/apk/debug/app-debug.apk`

### 2. Install via ADB
```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

### 3. Grant Accessibility Permission
1. Open **DoomScroller** on your Android device.
2. Tap **Enable Accessibility Service**.
3. Under **Installed Apps / Downloaded Services**, locate **DoomScroller Auto-Scroll Service** and toggle it **ON**.
4. (Recommended) Tap **Disable Battery Restrictions** to prevent aggressive OEM battery managers (MIUI, OneUI) from stopping the background service.

### 4. Enjoy Hands-Free YouTube Shorts
Tap **Open YouTube Shorts** in DoomScroller or launch the YouTube app. Play any Short—when it concludes, DoomScroller will automatically swipe up to the next video!

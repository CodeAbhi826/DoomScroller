# Codebase & Architecture Investigation Report: DoomScroller

**Date**: 2026-11-04  
**Investigator**: `explorer_survey_1`  
**Mission**: Comprehensive repository mapping, AccessibilityService investigation, architectural event flow analysis, build/SDK discovery, and test infrastructure assessment.

---

## Executive Summary

DoomScroller is a native Android accessibility application designed to automatically detect when a YouTube Short completes playback and dispatches a programmatic upward flick gesture to advance to the next Short. The project is an idiomatic single-module Kotlin Android project targeting API 35 with a minimum SDK of 26 (Android 8.0). It leverages Android's Accessibility Framework (`AccessibilityService`, `AccessibilityNodeInfo`, `GestureDescription`) without requiring root access or modified YouTube client binaries.

Crucial findings regarding R1–R4 requirements from the initial survey:
1. **Target Filtering**: The service config XML (`accessibility_service_config.xml`) currently includes YouTube TV, Instagram, and TikTok package names alongside `com.google.android.youtube`. The detector also includes Instagram/TikTok logic. Under the active requirement scope, YouTube Shorts is the exclusive target.
2. **Detection Logic & Latency**: `ShortsProgressDetector` uses a 1500ms debounce cooldown (`scrollCooldownMs = 1500L`). It detects completion using two triggers: near-end progress ($\ge 98.5\%$) and loop wraparound ($last \ge 88\% \rightarrow current \le 12\%$).
3. **Smart Pause**: Pausing is currently implemented by checking for YouTube comments drawer view IDs (`comment_sheet`, `comments_header`, `design_bottom_sheet`, `panel_header`) and detecting the "Play video" text or content description (which indicates the video is currently paused).
4. **Gesture Engine**: Dispatches quadratic Bezier gestures with subtle micro-jitter using `AccessibilityService.dispatchGesture`. Duration is randomized between 280ms and 330ms.
5. **Testing Infrastructure**: The repository currently contains **zero unit tests and zero UI/instrumented tests**. There are no test directories (`src/test`, `src/androidTest`) or test dependencies in `app/build.gradle.kts`.
6. **Build & Runtime Environment**:
   - The connected device `192.168.1.40:5555` (`SM_E146B`, Samsung Galaxy F14 5G) is online with `com.doomscroller.app` installed and `AutoScrollAccessibilityService` active in `enabled_accessibility_services`.
   - YouTube (`com.google.android.youtube`, version `21.43.523`) is installed on the device.
   - The host system default JDK is OpenJDK 27 (`27.0.1.0.3`), which causes Gradle 8.9 to fail immediately when launching `./gradlew` from the system default environment. A pre-compiled debug APK (`app-debug.apk`, 13.4MB) is present in the workspace root. For host builds, JDK 17/21 (`jdk17-openjdk` or `jdk21-openjdk`) must be configured.

---

## 1. Repository Structure & Map

### 1.1 Complete File Hierarchy

```
DoomScroller/
├── .agents/                                # Multi-agent teamwork metadata
│   └── teamwork/
│       ├── ORIGINAL_REQUEST.md             # Original user request & constraints
│       ├── explorer_survey_1/              # Explorer working directory
│       │   ├── BRIEFING.md
│       │   ├── DISPATCH.md
│       │   ├── progress.md
│       │   ├── report.md
│       │   └── handoff.md
│       └── ...
├── app/
│   ├── build.gradle.kts                    # App module build configuration
│   ├── proguard-rules.pro                  # R8/Proguard rules (empty template)
│   └── src/
│       └── main/
│           ├── AndroidManifest.xml          # Permissions, MainActivity, AccessibilityService
│           ├── java/com/doomscroller/app/
│           │   ├── MainActivity.kt          # UI, accessibility status, toggles, launch intent
│           │   ├── data/
│           │   │   └── AppPreferences.kt    # SharedPreferences wrapper
│           │   ├── detector/
│           │   │   └── ShortsProgressDetector.kt # AccessibilityNode progress evaluation
│           │   └── service/
│           │       ├── AutoScrollAccessibilityService.kt # AccessibilityService lifecycle & bridge
│           │       └── GestureEngine.kt     # dispatchGesture touch simulation
│           └── res/
│               ├── drawable/                # (Empty)
│               ├── layout/
│               │   └── activity_main.xml    # Material 3 UI layout with status card and controls
│               ├── values/
│               │   ├── colors.xml           # Dark theme color palette
│               │   ├── strings.xml          # Localization strings
│               │   └── themes.xml           # DayNight.NoActionBar Material3 theme
│               └── xml/
│                   └── accessibility_service_config.xml # Accessibility metadata
├── gradle/
│   ├── libs.versions.toml                   # Gradle Version Catalog (AGP, Kotlin, AndroidX)
│   └── wrapper/
│       ├── gradle-wrapper.jar
│       └── gradle-wrapper.properties        # Gradle 8.9 distribution
├── app-debug.apk                            # Pre-existing debug build artifact (13.4MB)
├── build.gradle.kts                         # Root project build script (plugin aliases)
├── gradle.properties                        # JVM memory args, AndroidX flags
├── gradlew                                  # Gradle wrapper shell script
├── README.md                                # Project documentation & architecture diagram
└── settings.gradle.kts                      # Dependency resolution management & module inclusion
```

### 1.2 Package Organization
All application code resides under the root namespace `com.doomscroller.app`:
- `com.doomscroller.app`: `MainActivity.kt` (Entry activity)
- `com.doomscroller.app.data`: `AppPreferences.kt` (User configuration state)
- `com.doomscroller.app.detector`: `ShortsProgressDetector.kt` (Video end & pause detection)
- `com.doomscroller.app.service`: `AutoScrollAccessibilityService.kt`, `GestureEngine.kt` (Accessibility lifecycle and input injection)

---

## 2. Build Configuration, SDKs & Dependencies

### 2.1 Build Tooling Versions
- **Gradle Version**: 8.9 (via `gradle/wrapper/gradle-wrapper.properties`)
- **Android Gradle Plugin (AGP)**: 8.6.1 (`gradle/libs.versions.toml`)
- **Kotlin Version**: 2.0.21 (`gradle/libs.versions.toml`)
- **JDK Target**: Java 17 (`sourceCompatibility`, `targetCompatibility`, and `kotlinOptions.jvmTarget = "17"`)
- **Host JVM Incompatibility Note**: Host system has OpenJDK 27 default. Running `./gradlew` triggers `FAILURE: Build failed with an exception. What went wrong: 27.0.1.0.3`. When executing `./gradlew`, `JAVA_HOME` must point to JDK 17 or JDK 21.

### 2.2 SDK Levels (`app/build.gradle.kts`)
- `compileSdk = 35` (Android 15)
- `targetSdk = 35` (Android 15)
- `minSdk = 26` (Android 8.0 Oreo - required for `AccessibilityService.dispatchGesture` introduced in API 24/26)
- `versionCode = 1`
- `versionName = "1.0.0"`

### 2.3 Dependencies & Libraries
From `gradle/libs.versions.toml` and `app/build.gradle.kts`:
- `androidx.core:core-ktx:1.15.0`
- `androidx.appcompat:appcompat:1.7.0`
- `com.google.android.material:material:1.12.0`
- `androidx.constraintlayout:constraintlayout:2.2.0`

### 2.4 Build Features & ProGuard
- `viewBinding = true`
- Release build: `isMinifyEnabled = false`, ProGuard rules at `app/proguard-rules.pro`.

### 2.5 Standard Build Commands
- Assemble debug APK: `./gradlew assembleDebug` (Output: `app/build/outputs/apk/debug/app-debug.apk`)
- Clean build: `./gradlew clean`
- Run lint: `./gradlew lintDebug`
- Unit tests: `./gradlew test` (Currently executes 0 tests due to absence of test sources)

---

## 3. AccessibilityService Deep Dive

### 3.1 Service Declaration in `AndroidManifest.xml`
```xml
<service
    android:name=".service.AutoScrollAccessibilityService"
    android:exported="true"
    android:label="@string/accessibility_service_name"
    android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
    <intent-filter>
        <action android:name="android.accessibilityservice.AccessibilityService" />
    </intent-filter>
    <meta-data
        android:name="android.accessibilityservice"
        android:resource="@xml/accessibility_service_config" />
</service>
```
Permissions requested in manifest:
- `android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`: Prevents OEM background kills.
- `android.permission.RECEIVE_BOOT_COMPLETED`: Allows starting on boot.
- `android.permission.SYSTEM_ALERT_WINDOW`: Can display system overlays if needed.

### 3.2 Accessibility XML Configuration (`res/xml/accessibility_service_config.xml`)
```xml
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowContentChanged|typeWindowStateChanged|typeViewScrolled"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:accessibilityFlags="flagDefault|flagRetrieveInteractiveWindows|flagReportViewIds"
    android:canPerformGestures="true"
    android:canRetrieveWindowContent="true"
    android:description="@string/accessibility_service_description"
    android:notificationTimeout="50"
    android:packageNames="com.google.android.youtube,com.google.android.youtube.tv,com.instagram.android,com.zhiliaoapp.musically" />
```

#### Detailed Breakdown of Attributes:
1. **`android:accessibilityEventTypes`**:
   - `typeWindowContentChanged`: Dispatched when view hierarchies update (e.g. playback progress bar animating, comments bottom sheet popping up).
   - `typeWindowStateChanged`: Dispatched when activities or windows transition (e.g., opening a new video or dialog).
   - `typeViewScrolled`: Dispatched during scroll events (e.g., when moving between shorts).
2. **`android:accessibilityFlags`**:
   - `flagDefault`: Basic accessibility behavior.
   - `flagRetrieveInteractiveWindows`: Allows inspecting active windows including overlays and bottom sheets.
   - `flagReportViewIds`: Essential for reading view resource IDs (such as `reel_player_progress_bar`).
3. **`android:canPerformGestures="true"`**:
   - Mandatory permission granting the service ability to call `dispatchGesture()` to inject touch events without root.
4. **`android:canRetrieveWindowContent="true"`**:
   - Mandatory permission granting access to `rootInActiveWindow` and the `AccessibilityNodeInfo` tree.
5. **`android:notificationTimeout="50"`**:
   - Throttles event dispatching to once every 50ms per event type.
6. **`android:packageNames`**:
   - Filters events to only declared packages to reduce system battery drain. Currently contains: `com.google.android.youtube`, `com.google.android.youtube.tv`, `com.instagram.android`, `com.zhiliaoapp.musically`. (Scope constraint requires focusing exclusively on `com.google.android.youtube`).

---

## 4. Architectural Analysis & Event Flow

### 4.1 Architectural Components & Separation of Concerns

The architecture strictly decouples responsibilities across 4 discrete layers:

```
┌────────────────────────────────────────────────────────┐
│               Android System Framework                 │
│         (AccessibilityManager & WindowManager)          │
└───────────────────────────┬────────────────────────────┘
                            │
               AccessibilityEvent callbacks
                            ▼
┌────────────────────────────────────────────────────────┐
│             AutoScrollAccessibilityService             │
│  - Lifecycle management (onCreate, onServiceConnected) │
│  - UI status notifier (registerStatusListener)         │
│  - rootInActiveWindow acquisition                      │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
   rootNode & event                        │ trigger scroll
              ▼                            ▼
┌───────────────────────────┐    ┌───────────────────────┐
│   ShortsProgressDetector  │    │     GestureEngine     │
│ - View ID matching        │    │ - Bezier calculation  │
│ - Progress extraction     │    │ - Micro-jitter        │
│ - Gate checks (Pause/Wait)│    │ - dispatchGesture     │
│ - Debounce & cooldown     │    └───────────────────────┘
└─────────────┬─────────────┘
              │ reads config
              ▼
┌───────────────────────────┐
│       AppPreferences      │
│ - SharedPreferences       │
│ - Configurable thresholds │
└───────────────────────────┘
```

### 4.2 End-to-End Event Processing Flow

1. **System Callback**:
   - An accessibility event arrives at `AutoScrollAccessibilityService.onAccessibilityEvent(event)`.
   - The service fetches `rootInActiveWindow`. If null, drops the event immediately.
2. **Detector Gate Validation (`ShortsProgressDetector.shouldTriggerScroll`)**:
   - **Gate 1: Master switch**: `preferences.isAutoScrollEnabled` must be `true`.
   - **Gate 2: Package validation**: `isSupportedTarget(packageName)` confirms `packageName.contains("youtube")`.
   - **Gate 3: Debounce cooldown**: `now - lastScrollTriggerTime >= scrollCooldownMs` (1500ms).
   - **Gate 4: Shorts Screen Verification**:
     Checks if active window contains:
     - `com.google.android.youtube:id/reel_watch_fragment_root` OR
     - `com.google.android.youtube:id/reel_recycler` OR
     - `com.google.android.youtube:id/reel_player_progress_bar`
   - **Gate 5: Smart Pause - Comments Drawer**:
     Inspects hierarchy for comment drawer IDs:
     - `com.google.android.youtube:id/comment_sheet`
     - `com.google.android.youtube:id/comments_header`
     - `com.google.android.youtube:id/design_bottom_sheet`
     - `com.google.android.youtube:id/panel_header`
     If present and `preferences.pauseOnComments == true`, returns `false`.
   - **Gate 6: Smart Pause - Video Paused State**:
     Inspects hierarchy for text or `contentDescription` matching `"Play video"`. If found (meaning the toggle button is in the play state because video is paused), returns `false`.
   - **Gate 7: Playback Progress Evaluation**:
     - Extracts `AccessibilityNodeInfo` for `com.google.android.youtube:id/reel_player_progress_bar`.
     - Reads `RangeInfo`: calculates `progressRatio = (current - min) / (max - min)`.
     - Fallback: Recursively scans nodes for `RangeInfo` or regex-parses content descriptions (e.g., `"0:15 of 0:45"`).
     - Triggers completion if:
       - **Near-end**: `progress >= 0.985f` (98.5%)
       - **Loop-wraparound**: `lastObservedProgress >= 0.88f` and `progress <= 0.12f`
     - Evaluates required loops: `currentLoopCount >= preferences.loopCountRequired`.
     - Fallback Watchdog: If progress bar is missing (e.g. sponsor/ad segments), triggers if elapsed time $\ge$ `preferences.fallbackTimeoutSeconds` (65s).
3. **Gesture Dispatch (`GestureEngine.performScrollUp`)**:
   - Concurrency guard: Checks `isDispatching` flag.
   - Calculates coordinates:
     - Screen width & height retrieved from `service.resources.displayMetrics`.
     - `startX = width * 0.5f + microJitter`, `startY = height * 0.78f`.
     - `endX = width * 0.5f + 0.5 * microJitter`, `endY = height * 0.22f`.
     - Quadratic Bezier control point: `controlX = startX + microJitter`, `controlY = (startY + endY) * 0.5f`.
   - Builds `GestureDescription.StrokeDescription` with randomized duration ($280\text{--}330\text{ ms}$).
   - Calls `service.dispatchGesture(gesture, callback, null)`.
   - On completion or cancellation, clears `isDispatching` and invokes `onComplete`.

---

## 5. Current State of Testing Infrastructure

- **Unit Tests**: None. `app/src/test` does not exist.
- **Instrumented Tests**: None. `app/src/androidTest` does not exist.
- **Dependencies**: No testing dependencies declared in `app/build.gradle.kts` (e.g. no `junit`, `mockk`, `robolectric`, or `androidx.test`).
- **Runner Configuration**: `testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"` is specified in `defaultConfig`, but the artifact itself is omitted from `dependencies`.

---

## 6. Key Observations & Optimization Opportunities

1. **Debounce Cooldown Latency (R3)**:
   - `scrollCooldownMs` is set to `1500L` ms. While this prevents double-swiping, it could potentially delay detection if a very short video finishes quickly, or introduce an artificial barrier.
   - The threshold `progress >= 0.985f` is calibrated to $98.5\%$. The user requirements explicitly ask for transition as soon as video reaches completion ($\ge 98\%$) with latency under 300ms.
2. **Gesture Duration (R2 & R3)**:
   - `Random.nextLong(280, 330)` ms duration produces a smooth flick, but can be fine-tuned along with touch velocity to match Instagram's native auto-advance speed.
3. **Logcat Tags**:
   - Tags in use: `DoomScroller-Service`, `DoomScroller-Detector`, `DoomScroller-Gesture`. Matches the acceptance criteria filter `logcat -s DoomScroller-Service DoomScroller-Detector DoomScroller-Gesture`.
4. **Scope Constraint Alignment**:
   - `accessibility_service_config.xml` includes `com.instagram.android` and `com.zhiliaoapp.musically`.
   - While harmless if those apps are not in foreground, keeping strictly to the scope constraint (`com.google.android.youtube`) simplifies event filtering and reduces unnecessary CPU cycles.
5. **Connected Target Device**:
   - Active device on wireless ADB: `192.168.1.40:5555` (`SM_E146B`, Samsung Galaxy F14 5G, device `r0s`).
   - App package `com.doomscroller.app` is already installed and its accessibility service enabled.

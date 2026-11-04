# Project: DoomScroller

## Architecture
DoomScroller is an Android accessibility service engineered for hands-free automated scrolling of short-form video feeds, exclusively targeted at YouTube Shorts (`com.google.android.youtube`).

### Core Architecture Components:
- **`AutoScrollAccessibilityService`**: Event reception pipeline handling `AccessibilityEvent` streams (`typeWindowContentChanged`, `typeWindowStateChanged`, `typeViewScrolled`). Manages service lifecycle and dispatches to detector.
- **`ShortsProgressDetector`**: Evaluates UI node hierarchy, extracts playback progress from `reel_time_bar` and TalkBack time strings, tracks state across uneven video durations, evaluates completion thresholds ($\ge 98\%$), and handles smart pause gating.
- **`GestureEngine`**: Constructs and injects programmatic swipe gestures via `AccessibilityService.dispatchGesture`, tuned for Android 14 gesture navigation.
- **`AppPreferences`**: Configuration repository for runtime toggles (auto-scroll enabled, smart pause, cooldowns, watchdog timeouts).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Reel Time Bar Node Discovery | Discover `com.google.android.youtube:id/reel_time_bar` and child `SeekBar` nodes | M1 | Survey (explorer_survey_2, 3) |
| 2 | TalkBack Time String Parser | Parse natural language duration strings (`"X minutes Y seconds of Z minutes W seconds"`, etc.) into accurate progress float | M1 | Survey (explorer_survey_2, 3) |
| 3 | Uneven Duration & Wraparound Detection | Detect completion ($\ge 98\%$) and loop wraparounds reliably across short (<15s), medium (~30s), and long (~60s) clips | M1 | ORIGINAL_REQUEST R1 |
| 4 | Snappy Vertical Flick Gesture | Straight vertical swipe (`lineTo`) with 150-180ms duration preventing Android 14 gesture navigation cancellation | M2 | ORIGINAL_REQUEST R2, Survey |
| 5 | Debounce & Cooldown Tuning | 800ms debounce cooldown preventing duplicate swipes or over-scrolls | M2 | ORIGINAL_REQUEST R2, R3 |
| 6 | Sub-300ms Transition Latency | Optimize event notification timeout (16ms) and direct node lookup to transition within <300ms upon $\ge 98\%$ completion | M3 | ORIGINAL_REQUEST R3 |
| 7 | Scope Enforcement | Restrict package filtering in config strictly to `com.google.android.youtube` | M3 | ORIGINAL_REQUEST Scope Constraint |
| 8 | Comments Drawer Smart Pause | Detect open comments drawer with `isVisibleToUser` verification and pause auto-scrolling | M4 | ORIGINAL_REQUEST R4 |
| 9 | Manual Pause & Resume Gating | Pause auto-advance when user taps pause ("Play video" state) and resume when video plays | M4 | ORIGINAL_REQUEST R4 |
| 10 | Session Watchdog Pause Protection | Freeze/reset session timer during comments or manual pause to prevent false auto-advancing upon closing drawer | M4 | Survey (explorer_survey_2, 3) |
| 11 | Live Device E2E Verification | End-to-end automated verification of at least 3 consecutive YouTube Shorts of differing durations on `192.168.1.40:5555` | M5 | ORIGINAL_REQUEST Acceptance Criteria |
| 12 | Zero Crash Loops | Verify zero unhandled exceptions or crash loops across `DoomScroller-Service`, `DoomScroller-Detector`, `DoomScroller-Gesture` | M5 | ORIGINAL_REQUEST Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Detection & Time String Parser | `ShortsProgressDetector.kt` view discovery, TalkBack natural language parser, $\ge 98\%$ threshold, wraparound handling | none | DONE (Gate passed, 11,097 fuzzer tests passed) |
| M2 | Gesture Dispatch & Flick Tuning | `GestureEngine.kt` straight vertical flick, 150-180ms duration, coordinate safety, 800ms cooldown | M1 | DONE (Gate passed, 17/17 adversarial tests passed) |
| M3 | Latency Optimization & Scope Enforcement | `accessibility_service_config.xml` 16ms timeout, YouTube-only package filter, direct node lookup optimization | M1, M2 | DONE (Gate passed, latency < 200ms) |
| M4 | Smart Pause & State Protection | `ShortsProgressDetector.kt` `isVisibleToUser` comments check, play/pause state handling, watchdog timer freeze | M1 | DONE (Gate passed, watchdog freeze verified) |
| M5 | Live Verification, E2E Tests & Hardening | Cloud APK build via GitHub Actions, ADB deployment to `192.168.1.40:5555`, 100% E2E test pass, forensic audit | M1, M2, M3, M4 | READY (TEST_READY.md published, awaiting user freeze clearance for ADB) |

## Interface Contracts
### `ShortsProgressDetector` $\leftrightarrow$ `AutoScrollAccessibilityService`
- Signature: `fun shouldTriggerScroll(root: AccessibilityNodeInfo, event: AccessibilityEvent?): Boolean`
- Precondition: `root` is non-null root in active window; event package is `com.google.android.youtube`.
- Postcondition: Returns `true` if and only if video progress $\ge 0.98f$ or valid loop wraparound occurs, and auto-scroll is not paused (comments drawer closed, video not paused).
- Latency target: $<10$ms execution per evaluation.

### `GestureEngine` $\leftrightarrow$ `AutoScrollAccessibilityService`
- Signature: `fun performScrollUp(onComplete: (() -> Unit)? = null): Boolean`
- Mechanism: Dispatches vertical `GestureDescription` with `Path.lineTo` from $(width \times 0.5, height \times 0.75)$ to $(width \times 0.5, height \times 0.25)$ in $150\text{--}180$ms.
- Postcondition: System fires callback without cancellation; invokes `onComplete`.

## Code Layout
- `app/src/main/java/com/doomscroller/app/detector/ShortsProgressDetector.kt`: Playback and pause state detector (Owned by M1, M4)
- `app/src/main/java/com/doomscroller/app/service/GestureEngine.kt`: Swipe injection engine (Owned by M2)
- `app/src/main/res/xml/accessibility_service_config.xml`: Accessibility service configuration (Owned by M3)
- `app/src/main/java/com/doomscroller/app/service/AutoScrollAccessibilityService.kt`: Service entry and event coordinator
- `app/src/main/java/com/doomscroller/app/data/AppPreferences.kt`: User settings repository
- `.github/workflows/build.yml`: Cloud APK build pipeline
- `e2e/`: E2E test scripts and automated verification runner (Owned by E2E Testing Track)

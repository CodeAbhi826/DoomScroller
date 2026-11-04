# E2E Test Infra: DoomScroller

## Test Philosophy
- Opaque-box, requirement-driven testing against live connected device `192.168.1.40:5555`.
- Verification relies on observable runtime signals: ADB commands, `uiautomator dump`, and logcat tags (`DoomScroller-Service`, `DoomScroller-Detector`, `DoomScroller-Gesture`).
- Independent of internal class implementation details.

## Feature Inventory & Test Coverage Mapping
| # | Feature | Source (Requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|----------------------|:------:|:------:|:------:|:------:|
| 1 | Reel Time Bar Node Discovery | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ | ✓ |
| 2 | TalkBack Time String Parser | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ | ✓ |
| 3 | Uneven Duration & Wraparound (<15s, ~30s, ~60s) | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ | ✓ |
| 4 | Snappy Vertical Flick Gesture | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ | ✓ |
| 5 | Debounce & Cooldown Tuning | ORIGINAL_REQUEST R2, R3 | 5 | 5 | ✓ | ✓ |
| 6 | Sub-300ms Transition Latency | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ | ✓ |
| 7 | Scope Enforcement (`com.google.android.youtube`) | Scope Constraint | 5 | 5 | ✓ | ✓ |
| 8 | Comments Drawer Smart Pause | ORIGINAL_REQUEST R4 | 5 | 5 | ✓ | ✓ |
| 9 | Manual Pause & Resume Gating | ORIGINAL_REQUEST R4 | 5 | 5 | ✓ | ✓ |
| 10 | Session Watchdog Pause Protection | ORIGINAL_REQUEST R4 | 5 | 5 | ✓ | ✓ |
| 11 | Live 3+ Consecutive Auto-Advances | Acceptance Criteria | 5 | 5 | ✓ | ✓ |
| 12 | Zero Crash Loops / Exceptions | Acceptance Criteria | 5 | 5 | ✓ | ✓ |

## Test Architecture
- **Target Device**: `192.168.1.40:5555` (Samsung Galaxy F14 5G, Android 14)
- **Runner**: Shell / Python test harnesses running against `adb -s 192.168.1.40:5555`
- **Pass / Fail Semantics**:
  - Auto-advance triggers upon $\ge 98\%$ video completion.
  - Video transition latency $<300$ms.
  - Opening comments pauses scrolling; closing resumes.
  - At least 3 consecutive YouTube Shorts advance without human interaction.
  - Zero crashes or uncaught exceptions in logcat.

## Test Tiers & Scenarios

### Tier 1: Feature Coverage (>=5 per feature)
- T1.1: Short clip playback detection (<15s clip)
- T1.2: Medium clip playback detection (~30s clip)
- T1.3: Long clip playback detection (~60s clip)
- T1.4: Progress string parsing with minutes and seconds
- T1.5: Progress string parsing with seconds only
- T1.6: Progress string parsing with standard mm:ss
- T1.7: Upward flick gesture injection and verification
- T1.8: Debounce cooldown enforcement
- T1.9: Comments drawer opening detection
- T1.10: Manual pause state ("Play video") detection

### Tier 2: Boundary & Corner Cases (>=5 per feature)
- T2.1: Very short clip (<7s) wraparound detection without watchdog
- T2.2: Long clip (>60s) progress monitoring across multiple segments
- T2.3: Video looping back to 0% after reaching 99% before next frame
- T2.4: Rapid opening and closing of comments drawer
- T2.5: Comments drawer remaining open longer than 65s without watchdog auto-advancing
- T2.6: Mid-video manual pause remaining paused indefinitely without scroll
- T2.7: Rapid consecutive events within debounce window (no double swipe)

### Tier 3: Cross-Feature Combinations (Pairwise Coverage)
- T3.1: Comments drawer opened while video is at 95% completion (must NOT trigger scroll at 98%)
- T3.2: Comments drawer closed after video reached end (resumes cleanly on next loop)
- T3.3: Manual pause engaged at 99% progress (must NOT scroll while paused)
- T3.4: Manual resume at 99% progress (scrolls immediately upon playback resumption)
- T3.5: Navigating to next Short immediately after manual scroll (debounce holds)

### Tier 4: Real-World Application Workload Scenarios
- T4.1: Continuous hands-free auto-scrolling across 3 consecutive YouTube Shorts of varying lengths (<15s, ~30s, ~60s)
- T4.2: Measurement of transition latency from $\ge 98\%$ completion to swipe injection (<300ms)
- T4.3: Smart Pause live user simulation: user opens comments on Short #2 for 10s, closes it, auto-advance resumes
- T4.4: Device health verification: continuous logcat check during playback showing zero exceptions or crash loops

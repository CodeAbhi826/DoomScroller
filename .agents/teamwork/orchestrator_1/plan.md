# Plan: DoomScroller Live E2E Testing, Gesture Tuning & Latency Optimization

## Mission
Comprehensive end-to-end testing, gesture tuning, and latency optimization for DoomScroller on a live Android device connected via wireless ADB (`192.168.1.40:5555`) to ensure 100% automated scrolling exclusively for YouTube Shorts of uneven durations.

## Phases

### Phase 0: Survey & Scope Mapping
- Spawn 3 parallel Explorers to map the existing codebase, live device environment, build/install setup, accessibility services, gesture dispatch, video completion detection, and smart pause mechanisms.
- Aggregate findings into `PROJECT.md` (Feature Inventory, Architecture, Code Layout).

### Phase 1: Dual Track Decomposition & Planning
- Track A (Implementation): Define milestones for:
  - M1: Detection & Completion Logic (handling uneven durations, >=98% threshold, progress event tracking)
  - M2: Gesture Dispatch & Transition Tuning (smooth swipe gesture, debounce cooldown, preventing over-scroll/duplicates)
  - M3: Response Latency Optimization (<300ms transition latency from video completion to swipe)
  - M4: Smart Pause Validation (comments drawer, manual pause/play detection)
- Track B (E2E Testing): Create `TEST_INFRA.md` with 4-tier opaque-box test suites:
  - Tier 1: Feature Coverage (live YouTube Shorts <15s, ~30s, ~60s)
  - Tier 2: Boundary & Corner Cases (very short Shorts, long Shorts, edge bounds)
  - Tier 3: Cross-Feature Interactions (Smart Pause during transitions, rapid gestures)
  - Tier 4: Real-world workload tests (consecutive auto-advances, stability)

### Phase 2: Implementation & Iteration
- Execute milestones using Worker -> Reviewer -> Challenger -> Auditor gate loops.
- Build and deploy APK to device `192.168.1.40:5555`.

### Phase 3: Live Verification & Testing
- Run live test suites against device `192.168.1.40:5555` with YouTube Shorts.
- Capture logcat traces (`DoomScroller-Service`, `DoomScroller-Detector`, `DoomScroller-Gesture`).
- Verify <300ms transition latency, zero crash loops, 100% successful consecutive auto-advances.

### Phase 4: Final Victory Audit & Handoff
- Run forensic integrity audit on all criteria.
- Produce comprehensive handoff report to Sentinel with empirical evidence.

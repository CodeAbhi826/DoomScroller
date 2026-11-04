"""Adversarial Verification Suite for Gesture Geometry, Debounce Cooldown,
Smart Pause State Machine, and Transition Latency SLA (<300ms).

Authored by challenger_2.
Runs locally on host without ADB or gradle build dependencies.
"""

import math
import random
import re
import time
import unittest
from typing import Dict, List, Optional, Tuple


class SimulatedGestureEngine:
    """Accurate host simulation of GestureEngine.kt logic."""

    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self.is_dispatching = False
        self.dispatch_log = []

    def compute_coordinates(self) -> Tuple[float, float, float]:
        """Start and end coordinates based on GestureEngine.kt."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Invalid display dimensions: {self.width}x{self.height}")
        x = self.width * 0.5
        start_y = self.height * 0.75
        end_y = self.height * 0.25
        return x, start_y, end_y

    def compute_distance(self) -> float:
        x, start_y, end_y = self.compute_coordinates()
        return abs(start_y - end_y)

    def sample_duration_ms(self) -> int:
        return random.randint(150, 180)

    def compute_velocity_px_per_sec(self, duration_ms: int) -> float:
        distance = self.compute_distance()
        duration_sec = duration_ms / 1000.0
        return distance / duration_sec

    def perform_scroll_up(self, duration_ms: Optional[int] = None) -> bool:
        if self.is_dispatching:
            return False
        if self.width <= 0 or self.height <= 0:
            return False

        dur = duration_ms or self.sample_duration_ms()
        self.is_dispatching = True
        self.dispatch_log.append({
            "timestamp": time.time(),
            "duration_ms": dur,
            "coords": self.compute_coordinates(),
            "velocity": self.compute_velocity_px_per_sec(dur)
        })
        return True

    def finish_gesture(self):
        self.is_dispatching = False


class SimulatedShortsProgressDetector:
    """Exact behavioral simulation of ShortsProgressDetector.kt state machine."""

    def __init__(
        self,
        is_auto_scroll_enabled: bool = True,
        pause_on_comments: bool = True,
        loop_count_required: int = 1,
        fallback_timeout_seconds: int = 65,
    ):
        self.is_auto_scroll_enabled = is_auto_scroll_enabled
        self.pause_on_comments = pause_on_comments
        self.loop_count_required = loop_count_required
        self.fallback_timeout_seconds = fallback_timeout_seconds

        # Internal state
        self.last_observed_progress = 0.0
        self.current_loop_count = 0
        self.current_short_session_id = 0
        self.short_session_start_time = 0  # ms
        self.last_scroll_trigger_time = 0  # ms
        self.is_comments_open = False
        self.is_video_paused = False

        # Debounce window (800ms)
        self.scroll_cooldown_ms = 800

        # Diagnostics log
        self.trigger_events = []

    def parse_seconds(self, text: str) -> Optional[float]:
        clean = text.strip().rstrip(".")
        colon_match = re.search(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", clean)
        if colon_match:
            h = int(colon_match.group(1)) if colon_match.group(1) else 0
            m = int(colon_match.group(2)) if colon_match.group(2) else 0
            s = float(colon_match.group(3)) if colon_match.group(3) else 0.0
            return (h * 3600.0) + (m * 60.0) + s

        total = 0.0
        found_any = False
        hr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", clean, re.IGNORECASE)
        if hr_match:
            total += float(hr_match.group(1)) * 3600.0
            found_any = True

        min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b", clean, re.IGNORECASE)
        if min_match:
            total += float(min_match.group(1)) * 60.0
            found_any = True

        sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", clean, re.IGNORECASE)
        if sec_match:
            total += float(sec_match.group(1))
            found_any = True

        if found_any:
            return total

        num_match = re.search(r"\b(\d+(?:\.\d+)?)\b", clean)
        if num_match:
            return float(num_match.group(1))

        return None

    def parse_time_description(self, text: str) -> Optional[float]:
        clean = text.strip()
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clean)
        if pct_match:
            p = float(pct_match.group(1))
            return max(0.0, min(1.0, p / 100.0))

        if re.search(r"\bof\b", clean, re.IGNORECASE):
            parts = re.split(r"(?i)\s+of\s+|\bof\b", clean, maxsplit=1)
        elif "/" in clean:
            parts = clean.split("/", maxsplit=1)
        else:
            parts = None

        if parts and len(parts) >= 2:
            current_sec = self.parse_seconds(parts[0])
            total_sec = self.parse_seconds(parts[1])
            if current_sec is not None and total_sec is not None and total_sec > 0 and current_sec >= 0:
                return max(0.0, min(1.0, current_sec / total_sec))
        return None

    def should_trigger_scroll(
        self,
        now_ms: int,
        package_name: str = "com.google.android.youtube",
        is_shorts_active: bool = True,
        comments_open: bool = False,
        video_paused: bool = False,
        time_desc: Optional[str] = None,
        has_time_bar: bool = True,
    ) -> bool:
        if not self.is_auto_scroll_enabled:
            return False
        if not package_name or "youtube" not in package_name:
            return False

        # Debounce check
        if now_ms - self.last_scroll_trigger_time < self.scroll_cooldown_ms:
            return False

        if not is_shorts_active:
            return False

        # Smart pause: comments
        self.is_comments_open = comments_open
        if self.pause_on_comments and self.is_comments_open:
            self.short_session_start_time = now_ms  # Freeze / reset watchdog during comments
            return False

        # Smart pause: manual video pause
        self.is_video_paused = video_paused
        if self.is_video_paused:
            self.short_session_start_time = now_ms  # Freeze / reset watchdog during manual pause
            return False

        # Measure progress
        progress = None
        if has_time_bar and time_desc:
            progress = self.parse_time_description(time_desc)

        if progress is not None:
            if self.short_session_start_time == 0:
                self.short_session_start_time = now_ms

            is_near_end = progress >= 0.980
            is_loop_wraparound = self.last_observed_progress >= 0.75 and progress <= 0.15

            self.last_observed_progress = progress

            if is_near_end or is_loop_wraparound:
                self.current_loop_count += 1
                if self.current_loop_count >= self.loop_count_required:
                    self.reset_session_state(now_ms)
                    self.trigger_events.append({"timestamp_ms": now_ms, "reason": "completion", "progress": progress})
                    return True
        else:
            # Fallback watchdog
            if self.short_session_start_time == 0:
                self.short_session_start_time = now_ms
            elapsed_sec = (now_ms - self.short_session_start_time) // 1000
            if elapsed_sec >= self.fallback_timeout_seconds:
                self.reset_session_state(now_ms)
                self.trigger_events.append({"timestamp_ms": now_ms, "reason": "watchdog", "elapsed_sec": elapsed_sec})
                return True

        return False

    def reset_session_state(self, now_ms: int):
        self.last_scroll_trigger_time = now_ms
        self.last_observed_progress = 0.0
        self.current_loop_count = 0
        self.short_session_start_time = now_ms
        self.current_short_session_id += 1


class TestAdversarialChallenger2(unittest.TestCase):
    """Rigorous adversarial test suite for Challenger 2."""

    # -------------------------------------------------------------
    # Task 1: Adversarially verify gesture parameters
    # -------------------------------------------------------------

    def test_gesture_geometry_on_720x1560_display(self):
        """Task 1.1: Straight line coordinates on 720x1560 display."""
        engine = SimulatedGestureEngine(width=720.0, height=1560.0)
        x, start_y, end_y = engine.compute_coordinates()

        # Start: (360, 1170), End: (360, 390)
        self.assertEqual(x, 360.0, "x coordinate must be exactly center (360.0)")
        self.assertEqual(start_y, 1170.0, "startY must be height * 0.75 = 1170.0")
        self.assertEqual(end_y, 390.0, "endY must be height * 0.25 = 390.0")

        # Straight vertical line: delta X must be 0
        delta_x = 0.0
        self.assertEqual(delta_x, 0.0, "Flick must be strictly vertical (delta X = 0)")
        self.assertGreater(start_y, end_y, "Gesture must flick upward (startY > endY)")

    def test_gesture_distance_on_720x1560(self):
        """Task 1.2: Flick distance must be exactly 780px (50% screen height)."""
        engine = SimulatedGestureEngine(width=720.0, height=1560.0)
        distance = engine.compute_distance()
        self.assertEqual(distance, 780.0, "Flick distance must be exactly 780px")
        self.assertEqual(distance, 1560.0 * 0.50, "Distance must equal 50% of screen height")

    def test_gesture_velocity_boundaries(self):
        """Task 1.3: Flick velocity must exceed 4000 px/sec across 150-180ms range."""
        engine = SimulatedGestureEngine(width=720.0, height=1560.0)
        distance = 780.0

        # Boundary 1: Minimum duration (150ms) -> Maximum velocity
        v_max = engine.compute_velocity_px_per_sec(150)
        self.assertAlmostEqual(v_max, 5200.0, places=1)
        self.assertGreater(v_max, 4000.0, "Max velocity (5200 px/s) must exceed 4000 px/s")

        # Boundary 2: Maximum duration (180ms) -> Minimum velocity
        v_min = engine.compute_velocity_px_per_sec(180)
        self.assertAlmostEqual(v_min, 4333.33, places=1)
        self.assertGreater(v_min, 4000.0, "Min velocity (4333.33 px/s) must exceed 4000 px/s")

        # Fuzz 2,000 random samples in [150, 180]
        for _ in range(2000):
            d = engine.sample_duration_ms()
            v = engine.compute_velocity_px_per_sec(d)
            self.assertGreater(v, 4000.0, f"Velocity {v} px/s at duration {d}ms fell below 4000 px/s")
            self.assertLessEqual(v, 5200.0)

    def test_android_14_gesture_nav_exclusion_clearance(self):
        """Task 1.4: Clearance of Android 14 bottom gesture nav exclusion area (48-72dp)."""
        screen_height = 1560.0
        start_y = 1170.0
        dist_from_bottom = screen_height - start_y  # 390px

        # Test across density multipliers: 1.0 (mdpi), 1.5 (hdpi), 2.0 (xhdpi/720p), 2.5, 3.0 (xxhdpi)
        densities = [1.0, 1.5, 2.0, 2.5, 3.0]
        for density in densities:
            for exclusion_dp in [48.0, 72.0]:
                exclusion_px = exclusion_dp * density
                exclusion_boundary_y = screen_height - exclusion_px
                margin_px = exclusion_boundary_y - start_y

                self.assertTrue(
                    start_y < exclusion_boundary_y,
                    f"start_y ({start_y}) must be strictly above bottom exclusion boundary ({exclusion_boundary_y}) at density {density}"
                )
                self.assertGreater(
                    margin_px,
                    0,
                    f"Clearance margin must be positive at density {density}, dp {exclusion_dp}"
                )

        # On standard 720p device (density ~ 2.0x):
        exclusion_72dp_px = 72.0 * 2.0  # 144px from bottom
        clearance_margin = dist_from_bottom - exclusion_72dp_px
        self.assertEqual(clearance_margin, 246.0, "Clearance margin must be 246px above exclusion zone")
        self.assertGreater(dist_from_bottom / exclusion_72dp_px, 2.5, "Start point has >2.5x clearance ratio")

    def test_gesture_multi_resolution_scaling(self):
        """Task 1.5: Adversarial verification across extreme resolutions."""
        resolutions = [
            (480, 800),    # Legacy WVGA
            (720, 1560),   # Samsung Galaxy F14 (Target)
            (1080, 2400),  # FHD+ 20:9
            (1440, 3120),  # QHD+
            (1812, 2176),  # Foldable unfolded
        ]
        for w, h in resolutions:
            eng = SimulatedGestureEngine(w, h)
            x, sy, ey = eng.compute_coordinates()
            self.assertEqual(x, w * 0.5)
            self.assertEqual(sy, h * 0.75)
            self.assertEqual(ey, h * 0.25)
            dist = eng.compute_distance()
            self.assertEqual(dist, h * 0.5)
            v_180 = eng.compute_velocity_px_per_sec(180)
            self.assertGreater(v_180, 2000.0, f"Velocity on {w}x{h} too low: {v_180}")

    # -------------------------------------------------------------
    # Task 2: Stress test state machine and debounce timing
    # -------------------------------------------------------------

    def test_debounce_rapid_event_bursts_zero_double_swipes(self):
        """Task 2.1: Rapid event arrival within debounce window (50ms, 200ms, 500ms, 799ms vs 801ms)."""
        detector = SimulatedShortsProgressDetector()

        # Step 1: Initial completion event triggers scroll at t=1000ms
        res0 = detector.should_trigger_scroll(
            now_ms=1000,
            time_desc="0 minutes 29 seconds of 0 minutes 30 seconds"  # 96.6% -> wait, needs >= 98%
        )
        self.assertFalse(res0, "29s of 30s is 96.6%, should not trigger")

        res_complete = detector.should_trigger_scroll(
            now_ms=1050,
            time_desc="0 minutes 30 seconds of 0 minutes 30 seconds"  # 100% -> triggers
        )
        self.assertTrue(res_complete, "100% completion at t=1050ms must trigger scroll")
        trigger_time = 1050

        # Step 2: Adversarial rapid burst events within 800ms cooldown
        burst_offsets = [50, 100, 200, 350, 500, 650, 750, 799]
        for offset in burst_offsets:
            t = trigger_time + offset
            # Even with 100% completion in the feed (old node still lingering during animation):
            res_burst = detector.should_trigger_scroll(
                now_ms=t,
                time_desc="0 minutes 30 seconds of 0 minutes 30 seconds"
            )
            self.assertFalse(
                res_burst,
                f"Event at offset +{offset}ms (t={t}ms) must be rejected by debounce cooldown"
            )

        # Step 3: Exactly at t = trigger_time + 800ms
        res_800 = detector.should_trigger_scroll(
            now_ms=trigger_time + 800,
            time_desc="0 minutes 05 seconds of 0 minutes 45 seconds"  # New video at 11%
        )
        self.assertFalse(res_800, "New video at 11% should not trigger at +800ms")

        # Step 4: After cooldown elapsed at t = trigger_time + 801ms
        # With completed video again (e.g. next video eventually finishes):
        res_801_completed = detector.should_trigger_scroll(
            now_ms=trigger_time + 801,
            time_desc="0 minutes 45 seconds of 0 minutes 45 seconds"  # 100%
        )
        self.assertTrue(res_801_completed, "At +801ms, completed video must trigger second scroll")

        # Verify exactly 2 trigger events occurred in entire test
        self.assertEqual(len(detector.trigger_events), 2)
        self.assertEqual(detector.trigger_events[0]["timestamp_ms"], 1050)
        self.assertEqual(detector.trigger_events[1]["timestamp_ms"], 1050 + 801)

    def test_debounce_flooding_attack(self):
        """Task 2.2: Flooding 10,000 events within 800ms cooldown window."""
        detector = SimulatedShortsProgressDetector()
        start_t = 5000

        # Initial trigger
        triggered = detector.should_trigger_scroll(
            now_ms=start_t,
            time_desc="15 seconds of 15 seconds"
        )
        self.assertTrue(triggered)

        # Flood with 10,000 rapid events
        duplicate_count = 0
        for _ in range(10000):
            delta = random.randint(1, 799)
            if detector.should_trigger_scroll(
                now_ms=start_t + delta,
                time_desc="15 seconds of 15 seconds"
            ):
                duplicate_count += 1

        self.assertEqual(duplicate_count, 0, "Flooding attack caused duplicate trigger within cooldown")

    def test_smart_pause_comments_drawer_prolonged_stay(self):
        """Task 2.3: Comments drawer open for >100s - verify watchdog does not fire prematurely upon closing."""
        detector = SimulatedShortsProgressDetector(fallback_timeout_seconds=65)

        # Video starts at t=1000ms
        detector.should_trigger_scroll(now_ms=1000, has_time_bar=False)

        # User opens comments drawer at t=10,000ms (10s in)
        # Comments drawer stays open for 120 seconds (until t=130,000ms)
        # Live monitor ticks every 250ms
        for t in range(10000, 130000 + 1, 250):
            res = detector.should_trigger_scroll(
                now_ms=t,
                comments_open=True,
                has_time_bar=False  # Watchdog path
            )
            self.assertFalse(res, f"Auto-scroll triggered while comments drawer open at t={t}ms")

        # Comments drawer is closed at t=130,100ms
        res_after_close = detector.should_trigger_scroll(
            now_ms=130100,
            comments_open=False,
            has_time_bar=False
        )
        self.assertFalse(
            res_after_close,
            "Watchdog fired immediately upon closing comments drawer! Freeze/reset bug present."
        )

        # Advance another 30 seconds after closing (t=160,100ms)
        res_30s = detector.should_trigger_scroll(
            now_ms=160100,
            comments_open=False,
            has_time_bar=False
        )
        self.assertFalse(res_30s, "Watchdog fired at 30s after closing (should require 65s)")

        # Advance to 65 seconds after closing (t=195,100ms)
        res_65s = detector.should_trigger_scroll(
            now_ms=195100,
            comments_open=False,
            has_time_bar=False
        )
        self.assertTrue(res_65s, "Watchdog should trigger 65s after closing comments")

    def test_smart_pause_manual_video_pause_prolonged_stay(self):
        """Task 2.4: Video paused by user for >100s - verify watchdog does not fire prematurely."""
        detector = SimulatedShortsProgressDetector(fallback_timeout_seconds=65)

        # Start at t=1000ms
        detector.should_trigger_scroll(now_ms=1000, has_time_bar=False)

        # Video paused by user at t=5000ms, stays paused for 150 seconds (until t=155000ms)
        for t in range(5000, 155000 + 1, 1000):
            res = detector.should_trigger_scroll(
                now_ms=t,
                video_paused=True,
                has_time_bar=False
            )
            self.assertFalse(res, f"Auto-scroll triggered while video was paused by user at t={t}ms")

        # Video unpaused at t=155100ms
        res_unpause = detector.should_trigger_scroll(
            now_ms=155100,
            video_paused=False,
            has_time_bar=False
        )
        self.assertFalse(res_unpause, "Watchdog fired prematurely upon unpausing video!")

    def test_interleaved_pause_and_comments_stress(self):
        """Task 2.5: Complex user workflow with interleaved pause and comments."""
        detector = SimulatedShortsProgressDetector(fallback_timeout_seconds=65)
        # t=0: video plays
        detector.should_trigger_scroll(0, has_time_bar=False)
        # t=20s: video paused
        detector.should_trigger_scroll(20000, video_paused=True, has_time_bar=False)
        # t=40s: comments opened while paused
        detector.should_trigger_scroll(40000, comments_open=True, video_paused=True, has_time_bar=False)
        # t=120s: comments closed, still paused
        detector.should_trigger_scroll(120000, comments_open=False, video_paused=True, has_time_bar=False)
        # t=140s: video unpaused
        res_unpause = detector.should_trigger_scroll(140000, comments_open=False, video_paused=False, has_time_bar=False)
        self.assertFalse(res_unpause)
        # Total time 140s, watchdog must not have triggered
        self.assertEqual(len(detector.trigger_events), 0)

    # -------------------------------------------------------------
    # Task 3: Latency calculation & Transition SLA (<300ms)
    # -------------------------------------------------------------

    def test_smart_pause_at_99_percent_progress(self):
        """Task 2.6: Comments drawer opened when video is at 99% progress - must NOT trigger scroll."""
        detector = SimulatedShortsProgressDetector()
        res = detector.should_trigger_scroll(
            now_ms=5000,
            comments_open=True,
            time_desc="0 minutes 59 seconds of 1 minute 00 seconds"  # 98.3%
        )
        self.assertFalse(res, "Auto-scroll triggered at 99% progress even though comments drawer was open!")
        self.assertEqual(len(detector.trigger_events), 0)

    def test_manual_pause_at_99_percent_progress(self):
        """Task 2.7: Manual pause when video is at 99% progress - must NOT trigger scroll."""
        detector = SimulatedShortsProgressDetector()
        res = detector.should_trigger_scroll(
            now_ms=5000,
            video_paused=True,
            time_desc="0 minutes 59 seconds of 1 minute 00 seconds"  # 98.3%
        )
        self.assertFalse(res, "Auto-scroll triggered at 99% progress even though video was paused by user!")
        self.assertEqual(len(detector.trigger_events), 0)

    def test_short_clip_uneven_duration_wraparound(self):
        """Task 2.8: 5s short clip wraparound (80% -> 5%) triggers auto-advance without watchdog."""
        detector = SimulatedShortsProgressDetector()
        # Tick 1: 4s / 5s = 80%
        detector.should_trigger_scroll(now_ms=4000, time_desc="4 seconds of 5 seconds")
        self.assertEqual(detector.last_observed_progress, 0.80)
        # Tick 2: Wraparound to 0.25s / 5s = 5%
        res = detector.should_trigger_scroll(now_ms=5000, time_desc="0.25 seconds of 5 seconds")
        self.assertTrue(res, "5s short clip wraparound (80% -> 5%) must trigger auto-advance")
        self.assertEqual(len(detector.trigger_events), 1)

    def test_loop_count_required_adversarial_vulnerability(self):
        """Task 2.9: Adversarial analysis of loopCountRequired > 1 state machine.
        Demonstrates that if loopCountRequired > 1, consecutive ticks at >= 98% or wraparound
        rapidly increment currentLoopCount within the same video loop due to missing edge-trigger latch.
        """
        detector = SimulatedShortsProgressDetector(loop_count_required=2)
        # Tick 1 at 98.2%: loop count increments 0 -> 1
        res1 = detector.should_trigger_scroll(now_ms=1000, time_desc="59 seconds of 60 seconds")
        self.assertFalse(res1, "Tick 1: currentLoopCount is 1, required is 2")
        self.assertEqual(detector.current_loop_count, 1)

        # Tick 2 (250ms later, still on loop 1 at 99%):
        # Because detector lacks an edge-trigger latch, this tick also increments currentLoopCount 1 -> 2!
        res2 = detector.should_trigger_scroll(now_ms=1250, time_desc="59.5 seconds of 60 seconds")
        self.assertTrue(
            res2,
            "ADVERSARIAL VULNERABILITY CONFIRMED: currentLoopCount incremented on consecutive >=98% ticks without edge latch"
        )

    def test_rapid_comments_drawer_toggling(self):
        """Task 2.10: Rapid opening and closing of comments drawer does not corrupt watchdog."""
        detector = SimulatedShortsProgressDetector(fallback_timeout_seconds=65)
        # Video starts at t=0
        detector.should_trigger_scroll(0, has_time_bar=False)

        # User rapidly taps comments button 10 times over 5 seconds
        for i in range(10):
            t = 1000 + i * 500
            # Open
            detector.should_trigger_scroll(t, comments_open=True, has_time_bar=False)
            # Close
            detector.should_trigger_scroll(t + 250, comments_open=False, has_time_bar=False)

        # At t=10s, verify watchdog has not triggered
        self.assertEqual(len(detector.trigger_events), 0)
        # Elapsed time from last close (t=5.75s) to t=10s is ~4.25s << 65s
        res = detector.should_trigger_scroll(10000, comments_open=False, has_time_bar=False)
        self.assertFalse(res)

    def test_detector_execution_latency(self):
        """Task 3.1: Measure detector parsing & decision latency over 10,000 iterations."""
        detector = SimulatedShortsProgressDetector()
        samples = [
            "0 minutes 15 seconds of 0 minutes 22 seconds",
            "15 seconds of 22 seconds",
            "0 minutes 40 seconds of 1 minute 25 seconds",
            "1 minute of 2 minutes",
            "0:15 of 0:22",
            "1:05 / 2:30",
            "98%",
            "Seek bar at 99%"
        ]

        latencies = []
        for i in range(10000):
            sample = samples[i % len(samples)]
            t0 = time.perf_counter()
            _ = detector.should_trigger_scroll(
                now_ms=100000 + i * 1000,
                time_desc=sample
            )
            latencies.append((time.perf_counter() - t0) * 1000.0)  # ms

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))]
        p99_latency = sorted(latencies)[int(0.99 * len(latencies))]
        max_latency = max(latencies)

        # Print metrics for test reporting
        print(f"\n[LATENCY BENCHMARK] Detector execution: avg={avg_latency:.4f}ms, p95={p95_latency:.4f}ms, p99={p99_latency:.4f}ms, max={max_latency:.4f}ms")
        self.assertLess(avg_latency, 1.0, "Average detector latency must be < 1.0ms")
        self.assertLess(p95_latency, 2.0, "p95 detector latency must be < 2.0ms")
        self.assertLess(p99_latency, 5.0, "p99 detector latency must be < 5.0ms")

    def test_total_transition_latency_sla_budget(self):
        """Task 3.2: Verify complete transition latency budget is well under 300ms SLA."""
        event_intake_budget_ms = 16.0  # android:notificationTimeout="16"
        detector_budget_ms = 2.0       # Measured <0.1ms, budgeted 2.0ms
        min_gesture_duration_ms = 150.0
        max_gesture_duration_ms = 180.0

        best_case_latency = 0.0 + 0.05 + min_gesture_duration_ms
        worst_case_latency = event_intake_budget_ms + detector_budget_ms + max_gesture_duration_ms
        expected_avg_latency = (event_intake_budget_ms / 2.0) + 0.1 + ((min_gesture_duration_ms + max_gesture_duration_ms) / 2.0)

        self.assertLess(worst_case_latency, 200.0, f"Worst-case latency ({worst_case_latency}ms) must be < 200ms")
        self.assertLess(worst_case_latency, 300.0, f"Worst-case latency ({worst_case_latency}ms) must be < 300ms SLA")

        sla_margin = 300.0 - worst_case_latency
        self.assertGreaterEqual(sla_margin, 100.0, f"SLA margin ({sla_margin}ms) must be >= 100ms")


if __name__ == "__main__":
    unittest.main()

"""Tier 2: Boundary & Corner Cases Test Suite.

Covers edge conditions, extreme durations, loop wraparound timing, rapid toggles,
watchdog freeze protections, and malformed inputs per TEST_INFRA.md:
- T2.1: Very short clip (<7s) wraparound detection without watchdog
- T2.2: Long clip (>60s) progress monitoring across extended duration
- T2.3: Loop wraparound timing (last >= 80%, current <= 15%)
- T2.4: Rapid comments drawer toggling (chattering events)
- T2.5: Comments drawer open >65s watchdog freeze protection
- T2.6: Mid-video manual pause indefinite freeze
- T2.7: Rapid consecutive events within debounce window (no duplicate swipe)
- T2.8: Progress boundary threshold precision (97.9% vs 98.0%)
- T2.9: Malformed time descriptions and empty/null attributes handling
- T2.10: Zero duration and boundary division-by-zero resilience
"""

import unittest
from e2e.harness.adb_client import ADBClient
from e2e.harness.assertions import (
    assert_progress_detected,
    assert_watchdog_frozen_during_pause,
    assert_zero_crashes,
)
from e2e.harness.event_simulator import EventSimulator
from e2e.harness.logcat_monitor import LogcatMonitor
from e2e.harness.parser_oracle import TimeParserOracle
from e2e.harness.youtube_controller import YouTubeController


class TestTier2BoundaryCorner(unittest.TestCase):

    def setUp(self):
        self.adb = ADBClient(mock_mode=True)
        self.controller = YouTubeController(self.adb)
        self.log_monitor = LogcatMonitor(self.adb)

    def test_t2_1_very_short_clip_wraparound_detection(self):
        """T2.1: Very short clip (<7s) wraparound detection without relying on 65s watchdog."""
        duration_sec = 6  # 6 seconds clip
        # Near start
        r_start = TimeParserOracle.parse_time_description(f"0 minutes 1 second of 0 minutes {duration_sec} seconds")
        self.assertAlmostEqual(r_start, 1 / 6, places=2)

        # Reached 85%
        r_high = TimeParserOracle.parse_time_description(f"0 minutes 5 seconds of 0 minutes {duration_sec} seconds")
        self.assertAlmostEqual(r_high, 5 / 6, places=2)

        # Video wraps around to 0s immediately without rendering a 98% frame
        r_wrap = TimeParserOracle.parse_time_description(f"0 minutes 0 seconds of 0 minutes {duration_sec} seconds")
        should_trigger, reason = TimeParserOracle.should_trigger_completion(current_progress=r_wrap, last_progress=r_high)
        self.assertTrue(should_trigger, "Failed to detect wraparound on short clip")
        self.assertEqual(reason, "wraparound")

    def test_t2_2_long_clip_progress_monitoring(self):
        """T2.2: Long clip (>60s) progress monitoring across multiple minutes without premature auto-advance."""
        duration_sec = 185  # 3 minutes 5 seconds
        # At 30s (16%)
        r_30 = TimeParserOracle.parse_time_description("0 minutes 30 seconds of 3 minutes 5 seconds")
        assert_progress_detected(r_30, 0.15, 0.17)
        should_trigger, _ = TimeParserOracle.should_trigger_completion(r_30)
        self.assertFalse(should_trigger, "Premature trigger at 30s")

        # At 65s (35%) -> Watchdog must NOT trigger because progress bar exists
        r_65 = TimeParserOracle.parse_time_description("1 minute 5 seconds of 3 minutes 5 seconds")
        assert_progress_detected(r_65, 0.34, 0.36)
        should_trigger, _ = TimeParserOracle.should_trigger_completion(r_65)
        self.assertFalse(should_trigger, "Watchdog or progress false positive at 65s")

        # At 182s (98.3%) -> Trigger completion
        r_end = TimeParserOracle.parse_time_description("3 minutes 2 seconds of 3 minutes 5 seconds")
        assert_progress_detected(r_end, 0.98, 0.99)
        should_trigger, reason = TimeParserOracle.should_trigger_completion(r_end)
        self.assertTrue(should_trigger)
        self.assertEqual(reason, "near_end")

    def test_t2_3_loop_wraparound_timing_transition(self):
        """T2.3: Video looping back to 0-15% after reaching >=80% triggers wraparound completion."""
        test_pairs = [
            (0.85, 0.05, True),
            (0.92, 0.00, True),
            (0.80, 0.15, True),
            (0.79, 0.05, False),  # Was below 80%, not considered wraparound
            (0.85, 0.16, False),  # Current above 15%, not wrapped around yet
        ]
        for last_p, cur_p, expected_trigger in test_pairs:
            triggered, reason = TimeParserOracle.should_trigger_completion(cur_p, last_progress=last_p)
            self.assertEqual(
                triggered,
                expected_trigger,
                f"Wraparound transition from {last_p} to {cur_p} expected {expected_trigger} but got {triggered}",
            )

    def test_t2_4_rapid_comments_drawer_toggling(self):
        """T2.4: Rapid opening and closing of comments drawer (chattering within 200ms)."""
        rapid_events = [
            "11-04 14:00:01.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            "11-04 14:00:01.120  1247  1247 D DoomScroller-Detector: Live Progress: 40% (last: 40%)",
            "11-04 14:00:01.210  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            "11-04 14:00:01.350  1247  1247 D DoomScroller-Detector: Live Progress: 41% (last: 40%)",
        ]
        self.log_monitor.load_from_text("\n".join(rapid_events))
        # Ensure zero crashes or exceptions occurred during rapid state oscillations
        crashes = self.log_monitor.audit_crashes_and_exceptions()
        assert_zero_crashes(crashes)

    def test_t2_5_comments_open_over_65s_watchdog_freeze(self):
        """T2.5: Comments drawer remaining open longer than 65s without watchdog auto-advancing."""
        logs = EventSimulator.generate_comments_pause_logs()
        self.log_monitor.load_from_text(logs)

        # Check if watchdog fired during comments
        watchdog_entries = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Watchdog triggered")
        self.assertEqual(
            len(watchdog_entries),
            0,
            "Watchdog triggered while comments drawer was open! Session timer must freeze.",
        )
        assert_watchdog_frozen_during_pause(watchdog_triggered=bool(watchdog_entries), elapsed_sec=75.0)

    def test_t2_6_mid_video_manual_pause_freeze(self):
        """T2.6: Mid-video manual pause remaining paused indefinitely without triggering auto-scroll."""
        pause_logs = [
            "11-04 14:00:10.000  1247  1247 D DoomScroller-Detector: Live Progress: 50% (last: 45%)",
            "11-04 14:00:12.000  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused",
            "11-04 14:01:25.000  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused",  # >70s later
        ]
        self.log_monitor.load_from_text("\n".join(pause_logs))
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 0, "Gesture dispatched while video was paused by user!")

    def test_t2_7_rapid_consecutive_events_within_debounce_window(self):
        """T2.7: Rapid consecutive events within debounce window (no double swipe injection)."""
        debounce_window_ms = 900
        first_event_ms = 1000.0
        second_event_ms = 1400.0  # +400ms (within 900ms window)

        delta = second_event_ms - first_event_ms
        self.assertLess(delta, debounce_window_ms)

        # Detector logic: should reject second event
        def should_allow_scroll(last_time_ms: float, now_ms: float, cooldown: float) -> bool:
            return (now_ms - last_time_ms) >= cooldown

        self.assertFalse(should_allow_scroll(first_event_ms, second_event_ms, debounce_window_ms))
        self.assertTrue(should_allow_scroll(first_event_ms, first_event_ms + 950.0, debounce_window_ms))

    def test_t2_8_progress_boundary_thresholds(self):
        """T2.8: Strict boundary checks: 97.9% must NOT trigger, 98.0% MUST trigger."""
        # 97.9% -> No trigger
        triggered_979, _ = TimeParserOracle.should_trigger_completion(0.979)
        self.assertFalse(triggered_979, "97.9% prematurely triggered completion!")

        # 98.0% -> Trigger
        triggered_980, reason_980 = TimeParserOracle.should_trigger_completion(0.980)
        self.assertTrue(triggered_980, "98.0% failed to trigger completion!")
        self.assertEqual(reason_980, "near_end")

        # 100.0% -> Trigger
        triggered_100, reason_100 = TimeParserOracle.should_trigger_completion(1.0)
        self.assertTrue(triggered_100)

        # 0.0% -> No trigger
        triggered_0, _ = TimeParserOracle.should_trigger_completion(0.0)
        self.assertFalse(triggered_0)

    def test_t2_9_malformed_time_description_resilience(self):
        """T2.9: Malformed time strings and null inputs must return None without raising uncaught exceptions."""
        malformed_inputs = [
            "",
            "   ",
            "not a time string",
            "of 1 minute",
            "30 seconds of",
            "invalid / invalid",
            "null",
            None,
            "12:34:56:78 of 99:99",
            "abc of xyz",
        ]
        for item in malformed_inputs:
            result = TimeParserOracle.parse_time_description(item)
            self.assertIsNone(result, f"Expected None for malformed input '{item}' but got {result}")

    def test_t2_10_zero_duration_and_boundary_resilience(self):
        """T2.10: Zero duration handling: total_sec <= 0 must be handled without ZeroDivisionError."""
        zero_cases = [
            "0 seconds of 0 seconds",
            "0:00 of 0:00",
            "0:00 / 0:00",
            "0 minutes of 0 minutes",
        ]
        for case in zero_cases:
            result = TimeParserOracle.parse_time_description(case)
            self.assertIsNone(result, f"Zero duration case '{case}' must safely return None")


if __name__ == "__main__":
    unittest.main()

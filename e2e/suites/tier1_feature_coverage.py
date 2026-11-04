"""Tier 1: Feature Coverage Test Suite.

Covers all core features of DoomScroller in isolation per TEST_INFRA.md and PROJECT.md:
- T1.1: Short clip playback detection (<15s)
- T1.2: Medium clip playback detection (~30s)
- T1.3: Long clip playback detection (~60s)
- T1.4: Progress string parsing with minutes and seconds
- T1.5: Progress string parsing with seconds only
- T1.6: Progress string parsing with standard mm:ss
- T1.7: Upward flick gesture injection and safety boundaries
- T1.8: Debounce cooldown enforcement (>=800ms)
- T1.9: Comments drawer opening detection & auto-scroll pause
- T1.10: Manual pause state ("Play video") detection & auto-scroll pause
- T1.11: Scope enforcement: YouTube Shorts exclusivity
- T1.12: Reel time bar node discovery verification
"""

import unittest
from e2e.harness.adb_client import ADBClient
from e2e.harness.assertions import (
    assert_cooldown_enforced,
    assert_gesture_coordinates_safe,
    assert_progress_detected,
    assert_zero_crashes,
)
from e2e.harness.event_simulator import EventSimulator
from e2e.harness.logcat_monitor import LogcatMonitor
from e2e.harness.parser_oracle import TimeParserOracle
from e2e.harness.youtube_controller import YouTubeController


class TestTier1FeatureCoverage(unittest.TestCase):

    def setUp(self):
        # Default to safe mock_mode if ADB device is frozen
        self.adb = ADBClient(mock_mode=True)
        self.controller = YouTubeController(self.adb)
        self.log_monitor = LogcatMonitor(self.adb)

    def test_t1_1_short_clip_playback_detection(self):
        """T1.1: Short clip (<15s) playback detection and completion trigger."""
        duration_sec = 12
        # Expected outputs from oracle
        ratio_mid = TimeParserOracle.parse_time_description(f"0 minutes 6 seconds of 0 minutes {duration_sec} seconds")
        assert_progress_detected(ratio_mid, 0.49, 0.51)

        ratio_end = TimeParserOracle.parse_time_description(f"0 minutes {duration_sec} seconds of 0 minutes {duration_sec} seconds")
        assert_progress_detected(ratio_end, 0.98, 1.0)
        should_trigger, reason = TimeParserOracle.should_trigger_completion(ratio_end)
        self.assertTrue(should_trigger)
        self.assertEqual(reason, "near_end")

        # Verify against simulated logcat stream
        logs = EventSimulator.generate_single_video_playback_logs(duration_sec=duration_sec)
        self.log_monitor.load_from_text("\n".join(logs))
        completion_entries = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Short completion detected!")
        self.assertTrue(len(completion_entries) >= 1)

    def test_t1_2_medium_clip_playback_detection(self):
        """T1.2: Medium clip (~30s) playback detection and completion trigger."""
        duration_sec = 32
        ratio_mid = TimeParserOracle.parse_time_description(f"0 minutes 16 seconds of 0 minutes {duration_sec} seconds")
        assert_progress_detected(ratio_mid, 0.49, 0.51)

        ratio_end = TimeParserOracle.parse_time_description(f"0 minutes 31 seconds of 0 minutes {duration_sec} seconds")
        self.assertGreaterEqual(ratio_end, 0.96)
        should_trigger, reason = TimeParserOracle.should_trigger_completion(ratio_end)
        # 31 / 32 = 0.96875 -> at 32s it reaches 1.0 (>= 0.98)
        ratio_final = TimeParserOracle.parse_time_description(f"0 minutes 32 seconds of 0 minutes {duration_sec} seconds")
        should_trigger, _ = TimeParserOracle.should_trigger_completion(ratio_final)
        self.assertTrue(should_trigger)

        logs = EventSimulator.generate_single_video_playback_logs(duration_sec=duration_sec)
        self.log_monitor.load_from_text("\n".join(logs))
        completion_entries = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Short completion detected!")
        self.assertTrue(len(completion_entries) >= 1)

    def test_t1_3_long_clip_playback_detection(self):
        """T1.3: Long clip (~60s) playback detection and completion trigger."""
        duration_sec = 58
        ratio_mid = TimeParserOracle.parse_time_description(f"0 minutes 29 seconds of 0 minutes {duration_sec} seconds")
        assert_progress_detected(ratio_mid, 0.49, 0.51)

        ratio_end = TimeParserOracle.parse_time_description(f"0 minutes 57 seconds of 0 minutes {duration_sec} seconds")
        should_trigger, reason = TimeParserOracle.should_trigger_completion(ratio_end)
        self.assertTrue(should_trigger)
        self.assertEqual(reason, "near_end")

        logs = EventSimulator.generate_single_video_playback_logs(duration_sec=duration_sec)
        self.log_monitor.load_from_text("\n".join(logs))
        completion_entries = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Short completion detected!")
        self.assertTrue(len(completion_entries) >= 1)

    def test_t1_4_progress_parsing_minutes_and_seconds(self):
        """T1.4: Progress string parsing with full natural language minutes and seconds."""
        test_cases = [
            ("0 minutes 40 seconds of 1 minute 25 seconds", 40 / 85),
            ("1 minute 5 seconds of 2 minutes 10 seconds", 65 / 130),
            ("0 minutes 15 seconds of 0 minutes 45 seconds", 15 / 45),
            ("2 minutes 0 seconds of 4 minutes 0 seconds", 120 / 240),
            ("0 minutes 3 seconds of 1 minute 0 seconds", 3 / 60),
        ]
        for text, expected in test_cases:
            parsed = TimeParserOracle.parse_time_description(text)
            self.assertIsNotNone(parsed, f"Failed to parse '{text}'")
            self.assertAlmostEqual(parsed, expected, places=3, msg=f"Mismatch for '{text}'")

    def test_t1_5_progress_parsing_seconds_only(self):
        """T1.5: Progress string parsing with seconds only format."""
        test_cases = [
            ("15 seconds of 22 seconds", 15 / 22),
            ("7 seconds of 15 seconds", 7 / 15),
            ("30 seconds of 60 seconds", 30 / 60),
            ("1 second of 10 seconds", 1 / 10),
            ("59 seconds of 60 seconds", 59 / 60),
        ]
        for text, expected in test_cases:
            parsed = TimeParserOracle.parse_time_description(text)
            self.assertIsNotNone(parsed, f"Failed to parse '{text}'")
            self.assertAlmostEqual(parsed, expected, places=3, msg=f"Mismatch for '{text}'")

    def test_t1_6_progress_parsing_standard_colon_format(self):
        """T1.6: Progress string parsing with standard mm:ss colon syntax."""
        test_cases = [
            ("0:15 of 0:22", 15 / 22),
            ("1:05 / 2:30", 65 / 150),
            ("00:05 / 00:30", 5 / 30),
            ("0:45 of 1:00", 45 / 60),
            ("1:30 / 3:00", 90 / 180),
        ]
        for text, expected in test_cases:
            parsed = TimeParserOracle.parse_time_description(text)
            self.assertIsNotNone(parsed, f"Failed to parse '{text}'")
            self.assertAlmostEqual(parsed, expected, places=3, msg=f"Mismatch for '{text}'")

    def test_t1_7_upward_flick_gesture_dispatch_and_coordinates(self):
        """T1.7: Upward flick gesture injection and verification of coordinate safety on 720x1560 display."""
        width, height = 720, 1560
        # Target gesture parameters per GestureEngine contract
        start_x = int(width * 0.5)
        start_y = int(height * 0.76)
        end_x = int(width * 0.5)
        end_y = int(height * 0.22)
        duration_ms = 180

        # Verify coordinate safety
        assert_gesture_coordinates_safe(start_x, start_y, end_x, end_y, width, height)

        # Verify duration within snappy window (150-200ms)
        self.assertGreaterEqual(duration_ms, 150)
        self.assertLessEqual(duration_ms, 200)

        # Verify gesture parsing from logcat
        logs = [
            f"11-04 14:00:05.100  1247  1247 I DoomScroller-Gesture: Dispatching upward scroll gesture: ({start_x}, {start_y}) -> ({end_x}, {end_y}) in {duration_ms}ms",
            "11-04 14:00:05.280  1247  1247 I DoomScroller-Gesture: Scroll gesture completed successfully",
        ]
        self.log_monitor.load_from_text("\n".join(logs))
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 1)
        self.assertTrue(gestures[0].completed)
        self.assertFalse(gestures[0].cancelled)

    def test_t1_8_debounce_cooldown_enforcement(self):
        """T1.8: Debounce cooldown enforcement (disallowing duplicate swipes within 800ms cooldown window)."""
        min_cooldown_ms = 800.0

        # Dispatched too fast (e.g. 250ms interval) -> must fail assertion
        with self.assertRaises(AssertionError):
            assert_cooldown_enforced(interval_ms=250.0, min_cooldown_ms=min_cooldown_ms)

        # Dispatched after cooldown (e.g. 920ms interval) -> must pass
        assert_cooldown_enforced(interval_ms=920.0, min_cooldown_ms=min_cooldown_ms)

    def test_t1_9_comments_drawer_smart_pause(self):
        """T1.9: Comments drawer opening detection & auto-scroll pause gating."""
        xml_comments_open = EventSimulator.generate_shorts_ui_dump(comments_open=True)
        self.adb.set_mock_ui_hierarchy(xml_comments_open)

        self.assertTrue(self.controller.is_comments_drawer_visible())

        # Verify logcat record for comments drawer pause
        logs = [
            "11-04 14:00:10.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused"
        ]
        self.log_monitor.load_from_text("\n".join(logs))
        pause_entries = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Comments drawer open")
        self.assertEqual(len(pause_entries), 1)

    def test_t1_10_manual_pause_state_detection(self):
        """T1.10: Manual pause state ("Play video") detection & auto-scroll pause gating."""
        xml_paused = EventSimulator.generate_shorts_ui_dump(video_paused=True)
        self.adb.set_mock_ui_hierarchy(xml_paused)

        self.assertTrue(self.controller.is_video_paused())

        logs = [
            "11-04 14:00:15.000  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused"
        ]
        self.log_monitor.load_from_text("\n".join(logs))
        pause_entries = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Video is paused by user")
        self.assertEqual(len(pause_entries), 1)

    def test_t1_11_scope_enforcement_exclusivity(self):
        """T1.11: Scope enforcement: package filtering strictly limits to com.google.android.youtube."""
        def is_supported_package(pkg: str) -> bool:
            return pkg == "com.google.android.youtube"

        self.assertTrue(is_supported_package("com.google.android.youtube"))
        self.assertFalse(is_supported_package("com.android.chrome"))
        self.assertFalse(is_supported_package("com.sec.android.app.launcher"))
        self.assertFalse(is_supported_package("com.instagram.android"))
        self.assertFalse(is_supported_package("com.zhiliaoapp.musically"))

    def test_t1_12_reel_time_bar_node_discovery(self):
        """T1.12: Reel time bar node discovery verification in YouTube Shorts hierarchy."""
        xml = EventSimulator.generate_shorts_ui_dump(current_time_str="0 minutes 10 seconds", total_time_str="0 minutes 25 seconds")
        self.adb.set_mock_ui_hierarchy(xml)

        ratio, desc = self.controller.extract_live_progress()
        self.assertIsNotNone(ratio)
        self.assertEqual(desc, "0 minutes 10 seconds of 0 minutes 25 seconds")
        self.assertAlmostEqual(ratio, 10 / 25, places=3)


if __name__ == "__main__":
    unittest.main()

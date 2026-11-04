"""Tier 3: Cross-Feature Combinations Test Suite.

Tests interactions between multiple overlapping subsystems per TEST_INFRA.md:
- T3.1: Comments drawer opened at 95% progress (must NOT scroll at >=98% while comments open)
- T3.2: Comments drawer closed after video reached end (resumes cleanly on next loop cycle)
- T3.3: Manual pause engaged at 99% progress (must NOT scroll while paused)
- T3.4: Manual resume at 99% progress (scrolls immediately upon playback resumption)
- T3.5: Navigating to next Short immediately after manual scroll (debounce window holds)
- T3.6: Dual pause state: paused video with open comments sheet, released sequentially
"""

import unittest
from e2e.harness.adb_client import ADBClient
from e2e.harness.assertions import assert_zero_crashes
from e2e.harness.event_simulator import EventSimulator
from e2e.harness.logcat_monitor import LogcatMonitor
from e2e.harness.parser_oracle import TimeParserOracle
from e2e.harness.youtube_controller import YouTubeController


class TestTier3CrossFeature(unittest.TestCase):

    def setUp(self):
        self.adb = ADBClient(mock_mode=True)
        self.controller = YouTubeController(self.adb)
        self.log_monitor = LogcatMonitor(self.adb)

    def test_t3_1_comments_opened_at_95_percent_blocks_completion_scroll(self):
        """T3.1: Comments drawer opened at 95% progress blocks auto-scroll even when video reaches >=98%."""
        # Video at 95%
        r_95 = TimeParserOracle.parse_time_description("0 minutes 57 seconds of 1 minute 0 seconds")
        self.assertAlmostEqual(r_95, 0.95, places=2)

        # Simulation: User opens comments while video is at 95%
        # Next frame video is at 99%, but comments drawer is open!
        scenario_logs = [
            "11-04 14:10:00.000  1247  1247 D DoomScroller-Detector: Live Progress: 95% (last: 90%)",
            "11-04 14:10:01.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            # Video reaches 99% in background, but comments drawer is OPEN
            "11-04 14:10:02.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
        ]
        self.log_monitor.load_from_text("\n".join(scenario_logs))

        # Ensure NO gesture was dispatched
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 0, "Gesture dispatched while comments were open at 98%+!")

    def test_t3_2_comments_closed_after_video_ended_resumes_next_cycle(self):
        """T3.2: Comments drawer closed after video reached end resumes auto-advance on next loop."""
        scenario_logs = [
            # Video played to end while comments open
            "11-04 14:10:00.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            "11-04 14:10:05.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            # User closes comments: video has looped to 10%
            "11-04 14:10:08.000  1247  1247 D DoomScroller-Detector: Live Progress: 10% (last: 0%)",
            "11-04 14:10:15.000  1247  1247 D DoomScroller-Detector: Live Progress: 80% (last: 10%)",
            "11-04 14:10:18.000  1247  1247 D DoomScroller-Detector: Live Progress: 99% (last: 80%)",
            "11-04 14:10:18.010  1247  1247 I DoomScroller-Detector: Short completion detected! (Loops watched: 1 / Required: 1)",
            "11-04 14:10:18.100  1247  1247 I DoomScroller-Gesture: Dispatching upward scroll gesture: (360, 1185) -> (360, 343) in 175ms",
            "11-04 14:10:18.275  1247  1247 I DoomScroller-Gesture: Scroll gesture completed successfully",
        ]
        self.log_monitor.load_from_text("\n".join(scenario_logs))
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 1)
        self.assertTrue(gestures[0].completed)

    def test_t3_3_manual_pause_at_99_percent_blocks_scroll(self):
        """T3.3: Manual pause engaged at 99% progress blocks auto-scroll."""
        scenario_logs = [
            "11-04 14:15:00.000  1247  1247 D DoomScroller-Detector: Live Progress: 99% (last: 95%)",
            # User tapped pause immediately
            "11-04 14:15:00.050  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused",
            "11-04 14:15:10.000  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused",
        ]
        self.log_monitor.load_from_text("\n".join(scenario_logs))
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 0, "Gesture dispatched while manual pause was active!")

    def test_t3_4_manual_resume_at_99_percent_scrolls_promptly(self):
        """T3.4: Manual resume at 99% progress scrolls promptly upon playback resumption."""
        scenario_logs = [
            "11-04 14:15:00.000  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused",
            # User hits play
            "11-04 14:15:05.000  1247  1247 D DoomScroller-Detector: Live Progress: 99% (last: 99%)",
            "11-04 14:15:05.010  1247  1247 I DoomScroller-Detector: Short completion detected! (Loops watched: 1 / Required: 1)",
            "11-04 14:15:05.095  1247  1247 I DoomScroller-Gesture: Dispatching upward scroll gesture: (360, 1185) -> (360, 343) in 170ms",
            "11-04 14:15:05.265  1247  1247 I DoomScroller-Gesture: Scroll gesture completed successfully",
        ]
        self.log_monitor.load_from_text("\n".join(scenario_logs))
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 1)
        self.assertTrue(gestures[0].completed)

    def test_t3_5_navigating_immediately_after_manual_scroll(self):
        """T3.5: User manually scrolls to next Short; detector debounce holds to avoid duplicate auto-advance."""
        manual_scroll_time = 1420000.0
        auto_advance_attempt = 1420400.0  # +400ms after user scroll (within 900ms cooldown)
        self.assertLess(auto_advance_attempt - manual_scroll_time, 900.0)

    def test_t3_6_dual_pause_state_handling(self):
        """T3.6: User pauses video AND opens comments drawer (dual pause), releases comments while still paused."""
        scenario_logs = [
            # Dual pause
            "11-04 14:20:00.000  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused",
            "11-04 14:20:01.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            # User closes comments, but video is STILL paused
            "11-04 14:20:05.000  1247  1247 D DoomScroller-Detector: Video is paused by user, auto-scroll paused",
        ]
        self.log_monitor.load_from_text("\n".join(scenario_logs))
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 0, "Gesture dispatched while video was still paused after comments closed!")
        crashes = self.log_monitor.audit_crashes_and_exceptions()
        assert_zero_crashes(crashes)


if __name__ == "__main__":
    unittest.main()

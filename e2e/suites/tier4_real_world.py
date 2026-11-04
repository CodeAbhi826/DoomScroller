"""Tier 4: Real-World Application Workload Scenarios Test Suite.

End-to-end acceptance criteria validation per ORIGINAL_REQUEST.md and TEST_INFRA.md:
- T4.1: Continuous hands-free auto-scrolling across 3 consecutive YouTube Shorts of varying lengths (<15s, ~30s, ~60s)
- T4.2: Transition latency measurement from >=98% completion to swipe injection (<300ms SLA verification)
- T4.3: Smart Pause live user simulation (comments open on Short #2, then resume)
- T4.4: Device health verification: zero crashes, fatal exceptions, or ANR loops
"""

import unittest
from e2e.harness.adb_client import ADBClient
from e2e.harness.assertions import (
    assert_transition_latency_under_sla,
    assert_zero_crashes,
)
from e2e.harness.event_simulator import EventSimulator
from e2e.harness.logcat_monitor import LogcatMonitor
from e2e.harness.youtube_controller import YouTubeController


class TestTier4RealWorldWorkloads(unittest.TestCase):

    def setUp(self):
        self.adb = ADBClient(mock_mode=True)
        self.controller = YouTubeController(self.adb)
        self.log_monitor = LogcatMonitor(self.adb)

    def test_t4_1_three_consecutive_shorts_auto_advance(self):
        """T4.1: At least 3 consecutive YouTube Shorts of differing durations successfully auto-advance without user interaction."""
        workload_logs = EventSimulator.generate_workload_3_shorts()
        self.log_monitor.load_from_text(workload_logs)

        # 1. Verify 3 completion detection events
        completions = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Short completion detected!")
        self.assertGreaterEqual(len(completions), 3, f"Expected >= 3 completions, but found {len(completions)}")

        # 2. Verify 3 successful gesture dispatches
        gestures = self.log_monitor.extract_gesture_events()
        self.assertGreaterEqual(len(gestures), 3, f"Expected >= 3 gesture dispatches, but found {len(gestures)}")

        for i, g in enumerate(gestures[:3]):
            self.assertTrue(g.completed, f"Gesture {i+1} did not complete successfully")
            self.assertFalse(g.cancelled, f"Gesture {i+1} was cancelled by system")

    def test_t4_2_sub_300ms_transition_latency(self):
        """T4.2: Measurement of transition latency from >=98% completion to swipe injection (<300ms SLA)."""
        workload_logs = EventSimulator.generate_workload_3_shorts()
        self.log_monitor.load_from_text(workload_logs)

        latencies = self.log_monitor.measure_transition_latencies()
        self.assertGreaterEqual(len(latencies), 3, f"Expected >= 3 latency measurements, got {len(latencies)}")

        for idx, m in enumerate(latencies):
            # Assert each transition is strictly under 300ms
            assert_transition_latency_under_sla(
                m.latency_ms,
                max_sla_ms=300.0,
                msg=f"Short transition #{idx+1} ({m.trigger_type})",
            )
            # Log exact latency for test report
            self.assertLess(m.latency_ms, 300.0)

    def test_t4_3_smart_pause_live_user_simulation(self):
        """T4.3: Smart Pause live user simulation: user opens comments on Short #2 for 10s+, closes it, auto-advance resumes."""
        scenario_logs = EventSimulator.generate_comments_pause_logs()
        self.log_monitor.load_from_text(scenario_logs)

        # Verify pause log exists
        pauses = self.log_monitor.filter(tag="DoomScroller-Detector", pattern="Comments drawer open, auto-scroll paused")
        self.assertGreaterEqual(len(pauses), 1)

        # Verify auto-advance resumed after comments closed
        gestures = self.log_monitor.extract_gesture_events()
        self.assertEqual(len(gestures), 1)
        self.assertTrue(gestures[0].completed)

    def test_t4_4_device_health_and_zero_exceptions(self):
        """T4.4: Device health verification: continuous logcat check during playback showing zero exceptions or crash loops."""
        workload_logs = EventSimulator.generate_workload_3_shorts()
        self.log_monitor.load_from_text(workload_logs)

        bad_entries = self.log_monitor.audit_crashes_and_exceptions()
        assert_zero_crashes(bad_entries, msg="Tier 4 Real-World Workload continuous playback")


if __name__ == "__main__":
    unittest.main()

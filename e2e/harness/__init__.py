# DoomScroller E2E Harness Modules
from .adb_client import ADBClient
from .logcat_monitor import LogcatMonitor, LogcatEntry
from .parser_oracle import TimeParserOracle
from .event_simulator import EventSimulator
from .youtube_controller import YouTubeController
from .assertions import (
    assert_progress_detected,
    assert_transition_latency_under_sla,
    assert_cooldown_enforced,
    assert_gesture_coordinates_safe,
    assert_zero_crashes,
    assert_watchdog_frozen_during_pause,
)

__all__ = [
    "ADBClient",
    "LogcatMonitor",
    "LogcatEntry",
    "TimeParserOracle",
    "EventSimulator",
    "YouTubeController",
    "assert_progress_detected",
    "assert_transition_latency_under_sla",
    "assert_cooldown_enforced",
    "assert_gesture_coordinates_safe",
    "assert_zero_crashes",
    "assert_watchdog_frozen_during_pause",
]

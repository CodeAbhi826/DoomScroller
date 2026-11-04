"""Domain-specific assertions for DoomScroller E2E testing."""

from typing import List, Optional
from .logcat_monitor import LogcatEntry


class DoomScrollerAssertionError(AssertionError):
    pass


def assert_progress_detected(
    progress: Optional[float],
    expected_min: float = 0.0,
    expected_max: float = 1.0,
    msg: str = "",
):
    if progress is None:
        raise DoomScrollerAssertionError(f"Expected playback progress ratio but received None. {msg}")
    if not (expected_min <= progress <= expected_max):
        raise DoomScrollerAssertionError(
            f"Progress ratio {progress:.3f} out of expected bounds [{expected_min:.3f}, {expected_max:.3f}]. {msg}"
        )


def assert_transition_latency_under_sla(latency_ms: float, max_sla_ms: float = 300.0, msg: str = ""):
    if latency_ms > max_sla_ms:
        raise DoomScrollerAssertionError(
            f"Transition latency {latency_ms:.1f}ms exceeds SLA limit of {max_sla_ms:.1f}ms! {msg}"
        )


def assert_cooldown_enforced(interval_ms: float, min_cooldown_ms: float = 800.0, msg: str = ""):
    if interval_ms < min_cooldown_ms:
        raise DoomScrollerAssertionError(
            f"Event dispatched after {interval_ms:.1f}ms, violating minimum cooldown of {min_cooldown_ms:.1f}ms! {msg}"
        )


def assert_gesture_coordinates_safe(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    display_width: int = 720,
    display_height: int = 1560,
    msg: str = "",
):
    # Check vertical flick direction (upward swipe: start_y > end_y)
    if start_y <= end_y:
        raise DoomScrollerAssertionError(
            f"Gesture direction invalid: start_y ({start_y}) must be greater than end_y ({end_y}) for upward scroll. {msg}"
        )

    # Check horizontal safety margins (prevent triggering Android 14 edge back-gesture)
    edge_margin_x = display_width * 0.10
    if start_x < edge_margin_x or start_x > (display_width - edge_margin_x):
        raise DoomScrollerAssertionError(
            f"Start X ({start_x}) too close to screen edges (width={display_width}), risking gesture navigation conflict! {msg}"
        )

    # Check vertical flick span
    stroke_length = start_y - end_y
    min_span = display_height * 0.35
    if stroke_length < min_span:
        raise DoomScrollerAssertionError(
            f"Swipe stroke length ({stroke_length}px) too short (min required: {min_span}px) to trigger snap scroll in Shorts. {msg}"
        )


def assert_zero_crashes(bad_entries: List[LogcatEntry], msg: str = ""):
    if bad_entries:
        err_details = "\n".join(f"[{e.level}] {e.tag}: {e.message}" for e in bad_entries[:5])
        raise DoomScrollerAssertionError(
            f"Detected {len(bad_entries)} fatal/error log entries in DoomScroller components:\n{err_details}\n{msg}"
        )


def assert_watchdog_frozen_during_pause(watchdog_triggered: bool, elapsed_sec: float, msg: str = ""):
    if watchdog_triggered:
        raise DoomScrollerAssertionError(
            f"Watchdog auto-advance fired after {elapsed_sec}s while in paused state! Watchdog timer must be frozen during comments/pause. {msg}"
        )

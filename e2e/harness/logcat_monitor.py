"""Logcat Monitor and Event Analyzer for DoomScroller E2E testing.

Parses logcat records, extracts timeline events (progress, completion, gestures, pauses),
calculates transition latencies against the <300ms SLA, and audits for zero-crash guarantees.
"""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import List, Optional, Tuple
from .adb_client import ADBClient


@dataclass
class LogcatEntry:
    timestamp_str: str
    pid: int
    tid: int
    level: str
    tag: str
    message: str
    timestamp_epoch_ms: float = 0.0


@dataclass
class GestureEvent:
    timestamp_ms: float
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    duration_ms: int
    completed: bool = False
    cancelled: bool = False


@dataclass
class LatencyMeasurement:
    detection_timestamp_ms: float
    gesture_timestamp_ms: float
    latency_ms: float
    trigger_type: str  # "near_end" or "wraparound"


class LogcatMonitor:
    LOGCAT_PATTERN = re.compile(
        r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+([^:]+):\s+(.*)$"
    )

    def __init__(self, adb_client: Optional[ADBClient] = None):
        self.adb = adb_client or ADBClient()
        self.entries: List[LogcatEntry] = []

    def load_from_text(self, logcat_text: str):
        """Parse raw logcat text output into structured LogcatEntry objects."""
        self.entries = []
        for line in logcat_text.splitlines():
            line = line.strip()
            if not line or line.startswith("---------"):
                continue
            m = self.LOGCAT_PATTERN.match(line)
            if m:
                ts_str, pid_s, tid_s, lvl, tag, msg = m.groups()
                # Parse timestamp to epoch ms (using current year for date parsing)
                epoch_ms = self._parse_timestamp_to_ms(ts_str)
                self.entries.append(
                    LogcatEntry(
                        timestamp_str=ts_str,
                        pid=int(pid_s),
                        tid=int(tid_s),
                        level=lvl,
                        tag=tag.strip(),
                        message=msg.strip(),
                        timestamp_epoch_ms=epoch_ms,
                    )
                )

    def _parse_timestamp_to_ms(self, ts_str: str) -> float:
        """Converts MM-DD HH:MM:SS.mmm to milliseconds."""
        try:
            # Assuming current year 2026
            dt = datetime.strptime(f"2026-{ts_str}", "%Y-%m-%d %H:%M:%S.%f")
            return dt.timestamp() * 1000.0
        except Exception:
            return 0.0

    def capture_live(self, tags: Optional[List[str]] = None, lines: int = 200):
        """Fetch live logcat slice from device and parse."""
        tags = tags or ["DoomScroller-Service", "DoomScroller-Detector", "DoomScroller-Gesture", "AndroidRuntime"]
        text = self.adb.get_logcat_slice(tags=tags, lines=lines)
        self.load_from_text(text)

    def filter(
        self,
        tag: Optional[str] = None,
        level: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> List[LogcatEntry]:
        """Filter parsed entries matching criteria."""
        results = []
        for e in self.entries:
            if tag and tag not in e.tag:
                continue
            if level and e.level != level:
                continue
            if pattern and not re.search(pattern, e.message, re.IGNORECASE):
                continue
            results.append(e)
        return results

    def extract_progress_timeline(self) -> List[Tuple[float, int]]:
        """Returns list of (timestamp_ms, progress_pct) reported by detector."""
        timeline = []
        for e in self.entries:
            if "DoomScroller-Detector" in e.tag:
                m = re.search(r"Live Progress:\s+(\d+)%", e.message)
                if m:
                    timeline.append((e.timestamp_epoch_ms, int(m.group(1))))
        return timeline

    def extract_gesture_events(self) -> List[GestureEvent]:
        """Extract all gesture dispatch and completion records."""
        gestures: List[GestureEvent] = []
        active_gesture: Optional[GestureEvent] = None

        for e in self.entries:
            if "DoomScroller-Gesture" in e.tag:
                m_dispatch = re.search(
                    r"Dispatching upward scroll gesture:\s*\((\d+),\s*(\d+)\)\s*->\s*\((\d+),\s*(\d+)\)\s*in\s*(\d+)ms",
                    e.message,
                )
                if m_dispatch:
                    sx, sy, ex, ey, dur = [int(v) for v in m_dispatch.groups()]
                    active_gesture = GestureEvent(
                        timestamp_ms=e.timestamp_epoch_ms,
                        start_x=sx,
                        start_y=sy,
                        end_x=ex,
                        end_y=ey,
                        duration_ms=dur,
                    )
                    gestures.append(active_gesture)
                elif "Scroll gesture completed successfully" in e.message:
                    if active_gesture:
                        active_gesture.completed = True
                elif "Scroll gesture was cancelled by system" in e.message:
                    if active_gesture:
                        active_gesture.cancelled = True

        return gestures

    def measure_transition_latencies(self) -> List[LatencyMeasurement]:
        """Measures latency between video completion detection and gesture dispatch.

        SLA requirement: < 300ms.
        """
        measurements: List[LatencyMeasurement] = []
        pending_detection_time: Optional[float] = None
        trigger_type = "unknown"

        for e in self.entries:
            if "DoomScroller-Detector" in e.tag:
                if "Short completion detected!" in e.message or "Watchdog triggered:" in e.message:
                    pending_detection_time = e.timestamp_epoch_ms
                    trigger_type = "near_end" if "Short completion detected!" in e.message else "watchdog"
                elif "Live Progress: 98%" in e.message or "Live Progress: 99%" in e.message or "Live Progress: 100%" in e.message:
                    if pending_detection_time is None:
                        pending_detection_time = e.timestamp_epoch_ms
                        trigger_type = "near_end"

            elif "DoomScroller-Gesture" in e.tag:
                if "Dispatching upward scroll gesture:" in e.message:
                    if pending_detection_time is not None:
                        latency = e.timestamp_epoch_ms - pending_detection_time
                        if latency >= 0:
                            measurements.append(
                                LatencyMeasurement(
                                    detection_timestamp_ms=pending_detection_time,
                                    gesture_timestamp_ms=e.timestamp_epoch_ms,
                                    latency_ms=latency,
                                    trigger_type=trigger_type,
                                )
                            )
                        pending_detection_time = None

        return measurements

    def audit_crashes_and_exceptions(self) -> List[LogcatEntry]:
        """Finds any crash logs, fatal exceptions, or error-level entries in DoomScroller tags or AndroidRuntime."""
        bad_entries = []
        for e in self.entries:
            if e.level in ["E", "F"]:
                if "DoomScroller" in e.tag or "AndroidRuntime" in e.tag:
                    bad_entries.append(e)
            elif "FATAL EXCEPTION" in e.message or "NullPointerException" in e.message:
                bad_entries.append(e)
        return bad_entries

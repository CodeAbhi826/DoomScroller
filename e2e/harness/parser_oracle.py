"""Time Parser Oracle and Mathematical Progress Specification.

Authoritative reference oracle for TalkBack natural language duration strings,
colon-delimited timestamps, SeekBar progress calculations, and completion threshold evaluations.
Used across Tier 1, Tier 2, and Tier 3 tests to derive expected values.
"""

import math
import re
from typing import Optional, Tuple


class TimeParserOracle:
    """Authoritative reference implementation of playback progress parser."""

    NEAR_END_THRESHOLD = 0.980
    WRAPAROUND_HIGH_THRESHOLD = 0.80
    WRAPAROUND_LOW_THRESHOLD = 0.15

    @classmethod
    def parse_seconds(cls, text: str) -> Optional[int]:
        """Parses a time fragment into total seconds.

        Supports:
        - "1:25" or "0:40"
        - "0 minutes 40 seconds"
        - "1 minute 25 seconds"
        - "40 seconds"
        - "1 minute"
        - "40" (plain integer)
        """
        if not text:
            return None

        cleaned = text.strip()

        # Format 1: colon syntax (e.g., "1:25", "0:05", "1:02:15")
        if ":" in cleaned:
            colon_parts = cleaned.split(":")
            if 2 <= len(colon_parts) <= 3 and all(p.isdigit() for p in colon_parts):
                parts = [int(p) for p in colon_parts]
                if len(parts) == 2:
                    return parts[0] * 60 + parts[1]
                elif len(parts) == 3:
                    return parts[0] * 3600 + parts[1] * 60 + parts[2]
            return None

        # Format 2: Spoken natural language (e.g., "1 minute 25 seconds", "40 seconds")
        total = 0
        found_unit = False

        hour_match = re.search(r"(\d+)\s*(?:hours?|hrs?|h)\b", cleaned, re.IGNORECASE)
        if hour_match:
            total += int(hour_match.group(1)) * 3600
            found_unit = True

        min_match = re.search(r"(\d+)\s*(?:minutes?|mins?|m)\b", cleaned, re.IGNORECASE)
        if min_match:
            total += int(min_match.group(1)) * 60
            found_unit = True

        sec_match = re.search(r"(\d+)\s*(?:seconds?|secs?|s)\b", cleaned, re.IGNORECASE)
        if sec_match:
            total += int(sec_match.group(1))
            found_unit = True

        if found_unit:
            return total

        # Format 3: Plain digit fallback if no units matched
        plain_match = re.fullmatch(r"\d+", cleaned)
        if plain_match:
            return int(cleaned)

        return None

    @classmethod
    def parse_time_description(cls, text: str) -> Optional[float]:
        """Parses a full duration description string (e.g.

        "0 minutes 40 seconds of 1 minute 25 seconds"). Returns progress ratio
        in range [0.0, 1.0], or None if invalid.
        """
        if not text or not isinstance(text, str):
            return None

        # Split on separator ("of" or "/")
        if re.search(r"\bof\b", text, re.IGNORECASE):
            parts = re.split(r"\s+(?i:of)\s+", text.strip(), maxsplit=1)
        elif "/" in text:
            parts = [p.strip() for p in text.split("/", maxsplit=1)]
        else:
            return None

        if len(parts) != 2:
            return None

        current_sec = cls.parse_seconds(parts[0])
        total_sec = cls.parse_seconds(parts[1])

        if current_sec is None or total_sec is None:
            return None

        if total_sec <= 0:
            return None

        ratio = current_sec / total_sec
        # Coerce within [0.0, 1.0]
        return max(0.0, min(1.0, ratio))

    @classmethod
    def calculate_range_info_progress(cls, current: float, min_val: float, max_val: float) -> Optional[float]:
        """Calculates exact progress from AccessibilityNodeInfo.RangeInfo."""
        range_span = max_val - min_val
        if range_span <= 0:
            return None
        ratio = (current - min_val) / range_span
        return max(0.0, min(1.0, ratio))

    @classmethod
    def should_trigger_completion(cls, current_progress: float, last_progress: float = 0.0) -> Tuple[bool, str]:
        """Evaluates whether playback completion condition is satisfied.

        Returns (should_trigger, reason). Reasons:
        - "near_end": progress >= 98.0%
        - "wraparound": last >= 80% and current <= 15%
        - "none": neither condition met
        """
        if current_progress >= cls.NEAR_END_THRESHOLD:
            return True, "near_end"

        if last_progress >= cls.WRAPAROUND_HIGH_THRESHOLD and current_progress <= cls.WRAPAROUND_LOW_THRESHOLD:
            return True, "wraparound"

        return False, "none"

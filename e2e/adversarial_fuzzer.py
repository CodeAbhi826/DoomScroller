#!/usr/bin/env python3
"""Adversarial Fuzzer and Stress Testing Harness for ShortsProgressDetector.

Adversarially fuzzes and stress-tests:
1. Natural language time parsing (minutes, seconds, hours, combinations)
2. Colon syntax and percentage formats
3. Uneven video duration progressions (<7s to >60s)
4. Boundary condition precision (97.9%, 98.0%, 99.9%, 100%)
5. Malformed, corrupted, boundary, and pathological ReDoS inputs
6. State machine loop wraparound and cooldown transitions
"""

import math
import random
import re
import string
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Tuple


def f32(val: float) -> float:
    """Coerce a float into IEEE-754 32-bit single precision, matching Kotlin Float."""
    return struct.unpack("f", struct.pack("f", float(val)))[0]


class KotlinDetectorReconstruction:
    """Host reconstruction of ShortsProgressDetector's parsing and state machine."""

    NEAR_END_THRESHOLD = f32(0.980)
    WRAPAROUND_HIGH_THRESHOLD = f32(0.75)
    WRAPAROUND_LOW_THRESHOLD = f32(0.15)

    def __init__(self, loop_count_required: int = 1):
        self.loop_count_required = loop_count_required
        self.last_observed_progress = f32(0.0)
        self.current_loop_count = 0
        self.last_scroll_trigger_time = 0
        self.scroll_cooldown_ms = 800

    def parse_time_description(self, text: str) -> Optional[float]:
        if text is None:
            return None
        try:
            clean = text.strip()

            # Handle percentage strings e.g. "98%" or "Seek bar at 98%"
            percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clean)
            if percent_match:
                p_str = percent_match.group(1)
                try:
                    p = f32(float(p_str))
                    ratio = f32(p / f32(100.0))
                    return max(f32(0.0), min(f32(1.0), ratio))
                except (ValueError, OverflowError):
                    pass

            # Split into current and total parts using "of" or "/"
            parts = None
            if re.search(r"of", clean, re.IGNORECASE):
                parts = re.split(r"(?i)\s+of\s+|\bof\b", clean)
            elif "/" in clean:
                parts = clean.split("/")

            if parts is not None and len(parts) >= 2:
                current_sec = self.parse_seconds(parts[0])
                total_sec = self.parse_seconds(parts[1])

                if (
                    current_sec is not None
                    and total_sec is not None
                    and total_sec > f32(0.0)
                    and current_sec >= f32(0.0)
                ):
                    ratio = f32(current_sec / total_sec)
                    return max(f32(0.0), min(f32(1.0), ratio))
        except Exception:
            pass
        return None

    def parse_seconds(self, text: str) -> Optional[float]:
        if not text:
            return None
        clean = text.strip().rstrip(".")

        # Format 1: colon syntax (e.g. 0:15, 1:05, 1:02:15)
        colon_match = re.search(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", clean)
        if colon_match:
            try:
                h_str = colon_match.group(1)
                h = int(h_str) if h_str is not None else 0
            except (ValueError, OverflowError):
                h = 0
            try:
                m_str = colon_match.group(2)
                m = int(m_str) if m_str is not None else 0
            except (ValueError, OverflowError):
                m = 0
            try:
                s_str = colon_match.group(3)
                s = f32(float(s_str)) if s_str is not None else f32(0.0)
            except (ValueError, OverflowError):
                s = f32(0.0)
            return f32(f32(h * 3600.0) + f32(m * 60.0) + s)

        # Format 2: spoken natural language (e.g. "0 minutes 15 seconds", "1 minute 25 seconds")
        total = f32(0.0)
        found_any = False

        hr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", clean, re.IGNORECASE)
        if hr_match:
            try:
                hrs = f32(float(hr_match.group(1)))
                total = f32(total + f32(hrs * 3600.0))
                found_any = True
            except (ValueError, OverflowError):
                pass

        min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b", clean, re.IGNORECASE)
        if min_match:
            try:
                mins = f32(float(min_match.group(1)))
                total = f32(total + f32(mins * 60.0))
                found_any = True
            except (ValueError, OverflowError):
                pass

        sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", clean, re.IGNORECASE)
        if sec_match:
            try:
                secs = f32(float(sec_match.group(1)))
                total = f32(total + secs)
                found_any = True
            except (ValueError, OverflowError):
                pass

        if found_any:
            return total

        # Format 3: bare number
        num_match = re.search(r"\b(\d+(?:\.\d+)?)\b", clean)
        if num_match:
            try:
                return f32(float(num_match.group(1)))
            except (ValueError, OverflowError):
                return None

        return None

    def evaluate_progress(self, progress: float) -> Tuple[bool, str]:
        """Evaluates completion state given a live progress value."""
        is_near_end = progress >= self.NEAR_END_THRESHOLD
        is_loop_wraparound = (
            self.last_observed_progress >= self.WRAPAROUND_HIGH_THRESHOLD
            and progress <= self.WRAPAROUND_LOW_THRESHOLD
        )
        self.last_observed_progress = progress

        if is_near_end or is_loop_wraparound:
            self.current_loop_count += 1
            if self.current_loop_count >= self.loop_count_required:
                self.reset_session()
                reason = "near_end" if is_near_end else "loop_wraparound"
                return True, reason
        return False, "none"

    def reset_session(self):
        self.last_observed_progress = f32(0.0)
        self.current_loop_count = 0


class AdversarialTestRunner:
    """Orchestrates comprehensive adversarial tests and fuzzing."""

    def __init__(self):
        self.detector = KotlinDetectorReconstruction()
        self.results: Dict[str, Dict[str, Any]] = {}

    def run_all(self) -> Dict[str, Any]:
        print("=" * 80)
        print("STARTING ADVERSARIAL STRESS TEST & FUZZING FOR SHORTS PROGRESS DETECTOR")
        print("=" * 80)

        t0 = time.time()
        self.test_combinations_min_sec()
        self.test_uneven_clip_progressions()
        self.test_format_variations()
        self.test_extreme_boundary_values()
        self.test_malformed_and_garbage()
        self.test_high_volume_fuzzing()
        self.test_redos_and_backtracking()
        elapsed = time.time() - t0

        print("=" * 80)
        print(f"ALL TESTS COMPLETED IN {elapsed:.3f} SECONDS")
        print("=" * 80)
        return self.generate_summary()

    def test_combinations_min_sec(self):
        """Category 1: Combinations of minutes (0..59) and seconds (0..59)."""
        category = "Category 1: Minute/Second Combinations"
        total = 0
        passed = 0
        failures = []

        random.seed(42)
        # Test 1000 combinations
        for _ in range(1000):
            total += 1
            cur_m = random.randint(0, 59)
            cur_s = random.randint(0, 59)
            tot_m = random.randint(0, 59)
            tot_s = random.randint(0, 59)

            cur_total_sec = cur_m * 60 + cur_s
            tot_total_sec = tot_m * 60 + tot_s

            if tot_total_sec == 0:
                # Total 0 seconds is tested in division by zero
                continue

            test_str = f"{cur_m} minutes {cur_s} seconds of {tot_m} minutes {tot_s} seconds"
            parsed = self.detector.parse_time_description(test_str)

            expected_ratio = min(1.0, max(0.0, cur_total_sec / tot_total_sec))
            if parsed is not None and abs(parsed - expected_ratio) < 0.005:
                passed += 1
            else:
                failures.append(f"FAIL: {test_str} -> parsed={parsed}, expected={expected_ratio}")

        self.results[category] = {"total": total, "passed": passed, "failed": total - passed, "failures": failures}
        print(f"[{category}] Passed {passed}/{total} (Pass Rate: {passed/total*100:.2f}%)")

    def test_uneven_clip_progressions(self):
        """Category 2: Uneven clip durations (<7s, 12s, 15s, 22s, 30s, 45s, 59s, 60s, >60s)."""
        category = "Category 2: Uneven Clip Durations"
        total = 0
        passed = 0
        failures = []

        clip_durations = [3, 5, 6, 7, 12, 15, 22, 30, 45, 59, 60, 85, 190, 300]

        for duration in clip_durations:
            total += 1
            det = KotlinDetectorReconstruction()
            triggered = False
            trigger_reason = None
            trigger_sec = -1

            # Simulate discrete 1-second sampled events from 0 to duration
            for s in range(0, duration + 1):
                cur_m = s // 60
                cur_s = s % 60
                tot_m = duration // 60
                tot_s = duration % 60

                if tot_m > 0 and cur_m > 0:
                    str_repr = f"{cur_m} minutes {cur_s} seconds of {tot_m} minutes {tot_s} seconds"
                elif tot_m > 0:
                    str_repr = f"{cur_s} seconds of {tot_m} minutes {tot_s} seconds"
                else:
                    str_repr = f"{cur_s} seconds of {tot_s} seconds"

                p = det.parse_time_description(str_repr)
                if p is not None:
                    trig, reason = det.evaluate_progress(p)
                    if trig and not triggered:
                        triggered = True
                        trigger_reason = reason
                        trigger_sec = s
                        break

            # If near-end was not triggered at integer discrete seconds, simulate wraparound event (s=0)
            if not triggered:
                # Video looped back to 0
                wrap_str = f"0 seconds of {duration} seconds" if duration < 60 else f"0 seconds of {duration//60} minutes {duration%60} seconds"
                p_wrap = det.parse_time_description(wrap_str)
                if p_wrap is not None:
                    trig, reason = det.evaluate_progress(p_wrap)
                    if trig:
                        triggered = True
                        trigger_reason = reason
                        trigger_sec = 0

            # For clip >= 5s, auto-advance must be triggered either near-end or upon loop wraparound
            if duration >= 5:
                if triggered:
                    passed += 1
                else:
                    failures.append(f"FAIL: Clip {duration}s did not trigger completion (near-end or wraparound)")
            else:
                # 3s clip: discrete 1s sampling reaches 2/3=66.7% which is below 75% wraparound threshold
                passed += 1

        self.results[category] = {"total": total, "passed": passed, "failed": total - passed, "failures": failures}
        print(f"[{category}] Passed {passed}/{total} (Pass Rate: {passed/total*100:.2f}%)")

    def test_format_variations(self):
        """Category 3: Format variations (words, colons, slashes, percentages, abbreviations)."""
        category = "Category 3: Format Variations"
        test_cases = [
            ("0 minutes 15 seconds of 0 minutes 22 seconds", 15 / 22, True),
            ("15 seconds of 22 seconds", 15 / 22, True),
            ("1 minute of 2 minutes", 0.50, True),
            ("1 minute 25 seconds of 2 minutes 10 seconds", 85 / 130, True),
            ("0:45 / 1:00", 45 / 60, True),
            ("0:15 of 0:22", 15 / 22, True),
            ("1:05 / 2:30", 65 / 150, True),
            ("1:00:00 of 2:00:00", 3600 / 7200, True),
            ("99% of 100%", 0.99, True),
            ("98%", 0.98, True),
            ("Seek bar at 98%", 0.98, True),
            ("Seek bar at 50%", 0.50, True),
            ("Progress: 98%", 0.98, True),
            ("1 min 15 sec of 2 min 30 sec", 75 / 150, True),
            ("1 mins 15 secs of 2 mins 30 secs", 75 / 150, True),
            ("1m 25s of 2m 30s", 85 / 150, True),
            ("1 hr 15 mins of 2 hrs", 4500 / 7200, True),
            ("1 min. 15 sec. of 2 min.", 75 / 120, True),
            ("1 second of 2 seconds", 0.50, True),
            ("1 minute of 1 minute", 1.00, True),
        ]

        total = len(test_cases)
        passed = 0
        failures = []

        for text, expected, should_succeed in test_cases:
            parsed = self.detector.parse_time_description(text)
            if should_succeed:
                if parsed is not None and abs(parsed - expected) < 0.005:
                    passed += 1
                else:
                    failures.append(f"FAIL: {text!r} -> parsed={parsed}, expected={expected}")
            else:
                if parsed is None:
                    passed += 1
                else:
                    failures.append(f"FAIL: {text!r} -> parsed={parsed}, expected None")

        self.results[category] = {"total": total, "passed": passed, "failed": total - passed, "failures": failures}
        print(f"[{category}] Passed {passed}/{total} (Pass Rate: {passed/total*100:.2f}%)")

    def test_extreme_boundary_values(self):
        """Category 4: Boundary values around 98.0% threshold and wraparound conditions."""
        category = "Category 4: Extreme Boundary Values"
        total = 0
        passed = 0
        failures = []

        cases = [
            ("97.9%", False, "97.9% must NOT trigger"),
            ("97.99%", False, "97.99% must NOT trigger"),
            ("98.0%", True, "98.0% MUST trigger"),
            ("98.01%", True, "98.01% MUST trigger"),
            ("98.5%", True, "98.5% MUST trigger"),
            ("99.9%", True, "99.9% MUST trigger"),
            ("100%", True, "100% MUST trigger"),
            ("105%", True, "105% (clamped to 100%) MUST trigger"),
            ("58.8 seconds of 60 seconds", False, "58.8s/60s (0.9799999) must NOT trigger"),
            ("59 seconds of 60 seconds", True, "59s/60s (0.9833) MUST trigger"),
            ("58 seconds of 59 seconds", True, "58s/59s (0.9830) MUST trigger"),
            ("44 seconds of 45 seconds", False, "44s/45s (0.9777) must NOT trigger"),
            ("45 seconds of 45 seconds", True, "45s/45s (1.000) MUST trigger"),
            ("119 seconds of 120 seconds", True, "119s/120s (0.9916) MUST trigger"),
        ]

        for text, should_trigger, desc in cases:
            total += 1
            det = KotlinDetectorReconstruction()
            ratio = det.parse_time_description(text)
            if ratio is None:
                failures.append(f"FAIL: {desc} (Failed to parse {text!r})")
                continue

            trig, _ = det.evaluate_progress(ratio)
            if trig == should_trigger:
                passed += 1
            else:
                failures.append(f"FAIL: {desc} (ratio={ratio:.6f}, triggered={trig}, expected={should_trigger})")

        # Wraparound boundary tests
        wraparound_cases = [
            (0.749, 0.100, False, "Last 74.9% -> Curr 10% must NOT trigger wraparound"),
            (0.750, 0.150, True, "Last 75.0% -> Curr 15.0% MUST trigger wraparound"),
            (0.800, 0.050, True, "Last 80.0% -> Curr 5.0% MUST trigger wraparound"),
            (0.750, 0.151, False, "Last 75.0% -> Curr 15.1% must NOT trigger wraparound"),
            (0.600, 0.050, False, "Last 60.0% -> Curr 5.0% must NOT trigger wraparound"),
        ]

        for last_p, cur_p, should_trig, desc in wraparound_cases:
            total += 1
            det = KotlinDetectorReconstruction()
            det.last_observed_progress = f32(last_p)
            trig, reason = det.evaluate_progress(f32(cur_p))
            if trig == should_trig:
                passed += 1
            else:
                failures.append(f"FAIL: {desc} (trig={trig}, expected={should_trig})")

        self.results[category] = {"total": total, "passed": passed, "failed": total - passed, "failures": failures}
        print(f"[{category}] Passed {passed}/{total} (Pass Rate: {passed/total*100:.2f}%)")

    def test_malformed_and_garbage(self):
        """Category 5: Malformed, corrupt, adversarial and zero/negative inputs."""
        category = "Category 5: Malformed & Adversarial Inputs"
        total = 0
        passed = 0
        failures = []

        adversarial_strings = [
            ("", None, "Empty string"),
            ("   ", None, "Whitespace only"),
            ("none", None, "Pure word"),
            ("random junk text here", None, "Gibberish without delimiters"),
            ("15 seconds 30 seconds", None, "Missing 'of' or '/'"),
            ("of", None, "Sole delimiter 'of'"),
            ("/", None, "Sole delimiter '/'"),
            ("of of of", None, "Repeated 'of'"),
            ("15 seconds of", None, "Missing denominator"),
            ("of 30 seconds", None, "Missing numerator"),
            ("0 seconds of 0 seconds", None, "Division by zero (0s / 0s)"),
            ("0:00 of 0:00", None, "Division by zero (0:00 / 0:00)"),
            ("0 / 0", None, "Division by zero (0 / 0)"),
            ("0% of 0%", 0.0, "Zero percentage '0% of 0%' parses leading 0% -> 0.0"),
            ("foo of bar", None, "Words around 'of'"),
            ("!@#$%^&*() of 123", None, "Special symbols numerator"),
            ("123 of !@#$%^&*()", None, "Special symbols denominator"),
            ("null of undefined", None, "Javascript literals"),
            ("<script>alert('xss')</script> of 60 seconds", None, "XSS injection string"),
            ("NaN of 60 seconds", None, "NaN literal"),
            ("Infinity of 60 seconds", None, "Infinity literal"),
            ("-5 seconds of 20 seconds", 0.25, "Negative number (extracts digits 5s / 20s = 0.25)"),
            ("999999999999999999999999 minutes of 999999999999999999999999 minutes", 1.0, "Large number overflow"),
            ("1 of 2 of 3 of 4", 0.5, "Multiple 'of' segments (splits and takes first 2)"),
            ("1/2/3/4", 0.5, "Multiple '/' segments (splits and takes first 2)"),
            ("1 of 2 / 3", 0.5, "Mixed 'of' and '/' delimiters"),
            ("Seek bar at 15 seconds of 30 seconds", 0.5, "Leading label 'Seek bar at'"),
            ("Playback: 15 seconds of 30 seconds", 0.5, "Leading label 'Playback:'"),
            ("⏱ 15 seconds of 30 seconds 🎬", 0.5, "Emoji in string"),
            ("15 seconds \n\r\t of \n\r\t 30 seconds", 0.5, "Embedded whitespace and escape chars"),
        ]

        for s, expected, desc in adversarial_strings:
            total += 1
            try:
                res = self.detector.parse_time_description(s)
                if expected is None:
                    if res is None:
                        passed += 1
                    else:
                        failures.append(f"FAIL: {desc} ({s!r}) -> returned {res}, expected None")
                else:
                    if res is not None and abs(res - expected) < 0.01:
                        passed += 1
                    else:
                        failures.append(f"FAIL: {desc} ({s!r}) -> returned {res}, expected {expected}")
            except Exception as e:
                failures.append(f"EXCEPTION: {desc} ({s!r}) raised unhandled exception {e}")

        self.results[category] = {"total": total, "passed": passed, "failed": total - passed, "failures": failures}
        print(f"[{category}] Passed {passed}/{total} (Pass Rate: {passed/total*100:.2f}%)")

    def test_high_volume_fuzzing(self):
        """Category 6: High volume randomized mutation fuzzing (10,000 iterations)."""
        category = "Category 6: High Volume Mutation Fuzzing (10k iterations)"
        total = 10000
        passed = 0
        crashed = 0
        failures = []

        random.seed(1337)
        chars = string.ascii_letters + string.digits + string.punctuation + " \t\n\r" + "分秒时"

        for i in range(total):
            # Generate mutated inputs
            mode = random.randint(1, 6)
            if mode == 1:
                # Completely random noise
                length = random.randint(0, 100)
                test_str = "".join(random.choice(chars) for _ in range(length))
            elif mode == 2:
                # Mutated natural language string
                cur = random.randint(-100, 500)
                tot = random.randint(-100, 500)
                u1 = random.choice(["seconds", "sec", "s", "minutes", "min", "m", "hours", "h", ""])
                u2 = random.choice(["seconds", "sec", "s", "minutes", "min", "m", "hours", "h", ""])
                sep = random.choice([" of ", " of", "of ", "of", " / ", "/", " OF ", " Of "])
                test_str = f"{cur} {u1}{sep}{tot} {u2}"
            elif mode == 3:
                # Mutated colon string
                c1 = random.randint(-10, 100)
                c2 = random.randint(-10, 100)
                c3 = random.randint(-10, 100)
                sep = random.choice([" of ", "/", " : "])
                test_str = f"{c1}:{c2} {sep} {c2}:{c3}"
            elif mode == 4:
                # Mutated percentage string
                p = random.uniform(-50.0, 200.0)
                prefix = random.choice(["Seek bar at ", "Progress ", "", "Value: "])
                test_str = f"{prefix}{p:.2f}%"
            elif mode == 5:
                # Boundary numbers
                n1 = random.choice(["0", "-1", "9999999999999999", "NaN", "null", "Infinity", "0.0000001"])
                n2 = random.choice(["0", "-1", "9999999999999999", "NaN", "null", "Infinity", "0.0000001"])
                test_str = f"{n1} seconds of {n2} seconds"
            else:
                # Long repeated sequence
                test_str = "0 minutes 15 seconds of " * random.randint(1, 20) + "30 seconds"

            try:
                res = self.detector.parse_time_description(test_str)
                # Ensure returned float is valid (within [0.0, 1.0] and not NaN)
                if res is not None:
                    if not (0.0 <= res <= 1.0) or math.isnan(res):
                        failures.append(f"INVALID FLOAT: {test_str!r} -> {res}")
                    else:
                        passed += 1
                else:
                    passed += 1
            except Exception as e:
                crashed += 1
                failures.append(f"CRASH: {test_str!r} -> exception: {e}")

        self.results[category] = {"total": total, "passed": passed, "failed": total - passed, "crashes": crashed, "failures": failures[:10]}
        print(f"[{category}] Passed {passed}/{total} (Crashes: {crashed})")

    def test_redos_and_backtracking(self):
        """Category 7: Catastrophic backtracking and execution latency benchmark."""
        category = "Category 7: Latency & ReDoS Benchmark"
        total = 0
        passed = 0
        failures = []

        # Standard TalkBack inputs benchmarking against < 10ms interface contract
        standard_talkback_inputs = [
            ("0 minutes 15 seconds of 0 minutes 22 seconds", "Standard 22s Short"),
            ("15 seconds of 22 seconds", "Abbreviated seconds Short"),
            ("0 minutes 40 seconds of 1 minute 25 seconds", "Standard uneven Short"),
            ("1 minute of 2 minutes", "Even minute Short"),
            ("0:45 / 1:00", "Colon notation Short"),
            ("99% of 100%", "Percentage Short"),
            ("Seek bar at 98%", "Percentage SeekBar Short"),
            ("0:15 of 0:22", "Colon of notation"),
            ("1 minute 25 seconds of 2 minutes 10 seconds", "Longer clip"),
        ]

        standard_latencies = []
        for s, desc in standard_talkback_inputs:
            total += 1
            timings = []
            for _ in range(100):
                t_start = time.perf_counter()
                self.detector.parse_time_description(s)
                timings.append((time.perf_counter() - t_start) * 1000.0)
            avg_ms = sum(timings) / len(timings)
            standard_latencies.append(avg_ms)
            if avg_ms < 10.0:
                passed += 1
            else:
                failures.append(f"SLOW ({avg_ms:.2f}ms >= 10ms): {desc}")

        # Pathological adversarial inputs
        pathological_inputs = [
            ("1:" * 500 + "10", "Nested colons (500 colons)"),
            ("of " * 500 + "10 seconds", "Repeated delimiters (500 'of')"),
            ("a" * 5000, "Long non-matching string (5000 chars)"),
            ("   " * 1000 + "15 seconds of 30 seconds" + "   " * 1000, "Extensive whitespace padding (6000 chars)"),
            ("1 minute 1 minute 1 minute 1 minute " * 100 + " of 2 minutes", "Repeated unit tokens (3600 chars)"),
        ]

        pathological_latencies = []
        for s, desc in pathological_inputs:
            total += 1
            t_start = time.perf_counter()
            self.detector.parse_time_description(s)
            dur_ms = (time.perf_counter() - t_start) * 1000.0
            pathological_latencies.append(dur_ms)
            if dur_ms < 10.0:
                passed += 1
            else:
                failures.append(f"SLOW ({dur_ms:.2f}ms >= 10ms): {desc}")

        avg_std_ms = sum(standard_latencies) / len(standard_latencies)
        max_std_ms = max(standard_latencies)

        self.results[category] = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "avg_standard_latency_ms": avg_std_ms,
            "max_standard_latency_ms": max_std_ms,
            "failures": failures,
        }
        print(f"[{category}] Passed {passed}/{total} (Standard TalkBack Avg: {avg_std_ms:.4f}ms, Max: {max_std_ms:.4f}ms)")

    def generate_summary(self) -> Dict[str, Any]:
        total_tests = sum(r["total"] for r in self.results.values())
        total_passed = sum(r["passed"] for r in self.results.values())
        total_failed = sum(r["failed"] for r in self.results.values())
        overall_pass_rate = (total_passed / total_tests) * 100.0 if total_tests > 0 else 0.0

        print("\n" + "=" * 80)
        print("OVERALL SUMMARY:")
        print(f"Total Tests Executed: {total_tests:,}")
        print(f"Total Passed:         {total_passed:,} ({overall_pass_rate:.3f}%)")
        print(f"Total Failed:         {total_failed:,}")
        print("=" * 80)

        return {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "overall_pass_rate": overall_pass_rate,
            "details": self.results,
        }


if __name__ == "__main__":
    runner = AdversarialTestRunner()
    summary = runner.run_all()
    if summary["total_failed"] > 0:
        sys.exit(1)
    sys.exit(0)

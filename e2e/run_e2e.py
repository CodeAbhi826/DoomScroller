#!/usr/bin/env python3
"""DoomScroller E2E Automated Test Runner.

Executes 4 tiers of automated test suites:
- Tier 1: Feature Coverage (live playback detection, string parsing, gesture safety, cooldown, smart pause)
- Tier 2: Boundary & Corner Cases (very short/long clips, wraparound, rapid toggling, watchdog freeze, malformed inputs)
- Tier 3: Cross-Feature Combinations (comments opened at 95%, manual pause at 99%, manual resume, consecutive navigation)
- Tier 4: Real-world Workload Scenarios (3+ consecutive Shorts, <300ms SLA, live simulation, zero crashes)

Usage:
    python3 e2e/run_e2e.py [--tier {1,2,3,4,all}] [--device 192.168.1.40:5555] [--live] [--report-json <path>]
"""

import argparse
import json
import os
import sys
import time
import unittest
from typing import Dict, List

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e2e.suites.tier1_feature_coverage import TestTier1FeatureCoverage
from e2e.suites.tier2_boundary_corner import TestTier2BoundaryCorner
from e2e.suites.tier3_cross_feature import TestTier3CrossFeature
from e2e.suites.tier4_real_world import TestTier4RealWorldWorkloads


class TestResultCollector(unittest.TestResult):

    def __init__(self):
        super().__init__()
        self.test_details: List[Dict] = []
        self._start_time = 0.0

    def startTest(self, test):
        super().startTest(test)
        self._start_time = time.time()

    def addSuccess(self, test):
        super().addSuccess(test)
        duration_ms = (time.time() - self._start_time) * 1000
        self.test_details.append(
            {
                "test": test.id(),
                "name": test._testMethodName,
                "doc": test.shortDescription() or "",
                "status": "PASS",
                "duration_ms": round(duration_ms, 2),
                "error": None,
            }
        )

    def addFailure(self, test, err):
        super().addFailure(test, err)
        duration_ms = (time.time() - self._start_time) * 1000
        self.test_details.append(
            {
                "test": test.id(),
                "name": test._testMethodName,
                "doc": test.shortDescription() or "",
                "status": "FAIL",
                "duration_ms": round(duration_ms, 2),
                "error": self._exc_info_to_string(err, test),
            }
        )

    def addError(self, test, err):
        super().addError(test, err)
        duration_ms = (time.time() - self._start_time) * 1000
        self.test_details.append(
            {
                "test": test.id(),
                "name": test._testMethodName,
                "doc": test.shortDescription() or "",
                "status": "ERROR",
                "duration_ms": round(duration_ms, 2),
                "error": self._exc_info_to_string(err, test),
            }
        )


def build_suite(tier: str) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    if tier in ("1", "all"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier1FeatureCoverage))
    if tier in ("2", "all"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier2BoundaryCorner))
    if tier in ("3", "all"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier3CrossFeature))
    if tier in ("4", "all"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier4RealWorldWorkloads))

    return suite


def main():
    parser = argparse.ArgumentParser(description="DoomScroller E2E Test Suite Runner")
    parser.add_argument(
        "--tier",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Test tier to execute (default: all)",
    )
    parser.add_argument(
        "--device",
        default="192.168.1.40:5555",
        help="Target device serial / IP (default: 192.168.1.40:5555)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute against live physical device (NOTE: Default is safe host execution mode)",
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help="Optional path to output structured JSON test results",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    print("=" * 72)
    print(" DOOMSCROLLER E2E TEST RUNNER")
    print(f" Target Device : {args.device}")
    print(f" Mode          : {'LIVE DEVICE' if args.live else 'OFFLINE / SIMULATION (Safe Mode)'}")
    print(f" Target Tier   : {args.tier.upper()}")
    print("=" * 72)

    suite = build_suite(args.tier)
    collector = TestResultCollector()

    start_wall_time = time.time()
    suite.run(collector)
    total_duration_sec = time.time() - start_wall_time

    # Group by tier
    tier_summary = {"Tier 1": [], "Tier 2": [], "Tier 3": [], "Tier 4": []}
    for item in collector.test_details:
        test_id = item["test"]
        if "tier1" in test_id:
            tier_summary["Tier 1"].append(item)
        elif "tier2" in test_id:
            tier_summary["Tier 2"].append(item)
        elif "tier3" in test_id:
            tier_summary["Tier 3"].append(item)
        elif "tier4" in test_id:
            tier_summary["Tier 4"].append(item)

    print("\nRESULTS SUMMARY:")
    print("-" * 72)
    for tier_name, tests in tier_summary.items():
        if not tests:
            continue
        passed = sum(1 for t in tests if t["status"] == "PASS")
        failed = sum(1 for t in tests if t["status"] == "FAIL")
        errors = sum(1 for t in tests if t["status"] == "ERROR")
        tier_status = "PASS" if (failed == 0 and errors == 0) else "FAIL"
        print(f" {tier_name:<10}: {len(tests):2d} tests | {passed:2d} passed | {failed:2d} failed | {errors:2d} errors [{tier_status}]")
        if args.verbose:
            for t in tests:
                print(f"   - {t['name']:<50} {t['status']} ({t['duration_ms']:.1f}ms)")
                if t["error"]:
                    print(f"     ERROR: {t['error'].strip().splitlines()[-1]}")

    print("-" * 72)
    total_tests = len(collector.test_details)
    total_passed = sum(1 for t in collector.test_details if t["status"] == "PASS")
    total_failed = sum(1 for t in collector.test_details if t["status"] == "FAIL")
    total_errors = sum(1 for t in collector.test_details if t["status"] == "ERROR")

    overall_status = "PASS" if (total_failed == 0 and total_errors == 0) else "FAIL"
    print(f" TOTAL: {total_tests} tests in {total_duration_sec:.2f}s | {total_passed} Passed | {total_failed} Failed | {total_errors} Errors")
    print(f" OVERALL VERDICT: {overall_status}")
    print("=" * 72)

    # Optional JSON output
    if args.report_json:
        report = {
            "device": args.device,
            "mode": "live" if args.live else "simulation",
            "tier": args.tier,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_sec": round(total_duration_sec, 3),
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "errors": total_errors,
            "overall_status": overall_status,
            "tests": collector.test_details,
        }
        with open(args.report_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f" Structured report written to: {args.report_json}")

    sys.exit(0 if overall_status == "PASS" else 1)


if __name__ == "__main__":
    main()

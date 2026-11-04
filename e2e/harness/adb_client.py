"""ADB Client wrapper for DoomScroller E2E Testing.

Always enforces -s <device_id> to disambiguate multiple attached devices.
Supports live execution as well as a mock/offline mode for safe local validation.
"""

import os
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple


class ADBClient:
    DEFAULT_DEVICE_ID = "192.168.1.40:5555"

    def __init__(self, device_id: str = DEFAULT_DEVICE_ID, mock_mode: bool = False):
        self.device_id = device_id or self.DEFAULT_DEVICE_ID
        self.mock_mode = mock_mode
        self._mock_responses: Dict[str, Tuple[int, str, str]] = {}
        self._mock_ui_hierarchy: Optional[str] = None

    def set_mock_response(self, cmd_pattern: str, exit_code: int, stdout: str, stderr: str = ""):
        """Register a mock response for commands matching regex pattern."""
        self._mock_responses[cmd_pattern] = (exit_code, stdout, stderr)

    def set_mock_ui_hierarchy(self, xml_content: str):
        """Set the mock XML string to return for uiautomator dump."""
        self._mock_ui_hierarchy = xml_content

    def _build_adb_command(self, args: List[str]) -> List[str]:
        """Constructs adb command ensuring -s <device_id> is present."""
        cmd = ["adb", "-s", self.device_id]
        cmd.extend(args)
        return cmd

    def run(self, args: List[str], timeout: int = 30) -> Tuple[int, str, str]:
        """Execute arbitrary adb command with -s <device_id>."""
        cmd_str = " ".join(args)

        if self.mock_mode:
            for pattern, resp in self._mock_responses.items():
                if re.search(pattern, cmd_str):
                    return resp
            # Default mock fallback
            return 0, "", ""

        full_cmd = self._build_adb_command(args)
        try:
            res = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds: {' '.join(full_cmd)}"
        except Exception as e:
            return -1, "", str(e)

    def shell(self, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
        """Execute command in adb shell."""
        return self.run(["shell", cmd], timeout=timeout)

    def get_state(self) -> str:
        """Get device state (device, offline, unauthorized, etc.)."""
        if self.mock_mode:
            return "device"
        code, out, _ = self.run(["get-state"], timeout=10)
        return out.strip() if code == 0 else "unknown"

    def get_prop(self, prop_name: str) -> str:
        """Query getprop value."""
        if self.mock_mode:
            props = {
                "ro.product.model": "SM-E146B",
                "ro.product.manufacturer": "samsung",
                "ro.build.version.release": "14",
                "ro.build.version.sdk": "34",
            }
            return props.get(prop_name, "")
        code, out, _ = self.shell(f"getprop {prop_name}")
        return out.strip() if code == 0 else ""

    def get_display_metrics(self) -> Tuple[int, int, int]:
        """Returns (width, height, dpi)."""
        if self.mock_mode:
            return 720, 1560, 280
        code, out, _ = self.shell("wm size")
        width, height = 720, 1560
        m = re.search(r"(\d+)x(\d+)", out)
        if m:
            width, height = int(m.group(1)), int(m.group(2))

        code_d, out_d, _ = self.shell("wm density")
        density = 280
        m_d = re.search(r"(\d+)", out_d)
        if m_d:
            density = int(m_d.group(1))
        return width, height, density

    def get_focused_window(self) -> str:
        """Get current focused window name."""
        if self.mock_mode:
            return "com.google.android.youtube/com.google.android.apps.youtube.app.watchwhile.InternalMainActivity"
        code, out, _ = self.shell("dumpsys window | grep -E 'mCurrentFocus'")
        return out.strip()

    def launch_youtube_shorts(self) -> bool:
        """Launch YouTube Shorts via explicit deep link."""
        if self.mock_mode:
            return True
        code, _, _ = self.shell("am start -a android.intent.action.VIEW -d 'https://www.youtube.com/shorts' -p com.google.android.youtube")
        return code == 0

    def tap(self, x: int, y: int) -> bool:
        """Send tap input."""
        if self.mock_mode:
            return True
        code, _, _ = self.shell(f"input tap {x} {y}")
        return code == 0

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 200) -> bool:
        """Send swipe input."""
        if self.mock_mode:
            return True
        code, _, _ = self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        return code == 0

    def keyevent(self, keycode: int) -> bool:
        """Send keyevent (e.g. 4 for BACK)."""
        if self.mock_mode:
            return True
        code, _, _ = self.shell(f"input keyevent {keycode}")
        return code == 0

    def dump_ui_hierarchy(self, remote_path: str = "/sdcard/e2e_dump.xml") -> Optional[str]:
        """Dump UI hierarchy with uiautomator and return XML string."""
        if self.mock_mode:
            if self._mock_ui_hierarchy:
                return self._mock_ui_hierarchy
            return (
                '<hierarchy rotation="0">'
                '<node index="0" text="" resource-id="com.google.android.youtube:id/reel_watch_fragment_root" class="android.widget.FrameLayout" package="com.google.android.youtube">'
                '<node index="1" text="" resource-id="com.google.android.youtube:id/reel_time_bar" class="android.view.ViewGroup" package="com.google.android.youtube">'
                '<node index="0" text="" resource-id="" class="android.widget.SeekBar" package="com.google.android.youtube" '
                'content-desc="0 minutes 15 seconds of 0 minutes 30 seconds" bounds="[0,1407][720,1491]" />'
                '</node></node></hierarchy>'
            )

        self.shell(f"uiautomator dump {remote_path}")
        code, out, _ = self.shell(f"cat {remote_path}")
        if code == 0 and out.strip().startswith("<?xml") or "<hierarchy" in out:
            return out
        return None

    def clear_logcat(self) -> bool:
        """Clear device logcat buffer."""
        if self.mock_mode:
            return True
        code, _, _ = self.run(["logcat", "-c"])
        return code == 0

    def get_logcat_slice(self, tags: Optional[List[str]] = None, lines: int = 100) -> str:
        """Fetch recent logcat lines for specified tags."""
        if self.mock_mode:
            return ""
        args = ["logcat", "-d", "-t", str(lines)]
        if tags:
            tag_args = ["-s"] + tags
            args.extend(tag_args)
        code, out, _ = self.run(args)
        return out if code == 0 else ""

    def is_service_enabled(self, service_name: str = "com.doomscroller.app/.service.AutoScrollAccessibilityService") -> bool:
        """Check if DoomScroller accessibility service is enabled."""
        if self.mock_mode:
            return True
        code, out, _ = self.shell("settings get secure enabled_accessibility_services")
        return code == 0 and service_name in out

    def get_app_pid(self, package_name: str = "com.doomscroller.app") -> Optional[int]:
        """Get PID of running package."""
        if self.mock_mode:
            return 1247
        code, out, _ = self.shell(f"pidof {package_name}")
        if code == 0 and out.strip():
            pids = out.strip().split()
            if pids:
                return int(pids[0])
        return None

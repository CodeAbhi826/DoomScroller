"""YouTube Shorts Controller for E2E testing interactions."""

import re
from typing import Optional, Tuple
from .adb_client import ADBClient
from .parser_oracle import TimeParserOracle


class YouTubeController:

    def __init__(self, adb: ADBClient):
        self.adb = adb

    def launch_shorts(self) -> bool:
        """Launch YouTube Shorts via explicit VIEW intent."""
        return self.adb.launch_youtube_shorts()

    def scroll_to_next(self, duration_ms: int = 180) -> bool:
        """Simulate an upward swipe to advance to the next Short."""
        width, height, _ = self.adb.get_display_metrics()
        sx = int(width * 0.5)
        sy = int(height * 0.76)
        ex = sx
        ey = int(height * 0.22)
        return self.adb.swipe(sx, sy, ex, ey, duration_ms)

    def scroll_to_previous(self, duration_ms: int = 180) -> bool:
        """Simulate a downward swipe to return to previous Short."""
        width, height, _ = self.adb.get_display_metrics()
        sx = int(width * 0.5)
        sy = int(height * 0.25)
        ex = sx
        ey = int(height * 0.75)
        return self.adb.swipe(sx, sy, ex, ey, duration_ms)

    def toggle_playback(self) -> bool:
        """Tap center of video viewport to pause or resume playback."""
        width, height, _ = self.adb.get_display_metrics()
        cx = int(width * 0.5)
        cy = int(height * 0.5)
        return self.adb.tap(cx, cy)

    def open_comments_sheet(self) -> bool:
        """Tap the YouTube Shorts comments icon on the right action bar (~x=660, y=960 on 720x1560 screen)."""
        width, height, _ = self.adb.get_display_metrics()
        btn_x = int(width * 0.916)
        btn_y = int(height * 0.615)
        return self.adb.tap(btn_x, btn_y)

    def close_comments_sheet(self) -> bool:
        """Dismiss the comments bottom sheet via Android system Back."""
        return self.adb.keyevent(4)

    def extract_live_progress(self) -> Tuple[Optional[float], Optional[str]]:
        """Dumps current UI hierarchy, extracts reel_time_bar SeekBar content-description,

        and computes exact progress float. Returns (progress_ratio, raw_content_desc).
        """
        xml = self.adb.dump_ui_hierarchy()
        if not xml:
            return None, None

        # Look for SeekBar content-desc inside reel_time_bar
        m = re.search(r'class="android\.widget\.SeekBar"[^>]*content-desc="([^"]+)"', xml)
        if not m:
            # Fallback search for any node with "X of Y"
            m = re.search(r'content-desc="([^"]*(?:of|/)[^"]*)"', xml)

        if m:
            desc = m.group(1)
            ratio = TimeParserOracle.parse_time_description(desc)
            return ratio, desc

        return None, None

    def is_comments_drawer_visible(self) -> bool:
        """Checks if comments sheet is visible in current UI hierarchy."""
        xml = self.adb.dump_ui_hierarchy()
        if not xml:
            return False
        return bool(re.search(r'resource-id="[^"]*(?:comment_sheet|comments_header|design_bottom_sheet)"', xml))

    def is_video_paused(self) -> bool:
        """Checks if video is currently paused (displays 'Play video' control)."""
        xml = self.adb.dump_ui_hierarchy()
        if not xml:
            return False
        return 'content-desc="Play video"' in xml

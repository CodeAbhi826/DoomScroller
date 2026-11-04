"""Event Simulator for DoomScroller E2E Testing.

Generates realistic UI hierarchies and logcat event streams representing YouTube Shorts
playback, smart pauses, gestures, and corner cases. Enables full deterministic test
execution on host while physical device is undergoing live user testing.
"""

from typing import List


class EventSimulator:

    @staticmethod
    def generate_shorts_ui_dump(
        current_time_str: str = "0 minutes 15 seconds",
        total_time_str: str = "0 minutes 30 seconds",
        comments_open: bool = False,
        video_paused: bool = False,
        include_time_bar: bool = True,
    ) -> str:
        """Generates realistic YouTube Shorts uiautomator XML dump."""
        comments_node = ""
        if comments_open:
            comments_node = (
                '<node index="5" text="" resource-id="com.google.android.youtube:id/comment_sheet" '
                'class="android.widget.FrameLayout" package="com.google.android.youtube" bounds="[0,450][720,1560]">'
                '<node index="0" text="Comments" resource-id="com.google.android.youtube:id/title" '
                'class="android.widget.TextView" package="com.google.android.youtube" bounds="[32,480][300,530]" />'
                '</node>'
            )

        play_button_desc = "Play video" if video_paused else "Pause video"
        play_node = (
            f'<node index="2" text="" resource-id="com.google.android.youtube:id/player_control" '
            f'class="android.widget.ImageView" package="com.google.android.youtube" '
            f'content-desc="{play_button_desc}" bounds="[310,730][410,830]" />'
        )

        time_bar_node = ""
        if include_time_bar:
            time_bar_node = (
                '<node index="1" text="" resource-id="com.google.android.youtube:id/reel_time_bar" '
                'class="android.view.ViewGroup" package="com.google.android.youtube" bounds="[0,0][720,1560]">'
                f'<node index="0" text="" resource-id="" class="android.widget.SeekBar" '
                f'package="com.google.android.youtube" content-desc="{current_time_str} of {total_time_str}" '
                f'bounds="[0,1407][720,1491]" />'
                '</node>'
            )

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<hierarchy rotation="0">\n'
            '  <node index="0" text="" resource-id="com.google.android.youtube:id/reel_watch_fragment_root" '
            'class="android.widget.FrameLayout" package="com.google.android.youtube" bounds="[0,0][720,1560]">\n'
            '    <node index="0" text="" resource-id="com.google.android.youtube:id/reel_recycler" '
            'class="androidx.recyclerview.widget.RecyclerView" package="com.google.android.youtube" bounds="[0,0][720,1560]">\n'
            f'      {play_node}\n'
            f'      {time_bar_node}\n'
            f'      {comments_node}\n'
            '    </node>\n'
            '  </node>\n'
            '</hierarchy>'
        )
        return xml

    @staticmethod
    def generate_single_video_playback_logs(
        duration_sec: int,
        start_hh_mm_ss: str = "14:10:00.000",
        pid: int = 1247,
        tid: int = 1247,
        transition_delay_ms: int = 85,
        gesture_duration_ms: int = 175,
        gesture_cancelled: bool = False,
    ) -> List[str]:
        """Generates logcat stream for a single YouTube Short from 0% to completion and auto-advance."""
        lines = []
        base_h, base_m, base_s = [int(p) for p in start_hh_mm_ss.split(".")[0].split(":")]
        base_ms = int(start_hh_mm_ss.split(".")[1])

        def format_ts(offset_sec: float) -> str:
            total_sec = base_s + offset_sec
            cur_s = int(total_sec) % 60
            cur_m = (base_m + int(total_sec // 60)) % 60
            cur_h = (base_h + int((base_m + int(total_sec // 60)) // 60)) % 24
            cur_ms = int((total_sec - int(total_sec)) * 1000 + base_ms) % 1000
            return f"11-04 {cur_h:02d}:{cur_m:02d}:{cur_s:02d}.{cur_ms:03d}"

        # Progress ticks
        steps = [0.0, 0.15, 0.35, 0.55, 0.75, 0.90, 0.95, 0.985]
        for step in steps:
            t = step * duration_sec
            pct = int(step * 100)
            lines.append(
                f"{format_ts(t)}  {pid}  {tid} D DoomScroller-Detector: Live Progress: {pct}% (last: {max(0, pct - 15)}%)"
            )

        # Completion line at end
        comp_t = duration_sec * 0.985
        lines.append(
            f"{format_ts(comp_t)}  {pid}  {tid} I DoomScroller-Detector: Short completion detected! (Loops watched: 1 / Required: 1)"
        )

        # Gesture dispatch after transition delay
        disp_t = comp_t + (transition_delay_ms / 1000.0)
        lines.append(
            f"{format_ts(disp_t)}  {pid}  {tid} I DoomScroller-Gesture: Dispatching upward scroll gesture: (360, 1185) -> (360, 343) in {gesture_duration_ms}ms"
        )

        # Gesture completed or cancelled
        end_t = disp_t + (gesture_duration_ms / 1000.0)
        if gesture_cancelled:
            lines.append(
                f"{format_ts(end_t)}  {pid}  {tid} W DoomScroller-Gesture: Scroll gesture was cancelled by system"
            )
        else:
            lines.append(
                f"{format_ts(end_t)}  {pid}  {tid} I DoomScroller-Gesture: Scroll gesture completed successfully"
            )

        return lines

    @classmethod
    def generate_workload_3_shorts(cls) -> str:
        """Generates continuous playback logs for 3 consecutive YouTube Shorts:

        - Short 1: 12 seconds (< 15s)
        - Short 2: 32 seconds (~30s)
        - Short 3: 58 seconds (~60s)
        """
        all_lines = [
            "--------- beginning of main",
            "11-04 14:00:00.000  1247  1247 I DoomScroller-Service: DoomScroller Accessibility Service Created and Active",
            "11-04 14:00:00.050  1247  1247 I DoomScroller-Service: DoomScroller Connected to System Accessibility Framework",
        ]

        # Short 1 (12s)
        all_lines.extend(cls.generate_single_video_playback_logs(duration_sec=12, start_hh_mm_ss="14:00:01.000", transition_delay_ms=92))

        # Short 2 (32s)
        all_lines.extend(cls.generate_single_video_playback_logs(duration_sec=32, start_hh_mm_ss="14:00:14.000", transition_delay_ms=88))

        # Short 3 (58s)
        all_lines.extend(cls.generate_single_video_playback_logs(duration_sec=58, start_hh_mm_ss="14:00:47.000", transition_delay_ms=95))

        return "\n".join(all_lines)

    @classmethod
    def generate_comments_pause_logs(cls) -> str:
        """Generates logs for user opening comments drawer, remaining open for 70s (verifying watchdog freeze), then closing drawer and advancing."""
        lines = [
            "--------- beginning of main",
            "11-04 14:05:00.000  1247  1247 D DoomScroller-Detector: Live Progress: 20% (last: 0%)",
            "11-04 14:05:05.000  1247  1247 D DoomScroller-Detector: Live Progress: 40% (last: 20%)",
            # Comments open
            "11-04 14:05:07.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            "11-04 14:05:20.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            "11-04 14:06:00.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",
            "11-04 14:06:20.000  1247  1247 D DoomScroller-Detector: Comments drawer open, auto-scroll paused",  # >70s elapsed, NO watchdog triggered!
            # Comments closed
            "11-04 14:06:25.000  1247  1247 D DoomScroller-Detector: Live Progress: 85% (last: 40%)",
            "11-04 14:06:28.000  1247  1247 D DoomScroller-Detector: Live Progress: 99% (last: 85%)",
            "11-04 14:06:28.010  1247  1247 I DoomScroller-Detector: Short completion detected! (Loops watched: 1 / Required: 1)",
            "11-04 14:06:28.115  1247  1247 I DoomScroller-Gesture: Dispatching upward scroll gesture: (360, 1185) -> (360, 343) in 170ms",
            "11-04 14:06:28.285  1247  1247 I DoomScroller-Gesture: Scroll gesture completed successfully",
        ]
        return "\n".join(lines)

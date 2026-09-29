"""MPV-based audio player backend."""

from __future__ import annotations

import logging
import shutil
import threading
from collections.abc import Callable

import mpv

from ymusic_cli.api import TrackInfo, YMusicAPI

log = logging.getLogger(__name__)


def check_mpv_available() -> bool:
    """Check if mpv is available on the system."""
    return shutil.which("mpv") is not None


class PlayerState:
    """Observable player state."""

    def __init__(self) -> None:
        self.current_track: TrackInfo | None = None
        self.is_playing: bool = False
        self.position: float = 0.0  # seconds
        self.duration: float = 0.0  # seconds
        self.volume: int = 70
        self.queue: list[TrackInfo] = []
        self.queue_index: int = -1
        self.shuffle: bool = False
        self.repeat: str = "off"  # off, one, all

    @property
    def progress(self) -> float:
        """Return playback progress as 0.0–1.0."""
        if self.duration <= 0:
            return 0.0
        return min(self.position / self.duration, 1.0)

    @property
    def position_str(self) -> str:
        m, s = divmod(int(self.position), 60)
        return f"{m}:{s:02d}"

    @property
    def duration_str(self) -> str:
        m, s = divmod(int(self.duration), 60)
        return f"{m}:{s:02d}"


class Player:
    """Audio player wrapping libmpv."""

    def __init__(self, api: YMusicAPI, volume: int = 70) -> None:
        self.api = api
        self.state = PlayerState()
        self.state.volume = volume
        self._mpv: mpv.MPV | None = None
        self._on_track_change: list[Callable[[], None]] = []
        self._on_state_change: list[Callable[[], None]] = []
        self._on_end: list[Callable[[], None]] = []
        self._shutting_down = False
        self._shuffle_order: list[int] = []
        self._shuffle_pos: int = -1
        self._lock = threading.Lock()
        self._init_mpv()

    def _init_mpv(self) -> None:
        """Initialise (or re-initialise) the mpv instance."""
        if self._mpv is not None:
            try:
                self._mpv.terminate()
            except Exception:
                pass
        self._mpv = mpv.MPV(
            video=False,
            ytdl=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
        )
        self._mpv.volume = self.state.volume

        # Observe properties for position updates
        @self._mpv.property_observer("time-pos")
        def _on_time_pos(_name: str, value: float | None) -> None:
            if value is not None and not self._shutting_down:
                self.state.position = value
                self._notify_state_change()

        @self._mpv.property_observer("duration")
        def _on_duration(_name: str, value: float | None) -> None:
            if value is not None and not self._shutting_down:
                self.state.duration = value
                self._notify_state_change()

        @self._mpv.property_observer("pause")
        def _on_pause(_name: str, value: bool | None) -> None:
            if value is not None and not self._shutting_down:
                self.state.is_playing = not value
                self._notify_state_change()

        # End-of-file handler for auto-next
        @self._mpv.event_callback("end-file")
        def _on_end_file(event: mpv.MpvEvent) -> None:
            if self._shutting_down:
                return
            reason = None
            if event and hasattr(event, "data") and event.data:
                reason = getattr(event.data, "reason", None)
            elif event and hasattr(event, "as_dict"):
                try:
                    d = event.as_dict()
                    if d.get("reason") == b"eof":
                        reason = 0
                except Exception:
                    pass

            # reason 0 = EOF in mpv. Ignore STOP(2), QUIT(3), ERROR(4)
            if reason == 0:
                for cb in list(self._on_end):
                    try:
                        cb()
                    except Exception:
                        pass

    def on_track_change(self, callback: Callable[[], None]) -> None:
        self._on_track_change.append(callback)

    def on_state_change(self, callback: Callable[[], None]) -> None:
        self._on_state_change.append(callback)

    def on_end(self, callback: Callable[[], None]) -> None:
        self._on_end.append(callback)

    def _notify_track_change(self) -> None:
        for cb in list(self._on_track_change):
            try:
                cb()
            except Exception:
                pass

    def _notify_state_change(self) -> None:
        for cb in list(self._on_state_change):
            try:
                cb()
            except Exception:
                pass

    def play_track(self, track: TrackInfo) -> bool:
        """Play a single track. Returns False if URL unavailable."""
        if self._shutting_down:
            return False
        url = self.api.get_track_url(track)
        if not url:
            return False
        with self._lock:
            self.state.current_track = track
            self.state.is_playing = True
            self.state.position = 0.0
            self.state.duration = track.duration_ms / 1000.0
            if self._mpv:
                self._mpv.play(url)
                self._mpv.pause = False
        self._notify_track_change()
        return True

    def _build_shuffle_order(self, current_idx: int = 0) -> None:
        """Generate a random playback order putting current_idx first."""
        import random
        n = len(self.state.queue)
        if n == 0:
            self._shuffle_order = []
            self._shuffle_pos = -1
            return
        others = [i for i in range(n) if i != current_idx]
        random.shuffle(others)
        self._shuffle_order = [current_idx] + others
        self._shuffle_pos = 0

    def set_queue(self, tracks: list[TrackInfo], start_index: int = 0) -> bool:
        """Set the play queue and start playing from start_index."""
        self.state.queue = list(tracks)
        if not tracks or start_index < 0 or start_index >= len(tracks):
            self.state.queue_index = -1
            self._shuffle_order = []
            self._shuffle_pos = -1
            return False
        self.state.queue_index = start_index
        if self.state.shuffle:
            self._build_shuffle_order(start_index)
        else:
            self._shuffle_order = list(range(len(tracks)))
            self._shuffle_pos = start_index
        return self.play_track(tracks[start_index])

    def extend_queue(self, new_tracks: list[TrackInfo]) -> None:
        """Extend the existing queue and update shuffle order."""
        import random
        start_idx = len(self.state.queue)
        self.state.queue.extend(new_tracks)
        new_indices = list(range(start_idx, len(self.state.queue)))
        if self.state.shuffle:
            random.shuffle(new_indices)
            self._shuffle_order.extend(new_indices)
        else:
            self._shuffle_order.extend(new_indices)

    def next_track(self) -> bool:
        """Play the next track in queue."""
        if not self.state.queue:
            return False
        if self.state.repeat == "one" and self.state.current_track:
            return self.play_track(self.state.current_track)

        if self.state.shuffle:
            next_pos = self._shuffle_pos + 1
            if next_pos >= len(self._shuffle_order):
                if self.state.repeat == "all":
                    self._build_shuffle_order(self.state.queue_index)
                    next_pos = 0
                else:
                    return False
            self._shuffle_pos = next_pos
            idx = self._shuffle_order[self._shuffle_pos]
        else:
            idx = self.state.queue_index + 1
            if idx >= len(self.state.queue):
                if self.state.repeat == "all":
                    idx = 0
                else:
                    return False
            self.state.queue_index = idx

        self.state.queue_index = idx
        return self.play_track(self.state.queue[idx])

    def prev_track(self) -> bool:
        """Play the previous track in queue or restart current."""
        if not self.state.queue:
            return False
        # If more than 3 seconds in, restart current track
        if self.state.position > 3.0 and self.state.current_track:
            return self.play_track(self.state.current_track)

        if self.state.shuffle:
            prev_pos = self._shuffle_pos - 1
            if prev_pos < 0:
                prev_pos = len(self._shuffle_order) - 1 if self.state.repeat == "all" else 0
            self._shuffle_pos = prev_pos
            idx = self._shuffle_order[self._shuffle_pos]
        else:
            idx = self.state.queue_index - 1
            if idx < 0:
                idx = len(self.state.queue) - 1 if self.state.repeat == "all" else 0
            self.state.queue_index = idx

        self.state.queue_index = idx
        return self.play_track(self.state.queue[idx])

    def toggle_pause(self) -> None:
        """Toggle play/pause."""
        if self._mpv and self.state.current_track:
            self._mpv.pause = not self._mpv.pause

    def pause(self) -> None:
        if self._mpv and self.state.current_track:
            self._mpv.pause = True

    def resume(self) -> None:
        if self._mpv and self.state.current_track:
            self._mpv.pause = False

    def stop(self) -> None:
        """Stop playback."""
        if self._mpv:
            try:
                self._mpv.stop()
            except Exception:
                pass
        self.state.is_playing = False
        self.state.position = 0.0
        self._notify_state_change()

    def seek(self, seconds: float) -> None:
        """Seek relative (positive=forward, negative=backward)."""
        if self._mpv and self.state.current_track and self.state.is_playing:
            try:
                self._mpv.seek(seconds, reference="relative")
            except Exception:
                pass

    def seek_absolute(self, seconds: float) -> None:
        """Seek to absolute position."""
        if self._mpv and self.state.current_track and self.state.is_playing:
            try:
                self._mpv.seek(seconds, reference="absolute")
            except Exception:
                pass

    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        volume = max(0, min(100, volume))
        self.state.volume = volume
        if self._mpv:
            try:
                self._mpv.volume = volume
            except Exception:
                pass
        self._notify_state_change()

    def volume_up(self, step: int = 5) -> None:
        self.set_volume(self.state.volume + step)

    def volume_down(self, step: int = 5) -> None:
        self.set_volume(self.state.volume - step)

    def toggle_repeat(self) -> None:
        """Cycle repeat: off → all → one → off."""
        cycle = {"off": "all", "all": "one", "one": "off"}
        self.state.repeat = cycle.get(self.state.repeat, "off")
        self._notify_state_change()

    def toggle_shuffle(self) -> None:
        """Toggle shuffle mode."""
        self.state.shuffle = not self.state.shuffle
        if self.state.shuffle and self.state.queue:
            cur = max(0, self.state.queue_index)
            self._build_shuffle_order(cur)
        elif not self.state.shuffle and self.state.queue:
            self._shuffle_order = list(range(len(self.state.queue)))
            self._shuffle_pos = self.state.queue_index
        self._notify_state_change()

    def shutdown(self) -> None:
        """Clean up mpv resources safely without segfaults."""
        self._shutting_down = True
        self._on_end.clear()
        self._on_track_change.clear()
        self._on_state_change.clear()
        if self._mpv:
            try:
                self._mpv.terminate()
            except Exception:
                pass
            self._mpv = None

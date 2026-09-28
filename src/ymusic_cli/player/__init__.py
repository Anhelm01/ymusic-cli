"""MPV-based audio player backend."""

from __future__ import annotations

import threading
from typing import Callable, Optional

import mpv

from ymusic_cli.api import TrackInfo, YMusicAPI


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
            if value is not None:
                self.state.position = value
                self._notify_state_change()

        @self._mpv.property_observer("duration")
        def _on_duration(_name: str, value: float | None) -> None:
            if value is not None:
                self.state.duration = value
                self._notify_state_change()

        @self._mpv.property_observer("pause")
        def _on_pause(_name: str, value: bool | None) -> None:
            if value is not None:
                self.state.is_playing = not value
                self._notify_state_change()

        # End-of-file handler for auto-next
        @self._mpv.event_callback("end-file")
        def _on_end_file(event: mpv.MpvEvent) -> None:
            # Only auto-next on natural end (not stop/error)
            if event and hasattr(event, "event") and hasattr(event.event, "reason"):
                reason = event.event.reason
            else:
                reason = None
            # reason 0 = eof in mpv
            if reason == 0 or reason is None:
                for cb in self._on_end:
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
        for cb in self._on_track_change:
            try:
                cb()
            except Exception:
                pass

    def _notify_state_change(self) -> None:
        for cb in self._on_state_change:
            try:
                cb()
            except Exception:
                pass

    def play_track(self, track: TrackInfo) -> bool:
        """Play a single track. Returns False if URL unavailable."""
        url = self.api.get_track_url(track)
        if not url:
            return False
        with self._lock:
            self.state.current_track = track
            self.state.is_playing = True
            self.state.position = 0.0
            self.state.duration = track.duration_ms / 1000.0
            self._mpv.play(url)
            self._mpv.pause = False
        self._notify_track_change()
        return True

    def set_queue(self, tracks: list[TrackInfo], start_index: int = 0) -> bool:
        """Set the play queue and start playing from start_index."""
        self.state.queue = list(tracks)
        self.state.queue_index = start_index
        if tracks:
            return self.play_track(tracks[start_index])
        return False

    def next_track(self) -> bool:
        """Play the next track in queue."""
        if not self.state.queue:
            return False
        idx = self.state.queue_index + 1
        if self.state.repeat == "one":
            idx = self.state.queue_index
        elif idx >= len(self.state.queue):
            if self.state.repeat == "all":
                idx = 0
            else:
                return False
        self.state.queue_index = idx
        return self.play_track(self.state.queue[idx])

    def prev_track(self) -> bool:
        """Play the previous track in queue or restart current."""
        if not self.state.queue:
            return False
        # If more than 3 seconds in, restart current track
        if self.state.position > 3.0:
            return self.play_track(self.state.queue[self.state.queue_index])
        idx = self.state.queue_index - 1
        if idx < 0:
            idx = len(self.state.queue) - 1 if self.state.repeat == "all" else 0
        self.state.queue_index = idx
        return self.play_track(self.state.queue[idx])

    def toggle_pause(self) -> None:
        """Toggle play/pause."""
        if self._mpv:
            self._mpv.pause = not self._mpv.pause

    def pause(self) -> None:
        if self._mpv:
            self._mpv.pause = True

    def resume(self) -> None:
        if self._mpv:
            self._mpv.pause = False

    def stop(self) -> None:
        """Stop playback."""
        if self._mpv:
            self._mpv.stop()
        self.state.is_playing = False
        self.state.position = 0.0
        self._notify_state_change()

    def seek(self, seconds: float) -> None:
        """Seek relative (positive=forward, negative=backward)."""
        if self._mpv:
            self._mpv.seek(seconds, reference="relative")

    def seek_absolute(self, seconds: float) -> None:
        """Seek to absolute position."""
        if self._mpv:
            self._mpv.seek(seconds, reference="absolute")

    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        volume = max(0, min(100, volume))
        self.state.volume = volume
        if self._mpv:
            self._mpv.volume = volume
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
        self._notify_state_change()

    def shutdown(self) -> None:
        """Clean up mpv resources."""
        if self._mpv:
            try:
                self._mpv.terminate()
            except Exception:
                pass
            self._mpv = None

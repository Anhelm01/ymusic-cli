"""Custom Textual widgets for YMusic CLI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Label, ListView, ListItem, ProgressBar, Input, Button
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.message import Message

from ymusic_cli.api import TrackInfo


# ── Track List Widget ────────────────────────────────────────


class TrackSelected(Message):
    """Posted when a track is selected (Enter / click)."""

    def __init__(self, track: TrackInfo, index: int, tracks: list[TrackInfo]) -> None:
        super().__init__()
        self.track = track
        self.index = index
        self.tracks = tracks


class TrackItem(ListItem):
    """A single track row in the list."""

    DEFAULT_CSS = """
    TrackItem {
        height: 1;
        padding: 0 1;
    }
    TrackItem:hover {
        background: $primary 15%;
    }
    TrackItem.--highlight {
        background: $primary 30%;
    }
    TrackItem.playing {
        color: $success;
    }
    TrackItem .track-num {
        width: 4;
        color: $text-muted;
    }
    TrackItem .track-text {
        width: 1fr;
    }
    TrackItem .track-duration {
        width: 6;
        text-align: right;
        color: $text-muted;
    }
    TrackItem .track-row-inner {
        height: 1;
    }
    """

    def __init__(self, track: TrackInfo, index: int, is_playing: bool = False) -> None:
        super().__init__()
        self.track = track
        self.track_index = index
        self.is_playing = is_playing
        if is_playing:
            self.add_class("playing")

    def compose(self) -> ComposeResult:
        prefix = "▶" if self.is_playing else " "
        num = f"{self.track_index + 1:>3}"
        text = f"{self.track.title}  —  {self.track.artists}"
        with Horizontal(classes="track-row-inner"):
            yield Label(f"{prefix}{num}", classes="track-num")
            yield Label(text, classes="track-text")
            yield Label(self.track.duration_str, classes="track-duration")


class TrackList(Widget):
    """Scrollable list of tracks with selection support."""

    DEFAULT_CSS = """
    TrackList {
        height: 1fr;
    }
    TrackList #track-listview {
        height: 1fr;
    }
    """

    tracks: reactive[list[TrackInfo]] = reactive(list, always_update=True)
    playing_index: reactive[int] = reactive(-1)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._list_view: ListView | None = None

    def compose(self) -> ComposeResult:
        self._list_view = ListView(id="track-listview")
        yield self._list_view

    def watch_tracks(self, tracks: list[TrackInfo]) -> None:
        self._rebuild_list()

    def watch_playing_index(self, index: int) -> None:
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        if self._list_view is None:
            return
        self._list_view.clear()
        for i, track in enumerate(self.tracks):
            item = TrackItem(track, i, is_playing=(i == self.playing_index))
            self._list_view.append(item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, TrackItem):
            self.post_message(TrackSelected(item.track, item.track_index, list(self.tracks)))


# ── Player Bar Widget ────────────────────────────────────────


class PlayerBar(Widget):
    """Bottom bar showing now-playing info, controls, and progress."""

    DEFAULT_CSS = """
    PlayerBar {
        dock: bottom;
        height: 3;
        background: $panel;
        border-top: solid $primary-lighten-2;
    }
    PlayerBar #player-bar-inner {
        height: 3;
        padding: 0 1;
    }
    PlayerBar #track-info {
        width: 30;
        height: 3;
        padding: 0 1;
    }
    PlayerBar #track-title {
        text-style: bold;
        color: $text;
    }
    PlayerBar #track-artist {
        color: $text-muted;
    }
    PlayerBar #progress-section {
        width: 1fr;
        height: 3;
        align: center middle;
    }
    PlayerBar #controls-row {
        height: 1;
        align: center middle;
    }
    PlayerBar .control-btn {
        width: auto;
        padding: 0 1;
        color: $text;
    }
    PlayerBar .control-btn:hover {
        color: $primary;
    }
    PlayerBar .control-btn.active {
        color: $success;
    }
    PlayerBar #progress-bar-row {
        height: 1;
        align: center middle;
        padding: 0 1;
    }
    PlayerBar #time-current {
        width: 6;
        text-align: right;
        color: $text-muted;
    }
    PlayerBar #time-total {
        width: 6;
        text-align: left;
        color: $text-muted;
    }
    PlayerBar #progress {
        width: 1fr;
        padding: 0 1;
    }
    PlayerBar #volume-section {
        width: 14;
        height: 3;
        align: right middle;
        padding: 0 1;
    }
    PlayerBar #volume-label {
        color: $text-muted;
    }
    """

    track_title: reactive[str] = reactive("Nothing playing")
    track_artist: reactive[str] = reactive("")
    is_playing: reactive[bool] = reactive(False)
    position: reactive[float] = reactive(0.0)
    duration: reactive[float] = reactive(0.0)
    volume: reactive[int] = reactive(70)
    repeat_mode: reactive[str] = reactive("off")
    shuffle_on: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal(id="player-bar-inner"):
            # Left: track info
            with Vertical(id="track-info"):
                yield Label(self.track_title, id="track-title")
                yield Label(self.track_artist, id="track-artist")

            # Center: controls + progress
            with Vertical(id="progress-section"):
                with Horizontal(id="controls-row"):
                    yield Label("⇄", id="btn-shuffle", classes="control-btn")
                    yield Label("⏮", id="btn-prev", classes="control-btn")
                    yield Label("⏸", id="btn-play", classes="control-btn")
                    yield Label("⏭", id="btn-next", classes="control-btn")
                    yield Label("↻", id="btn-repeat", classes="control-btn")
                with Horizontal(id="progress-bar-row"):
                    yield Label("0:00", id="time-current")
                    yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="progress")
                    yield Label("0:00", id="time-total")

            # Right: volume
            with Vertical(id="volume-section"):
                yield Label(f"🔊 {self.volume}%", id="volume-label")

    def watch_track_title(self, value: str) -> None:
        try:
            self.query_one("#track-title", Label).update(value)
        except Exception:
            pass

    def watch_track_artist(self, value: str) -> None:
        try:
            self.query_one("#track-artist", Label).update(value)
        except Exception:
            pass

    def watch_is_playing(self, value: bool) -> None:
        try:
            btn = self.query_one("#btn-play", Label)
            btn.update("⏸" if value else "▶")
        except Exception:
            pass

    def watch_position(self, value: float) -> None:
        try:
            m, s = divmod(int(value), 60)
            self.query_one("#time-current", Label).update(f"{m}:{s:02d}")
            if self.duration > 0:
                pct = min(value / self.duration * 100, 100)
                self.query_one("#progress", ProgressBar).update(progress=pct)
        except Exception:
            pass

    def watch_duration(self, value: float) -> None:
        try:
            m, s = divmod(int(value), 60)
            self.query_one("#time-total", Label).update(f"{m}:{s:02d}")
        except Exception:
            pass

    def watch_volume(self, value: int) -> None:
        try:
            self.query_one("#volume-label", Label).update(f"🔊 {value}%")
        except Exception:
            pass

    def watch_repeat_mode(self, value: str) -> None:
        try:
            btn = self.query_one("#btn-repeat", Label)
            icons = {"off": "↻", "all": "↻ᴬ", "one": "↻¹"}
            btn.update(icons.get(value, "↻"))
            if value != "off":
                btn.add_class("active")
            else:
                btn.remove_class("active")
        except Exception:
            pass

    def watch_shuffle_on(self, value: bool) -> None:
        try:
            btn = self.query_one("#btn-shuffle", Label)
            if value:
                btn.add_class("active")
            else:
                btn.remove_class("active")
        except Exception:
            pass

    def update_from_player_state(self, state) -> None:
        """Bulk-update from a PlayerState object."""
        if state.current_track:
            self.track_title = state.current_track.title
            self.track_artist = state.current_track.artists
        self.is_playing = state.is_playing
        self.position = state.position
        self.duration = state.duration
        self.volume = state.volume
        self.repeat_mode = state.repeat
        self.shuffle_on = state.shuffle


# ── Sidebar Navigation ───────────────────────────────────────


class NavItemSelected(Message):
    """Posted when a navigation item is selected."""

    def __init__(self, item_id: str) -> None:
        super().__init__()
        self.item_id = item_id


class NavItem(ListItem):
    """Sidebar navigation item."""

    DEFAULT_CSS = """
    NavItem {
        height: 1;
        padding: 0 1;
    }
    NavItem:hover {
        background: $primary 20%;
    }
    NavItem.--highlight {
        background: $primary 40%;
        text-style: bold;
    }
    """

    def __init__(self, label: str, item_id: str, icon: str = "♪") -> None:
        super().__init__()
        self.label_text = label
        self.item_id = item_id
        self.icon = icon

    def compose(self) -> ComposeResult:
        yield Label(f" {self.icon}  {self.label_text}")


class Sidebar(Widget):
    """Left sidebar with navigation."""

    DEFAULT_CSS = """
    Sidebar {
        dock: left;
        width: 26;
        background: $panel;
        border-right: solid $primary-lighten-2;
    }
    Sidebar #sidebar-inner {
        padding: 1 0;
    }
    Sidebar .nav-label {
        padding: 0 2;
        height: 1;
        color: $text-muted;
        text-style: bold;
    }
    Sidebar .brand-label {
        padding: 0 2;
        height: 1;
        color: $primary;
        text-style: bold;
    }
    Sidebar #nav-list {
        height: auto;
        padding: 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar-inner"):
            yield Label(" 🎵 YMusic", classes="brand-label")
            yield Label("", classes="nav-label")  # spacer
            yield Label(" LIBRARY", classes="nav-label")
            lv = ListView(
                NavItem("My Wave", "wave", "🌊"),
                NavItem("Liked", "liked", "❤️"),
                NavItem("Playlists", "playlists", "📁"),
                NavItem("Search", "search", "🔍"),
                id="nav-list",
            )
            yield lv

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, NavItem):
            self.post_message(NavItemSelected(item.item_id))

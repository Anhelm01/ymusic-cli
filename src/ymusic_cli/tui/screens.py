"""Modal screens for YMusic CLI (playlist picker, help, etc.)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, ListView, ListItem, Static, Button
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding

from yandex_music import Playlist


class PlaylistItem(ListItem):
    """A single playlist entry in the picker."""

    DEFAULT_CSS = """
    PlaylistItem {
        height: 1;
        padding: 0 1;
    }
    PlaylistItem:hover {
        background: $primary 20%;
    }
    """

    def __init__(self, playlist: Playlist) -> None:
        super().__init__()
        self.playlist = playlist

    def compose(self) -> ComposeResult:
        title = self.playlist.title or "Untitled"
        count = self.playlist.track_count or 0
        yield Label(f"📁 {title}  ({count} tracks)")


class PlaylistPickerScreen(ModalScreen[Playlist | None]):
    """Modal to pick a playlist from user's library."""

    DEFAULT_CSS = """
    PlaylistPickerScreen {
        align: center middle;
    }
    PlaylistPickerScreen #picker-box {
        width: 50;
        height: 20;
        border: solid $primary;
        background: $panel;
        padding: 1 2;
    }
    PlaylistPickerScreen #picker-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    PlaylistPickerScreen #picker-list {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, playlists: list[Playlist]) -> None:
        super().__init__()
        self.playlists = playlists

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Label("Select a playlist:", id="picker-title")
            lv = ListView(id="picker-list")
            for pl in self.playlists:
                lv.append(PlaylistItem(pl))  # type: ignore
            yield lv

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, PlaylistItem):
            self.dismiss(item.playlist)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    """Help overlay showing keybindings."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen #help-box {
        width: 60;
        height: auto;
        max-height: 30;
        border: solid $primary;
        background: $panel;
        padding: 2 3;
    }
    HelpScreen #help-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        text-align: center;
    }
    HelpScreen .help-section {
        margin-bottom: 1;
        text-style: bold;
        color: $text;
    }
    HelpScreen .help-line {
        color: $text-muted;
    }
    HelpScreen .key {
        color: $success;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Label("🎵 YMusic CLI — Help", id="help-title")
            yield Label("PLAYBACK", classes="help-section")
            yield Label("  Space     Play / Pause", classes="help-line")
            yield Label("  n         Next track", classes="help-line")
            yield Label("  p         Previous track", classes="help-line")
            yield Label("  ← / →     Seek ±5 seconds", classes="help-line")
            yield Label("  = / -     Volume up / down", classes="help-line")
            yield Label("  r         Cycle repeat (off/all/one)", classes="help-line")
            yield Label("  s         Toggle shuffle", classes="help-line")
            yield Label("")
            yield Label("LIBRARY", classes="help-section")
            yield Label("  l         Like current track", classes="help-line")
            yield Label("  d         Dislike (don't recommend)", classes="help-line")
            yield Label("  /         Focus search", classes="help-line")
            yield Label("  1-4       Switch sections", classes="help-line")
            yield Label("")
            yield Label("GENERAL", classes="help-section")
            yield Label("  ?         This help", classes="help-line")
            yield Label("  q         Quit", classes="help-line")
            yield Label("")
            yield Button("Close", variant="primary", id="help-close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

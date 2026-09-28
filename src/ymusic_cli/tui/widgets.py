"""Cmus-style Linux terminal widgets for YMusic CLI."""

from __future__ import annotations

from typing import Optional
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static, Input, Label
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual.screen import ModalScreen
from rich.text import Text

from ymusic_cli.api import TrackInfo
from ymusic_cli.player import PlayerState


class CmusTable(DataTable):
    """Full-width terminal track table with Vim navigation."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("ctrl+d", "page_down", "Page Down", show=False),
        Binding("ctrl+u", "page_up", "Page Up", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", id="track-table", **kwargs)


class TopBar(Static):
    """Top status header showing numbered views and user status."""

    def __init__(self, **kwargs) -> None:
        super().__init__(id="top-bar", **kwargs)
        self.active_view = 2
        self.liked_count = 0
        self.view_detail = ""
        self.username = "User"
        self.has_plus = True

    def update_header(
        self,
        active_view: int,
        username: str,
        has_plus: bool,
        liked_count: int = 0,
        detail: str = "",
    ) -> None:
        self.active_view = active_view
        self.username = username
        self.has_plus = has_plus
        self.liked_count = liked_count
        self.view_detail = detail
        self.render_bar()

    def render_bar(self) -> None:
        t = Text()

        # View 1: Wave
        v1_style = "bold #00ff7f reverse" if self.active_view == 1 else "bold #00bfff"
        t.append(" [1: Wave] ", style=v1_style)
        t.append(" ")

        # View 2: Liked
        v2_label = f" [2: Liked ({self.liked_count})] " if self.liked_count else " [2: Liked] "
        v2_style = "bold #00ff7f reverse" if self.active_view == 2 else "bold #00bfff"
        t.append(v2_label, style=v2_style)
        t.append(" ")

        # View 3: Playlists
        v3_label = f" [3: Playlists > {self.view_detail}] " if (self.active_view == 3 and self.view_detail) else " [3: Playlists] "
        v3_style = "bold #00ff7f reverse" if self.active_view == 3 else "bold #00bfff"
        t.append(v3_label, style=v3_style)
        t.append(" ")

        # View 4: Search
        v4_label = f" [4: Search: \"{self.view_detail}\"] " if (self.active_view == 4 and self.view_detail) else " [4: Search] "
        v4_style = "bold #00ff7f reverse" if self.active_view == 4 else "bold #00bfff"
        t.append(v4_label, style=v4_style)

        # Right side: User & Plus badge
        plus_text = " [Plus]" if self.has_plus else " [No Plus]"
        plus_style = "bold #00ff7f" if self.has_plus else "bold #ff5555"
        user_info = f"│ {self.username}"

        t.append(f" {user_info}", style="dim #888888")
        t.append(plus_text, style=plus_style)
        t.append(" │ ? Help", style="dim #888888")

        self.update(t)


class CmusPlayerBar(Widget):
    """Cmus-style 3-line bottom player bar with status, progress, and hints."""

    def compose(self) -> ComposeResult:
        with Vertical(id="player-bar"):
            yield Static("[STOPPED] Nothing playing", id="status-line")
            yield Static("────────────────────────────────────────────────────────────────────────────", id="progress-line")
            yield Static("[j/k] Nav  [Enter] Play  [c/Space] Pause  [b/z] Next/Prev  [+/-] Vol  [/] Search  [1-4] Views  [q] Quit", id="cmd-line")

    def update_state(self, state: PlayerState) -> None:
        status_line = self.query_one("#status-line", Static)
        progress_line = self.query_one("#progress-line", Static)

        # Status text
        st = Text()
        if not state.current_track:
            st.append("[STOPPED] ", style="bold #ff5555")
            st.append("Nothing playing", style="#888888")
        else:
            if state.is_playing:
                st.append("[PLAYING] ", style="bold #00ff7f")
            else:
                st.append("[PAUSED]  ", style="bold #ffaa00")

            # Time: mm:ss / mm:ss
            st.append(f"{state.position_str} / {state.duration_str} ", style="bold #ffffff")
            st.append("— ", style="#888888")
            st.append(f"{state.current_track.artists} - {state.current_track.title} ", style="bold #00e5ff")
            if state.current_track.album:
                st.append(f"[{state.current_track.album}] ", style="dim #aaaaaa")

        # Controls info
        st.append(f" [vol: {state.volume}%]", style="#888888")
        st.append(f" [rep: {state.repeat}]", style="#888888")
        if state.shuffle:
            st.append(" [shuf: on]", style="#00ff7f")
        else:
            st.append(" [shuf: off]", style="#888888")

        status_line.update(st)

        # Progress bar line
        width = max(20, self.size.width - 2) if self.size.width else 78
        frac = state.progress
        fill_width = int(frac * (width - 1))
        fill_width = max(0, min(width - 1, fill_width))
        empty_width = (width - 1) - fill_width

        pt = Text()
        pt.append("━" * fill_width, style="bold #00ff7f")
        pt.append("●", style="bold #ffffff")
        pt.append("─" * empty_width, style="#333333")
        progress_line.update(pt)

    def set_message(self, message: str, style: str = "bold #ffaa00") -> None:
        cmd_line = self.query_one("#cmd-line", Static)
        t = Text()
        t.append(f":: {message}", style=style)
        cmd_line.update(t)

    def restore_hints(self) -> None:
        cmd_line = self.query_one("#cmd-line", Static)
        cmd_line.update("[j/k] Nav  [Enter] Play  [c/Space] Pause  [b/z] Next/Prev  [+/-] Vol  [/] Search  [1-4] Views  [q] Quit")


class HelpScreen(ModalScreen[None]):
    """Clean ASCII help screen overlay."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("q", "dismiss_modal", "Close"),
        Binding("question_mark", "dismiss_modal", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            with Vertical(id="help-box"):
                yield Label("── YMusic CLI Cheatsheet (Cmus / Vim Keys) ──", id="help-title")

                yield Label("NAVIGATION (Vim)", classes="help-category")
                yield Label("  j / Down       Move down 1 track", classes="help-entry")
                yield Label("  k / Up         Move up 1 track", classes="help-entry")
                yield Label("  g / Home       Jump to top of list", classes="help-entry")
                yield Label("  G / End        Jump to bottom of list", classes="help-entry")
                yield Label("  Ctrl+D / U     Half page down / up", classes="help-entry")
                yield Label("  Enter          Play selected track / Open playlist", classes="help-entry")
                yield Label("  Backspace/Esc  Back from playlist view", classes="help-entry")

                yield Label("PLAYBACK (cmus standard)", classes="help-category")
                yield Label("  c / Space      Toggle pause / play", classes="help-entry")
                yield Label("  b / n          Next track", classes="help-entry")
                yield Label("  z / p          Previous track", classes="help-entry")
                yield Label("  x              Restart track from beginning", classes="help-entry")
                yield Label("  v              Stop playback", classes="help-entry")
                yield Label("  + / =          Volume up (+5%)", classes="help-entry")
                yield Label("  - / _          Volume down (-5%)", classes="help-entry")
                yield Label("  h / Left       Seek -5 seconds", classes="help-entry")
                yield Label("  l / Right      Seek +5 seconds", classes="help-entry")
                yield Label("  H / L          Seek -30s / +30s", classes="help-entry")
                yield Label("  r              Cycle repeat (off -> all -> one)", classes="help-entry")
                yield Label("  s              Toggle shuffle", classes="help-entry")

                yield Label("VIEWS & ACTIONS", classes="help-category")
                yield Label("  1              Switch to My Wave (Моя Волна)", classes="help-entry")
                yield Label("  2              Switch to Liked Tracks (Любимые)", classes="help-entry")
                yield Label("  3              Switch to Playlists (Плейлисты)", classes="help-entry")
                yield Label("  4              Switch to Search Results", classes="help-entry")
                yield Label("  a              Like current track (❤️)", classes="help-entry")
                yield Label("  d              Dislike current track (👎 / do not recommend)", classes="help-entry")
                yield Label("  u              Reload current view from Yandex", classes="help-entry")
                yield Label("  /              Inline search prompt", classes="help-entry")
                yield Label("  :              Inline command (:q, :wave, :vol, :help)", classes="help-entry")
                yield Label("  ?              Toggle this help screen", classes="help-entry")
                yield Label("  q              Quit YMusic CLI", classes="help-entry")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

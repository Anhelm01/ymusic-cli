"""Main Cmus-style TUI application for YMusic CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, List, Optional

from textual.app import App, ComposeResult
from textual.widgets import Static, Input, DataTable
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.binding import Binding
from rich.text import Text

from ymusic_cli.config import Config
from ymusic_cli.api import YMusicAPI, TrackInfo
from ymusic_cli.player import Player
from ymusic_cli.tui.widgets import (
    CmusTable,
    TopBar,
    CmusPlayerBar,
    HelpScreen,
)


VIEW_WAVE = 1
VIEW_LIKED = 2
VIEW_PLAYLISTS = 3
VIEW_SEARCH = 4


class MainScreen(Screen):
    """Cmus-style full-terminal player screen."""

    BINDINGS = [
        # Navigation
        Binding("1", "switch_view_wave", "Wave", show=False),
        Binding("2", "switch_view_liked", "Liked", show=False),
        Binding("3", "switch_view_playlists", "Playlists", show=False),
        Binding("4", "switch_view_search", "Search", show=False),
        # Playback (cmus keys)
        Binding("c", "toggle_pause", "Pause", show=False),
        Binding("space", "toggle_pause", "Pause", show=False),
        Binding("b", "next_track", "Next", show=False),
        Binding("n", "next_track", "Next", show=False),
        Binding("z", "prev_track", "Prev", show=False),
        Binding("p", "prev_track", "Prev", show=False),
        Binding("x", "restart_track", "Restart", show=False),
        Binding("v", "stop_track", "Stop", show=False),
        Binding("plus", "volume_up", "Vol+", show=False),
        Binding("equals", "volume_up", "Vol+", show=False),
        Binding("minus", "volume_down", "Vol-", show=False),
        Binding("underscore", "volume_down", "Vol-", show=False),
        Binding("h", "seek_backward", "Seek-5", show=False),
        Binding("left", "seek_backward", "Seek-5", show=False),
        Binding("l", "seek_forward", "Seek+5", show=False),
        Binding("right", "seek_forward", "Seek+5", show=False),
        Binding("H", "seek_back_30", "Seek-30", show=False),
        Binding("L", "seek_fwd_30", "Seek+30", show=False),
        Binding("r", "toggle_repeat", "Repeat", show=False),
        Binding("s", "toggle_shuffle", "Shuffle", show=False),
        # Actions
        Binding("a", "like_current", "Like", show=False),
        Binding("d", "dislike_current", "Dislike", show=False),
        Binding("u", "reload_view", "Reload", show=False),
        Binding("backspace", "back_or_escape", "Back", show=False),
        Binding("escape", "back_or_escape", "Back", show=False),
        # Prompts
        Binding("slash", "open_search_prompt", "Search", show=False),
        Binding("colon", "open_command_prompt", "Command", show=False),
        Binding("question_mark", "show_help", "Help", show=False),
        Binding("q", "quit_app", "Quit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.active_view = VIEW_LIKED
        self.current_tracks: list[TrackInfo] = []
        self.cached_playlists: list[Any] = []
        self.in_playlist_detail: bool = False
        self.current_playlist_title: str = ""
        self.search_query: str = ""
        self.liked_tracks_cache: list[TrackInfo] = []
        self._prompt_mode: str = ""  # "/" or ":"

    def compose(self) -> ComposeResult:
        yield TopBar()
        yield CmusTable()
        yield CmusPlayerBar()
        with Horizontal(id="prompt-container"):
            yield Static("/", id="prompt-label")
            yield Input(id="prompt-input")

    def _get_app(self) -> YMusicApp:
        return self.app  # type: ignore

    def on_mount(self) -> None:
        app = self._get_app()
        # Initialize top bar
        top_bar = self.query_one(TopBar)
        top_bar.update_header(
            active_view=self.active_view,
            username=app.api.username,
            has_plus=app.api.has_plus,
        )

        # Focus table for keyboard navigation
        table = self.query_one(CmusTable)
        table.focus()

        # Load initial liked tracks
        self.action_switch_view_liked()

        # Position/status update interval
        self.set_interval(0.5, self._on_timer_tick)

    # ── Table Management ─────────────────────────────────────

    def _setup_track_columns(self) -> None:
        table = self.query_one(CmusTable)
        table.clear(columns=True)
        table.add_columns("  #  ", "Title", "Artist", "Album", "Time")

    def _populate_tracks(self, tracks: list[TrackInfo]) -> None:
        self.current_tracks = list(tracks)
        table = self.query_one(CmusTable)
        self._setup_track_columns()

        app = self._get_app()
        playing_id = str(app.player.state.current_track.id) if (app.player and app.player.state.current_track) else None

        for i, t in enumerate(tracks):
            is_playing = playing_id is not None and str(t.id) == playing_id
            prefix = "▶" if is_playing else " "
            num_label = f"{prefix} {i+1:>3}"

            title_text = Text(t.title, style="bold #00ff7f" if is_playing else "default")
            artist_text = Text(t.artists, style="bold #00e5ff" if is_playing else "#cccccc")

            table.add_row(
                num_label,
                title_text,
                artist_text,
                t.album,
                t.duration_str,
                key=f"track_{i}",
            )

        if tracks and table.row_count > 0:
            table.move_cursor(row=0)

    def _update_playing_indicator(self) -> None:
        app = self._get_app()
        if not app.player:
            return
        table = self.query_one(CmusTable)
        if not self.current_tracks or table.row_count != len(self.current_tracks):
            return

        current = app.player.state.current_track
        playing_id = str(current.id) if current else None

        col_keys = list(table.columns.keys())
        if not col_keys:
            return
        num_col_key = col_keys[0]

        for i, t in enumerate(self.current_tracks):
            is_playing = playing_id is not None and str(t.id) == playing_id
            prefix = "▶" if is_playing else " "
            new_val = f"{prefix} {i+1:>3}"
            row_key = f"track_{i}"
            try:
                if table.get_cell(row_key, num_col_key) != new_val:
                    table.update_cell(row_key, num_col_key, new_val)
            except Exception:
                pass

    # ── View Switching ───────────────────────────────────────

    def action_switch_view_wave(self) -> None:
        self.active_view = VIEW_WAVE
        self.in_playlist_detail = False
        app = self._get_app()
        top_bar = self.query_one(TopBar)
        top_bar.update_header(
            active_view=VIEW_WAVE,
            username=app.api.username,
            has_plus=app.api.has_plus,
            liked_count=len(self.liked_tracks_cache),
        )
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.set_message("Loading My Wave tracks...")
        self.run_worker(self._load_wave_worker)

    async def _load_wave_worker(self) -> None:
        app = self._get_app()
        tracks = await asyncio.to_thread(app.api.start_wave)
        self._populate_tracks(tracks)
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.restore_hints()

    def action_switch_view_liked(self) -> None:
        self.active_view = VIEW_LIKED
        self.in_playlist_detail = False
        app = self._get_app()
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.set_message("Loading Liked tracks...")
        self.run_worker(self._load_liked_worker)

    async def _load_liked_worker(self) -> None:
        app = self._get_app()
        tracks = await asyncio.to_thread(app.api.get_liked_tracks, limit=100)
        self.liked_tracks_cache = tracks
        self._populate_tracks(tracks)

        top_bar = self.query_one(TopBar)
        top_bar.update_header(
            active_view=VIEW_LIKED,
            username=app.api.username,
            has_plus=app.api.has_plus,
            liked_count=len(tracks),
        )
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.restore_hints()

    def action_switch_view_playlists(self) -> None:
        self.active_view = VIEW_PLAYLISTS
        self.in_playlist_detail = False
        app = self._get_app()
        top_bar = self.query_one(TopBar)
        top_bar.update_header(
            active_view=VIEW_PLAYLISTS,
            username=app.api.username,
            has_plus=app.api.has_plus,
            liked_count=len(self.liked_tracks_cache),
        )
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.set_message("Loading Playlists...")
        self.run_worker(self._load_playlists_worker)

    async def _load_playlists_worker(self) -> None:
        app = self._get_app()
        playlists = await asyncio.to_thread(app.api.get_playlists)
        self.cached_playlists = playlists

        table = self.query_one(CmusTable)
        table.clear(columns=True)
        table.add_columns("  #  ", "Playlist Title", "Tracks", "Owner")

        for i, pl in enumerate(playlists):
            title = pl.title or "Untitled"
            count = f"{pl.track_count or 0} tracks"
            owner = getattr(pl.owner, "name", "User") if hasattr(pl, "owner") and pl.owner else "User"
            table.add_row(f"  {i+1:>3}", title, count, str(owner), key=f"pl_{i}")

        player_bar = self.query_one(CmusPlayerBar)
        player_bar.restore_hints()

    async def _load_playlist_tracks_worker(self, playlist: Any) -> None:
        app = self._get_app()
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.set_message(f"Loading '{playlist.title}' tracks...")
        tracks = await asyncio.to_thread(app.api.get_playlist_tracks, playlist, limit=100)
        self._populate_tracks(tracks)

        self.in_playlist_detail = True
        self.current_playlist_title = playlist.title or "Playlist"
        top_bar = self.query_one(TopBar)
        top_bar.update_header(
            active_view=VIEW_PLAYLISTS,
            username=app.api.username,
            has_plus=app.api.has_plus,
            liked_count=len(self.liked_tracks_cache),
            detail=f"{self.current_playlist_title} ({len(tracks)})",
        )
        player_bar.restore_hints()

    def action_switch_view_search(self) -> None:
        self.active_view = VIEW_SEARCH
        self.in_playlist_detail = False
        app = self._get_app()
        top_bar = self.query_one(TopBar)
        top_bar.update_header(
            active_view=VIEW_SEARCH,
            username=app.api.username,
            has_plus=app.api.has_plus,
            liked_count=len(self.liked_tracks_cache),
            detail=self.search_query,
        )
        if not self.search_query:
            self.action_open_search_prompt()

    # ── Table Selection & Playback ───────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = event.cursor_row
        if self.active_view == VIEW_PLAYLISTS and not self.in_playlist_detail:
            # Selected a playlist from the list
            if 0 <= idx < len(self.cached_playlists):
                pl = self.cached_playlists[idx]
                self.run_worker(self._load_playlist_tracks_worker(pl))
            return

        # Selected a track to play
        if 0 <= idx < len(self.current_tracks):
            self.run_worker(self._play_track_index(idx))

    async def _play_track_index(self, index: int) -> None:
        app = self._get_app()
        if not app.player or not self.current_tracks:
            return
        track = self.current_tracks[index]
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.set_message(f"Connecting stream: {track.title}...")

        # Wave feedback if in wave mode
        if self.active_view == VIEW_WAVE and app.api.radio_session:
            await asyncio.to_thread(app.api.radio_session.feedback_track_started, track)

        await asyncio.to_thread(app.player.set_queue, self.current_tracks, index)
        self._update_playing_indicator()
        player_bar.restore_hints()

    # ── Timer & Progress ─────────────────────────────────────

    def _on_timer_tick(self) -> None:
        app = self._get_app()
        if not app.player:
            return
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.update_state(app.player.state)
        self._update_playing_indicator()

    # ── Playback Controls (cmus bindings) ────────────────────

    def action_toggle_pause(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.toggle_pause()
            self._on_timer_tick()

    def action_next_track(self) -> None:
        self.run_worker(self._do_next_track)

    async def _do_next_track(self) -> None:
        app = self._get_app()
        if not app.player:
            return
        if self.active_view == VIEW_WAVE and app.api.radio_session and app.player.state.current_track:
            await asyncio.to_thread(
                app.api.radio_session.feedback_skip,
                app.player.state.current_track,
                app.player.state.position,
            )
        await asyncio.to_thread(app.player.next_track)
        self._update_playing_indicator()

        # If in wave mode, check if we need more tracks
        if self.active_view == VIEW_WAVE and app.api.radio_session:
            queue = app.player.state.queue
            idx = app.player.state.queue_index
            if idx >= len(queue) - 2:
                more = await asyncio.to_thread(app.api.get_more_wave_tracks)
                if more:
                    app.player.state.queue.extend(more)
                    self.current_tracks = list(app.player.state.queue)
                    self._populate_tracks(self.current_tracks)

    def action_prev_track(self) -> None:
        self.run_worker(self._do_prev_track)

    async def _do_prev_track(self) -> None:
        app = self._get_app()
        if app.player:
            await asyncio.to_thread(app.player.prev_track)
            self._update_playing_indicator()

    def action_restart_track(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.seek_absolute(0)

    def action_stop_track(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.stop()
            self._update_playing_indicator()

    def action_volume_up(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.volume_up(5)
            self._on_timer_tick()

    def action_volume_down(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.volume_down(5)
            self._on_timer_tick()

    def action_seek_forward(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.seek(5)

    def action_seek_backward(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.seek(-5)

    def action_seek_fwd_30(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.seek(30)

    def action_seek_back_30(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.seek(-30)

    def action_toggle_repeat(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.toggle_repeat()
            self._on_timer_tick()

    def action_toggle_shuffle(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.toggle_shuffle()
            self._on_timer_tick()

    def action_like_current(self) -> None:
        self.run_worker(self._do_like_current)

    async def _do_like_current(self) -> None:
        app = self._get_app()
        player_bar = self.query_one(CmusPlayerBar)
        if app.player and app.player.state.current_track:
            track = app.player.state.current_track
            ok = await asyncio.to_thread(app.api.like_track, track)
            if ok:
                player_bar.set_message(f"❤️ Liked: {track.title}", style="bold #00ff7f")
            else:
                player_bar.set_message(f"Failed to like: {track.title}", style="bold #ff5555")

    def action_dislike_current(self) -> None:
        self.run_worker(self._do_dislike_current)

    async def _do_dislike_current(self) -> None:
        app = self._get_app()
        player_bar = self.query_one(CmusPlayerBar)
        if app.player and app.player.state.current_track:
            track = app.player.state.current_track
            ok = await asyncio.to_thread(app.api.dislike_track, track)
            if ok:
                player_bar.set_message(f"👎 Disliked (won't recommend): {track.title}", style="bold #ffaa00")
                if self.active_view == VIEW_WAVE:
                    await self._do_next_track()
            else:
                player_bar.set_message(f"Failed to dislike: {track.title}", style="bold #ff5555")

    def action_reload_view(self) -> None:
        if self.active_view == VIEW_WAVE:
            self.action_switch_view_wave()
        elif self.active_view == VIEW_LIKED:
            self.action_switch_view_liked()
        elif self.active_view == VIEW_PLAYLISTS:
            self.action_switch_view_playlists()
        elif self.active_view == VIEW_SEARCH:
            if self.search_query:
                self.run_worker(self._do_search(self.search_query))

    def action_back_or_escape(self) -> None:
        # If in prompt input, close it
        prompt_box = self.query_one("#prompt-container")
        if prompt_box.display:
            prompt_box.display = False
            self.query_one(CmusTable).focus()
            return
        # If in playlist detail, go back to playlist list
        if self.active_view == VIEW_PLAYLISTS and self.in_playlist_detail:
            self.action_switch_view_playlists()

    # ── Search & Command Prompts ─────────────────────────────

    def action_open_search_prompt(self) -> None:
        self._prompt_mode = "/"
        prompt_box = self.query_one("#prompt-container")
        prompt_label = self.query_one("#prompt-label", Static)
        prompt_input = self.query_one("#prompt-input", Input)

        prompt_label.update("/")
        prompt_input.value = ""
        prompt_box.display = True
        prompt_input.focus()

    def action_open_command_prompt(self) -> None:
        self._prompt_mode = ":"
        prompt_box = self.query_one("#prompt-container")
        prompt_label = self.query_one("#prompt-label", Static)
        prompt_input = self.query_one("#prompt-input", Input)

        prompt_label.update(":")
        prompt_input.value = ""
        prompt_box.display = True
        prompt_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt_box = self.query_one("#prompt-container")
        prompt_box.display = False
        val = event.value.strip()
        self.query_one(CmusTable).focus()

        if self._prompt_mode == "/":
            if val:
                self.search_query = val
                self.active_view = VIEW_SEARCH
                app = self._get_app()
                top_bar = self.query_one(TopBar)
                top_bar.update_header(
                    active_view=VIEW_SEARCH,
                    username=app.api.username,
                    has_plus=app.api.has_plus,
                    liked_count=len(self.liked_tracks_cache),
                    detail=val,
                )
                self.run_worker(self._do_search(val))
        elif self._prompt_mode == ":":
            self._handle_command(val)

    def _handle_command(self, cmd: str) -> None:
        cmd = cmd.strip()
        player_bar = self.query_one(CmusPlayerBar)

        if cmd in ("q", "quit", "exit"):
            self.action_quit_app()
        elif cmd in ("1", "wave"):
            self.action_switch_view_wave()
        elif cmd in ("2", "liked"):
            self.action_switch_view_liked()
        elif cmd in ("3", "playlists", "pl"):
            self.action_switch_view_playlists()
        elif cmd.startswith("search ") or cmd.startswith("s "):
            q = cmd.split(" ", 1)[1].strip()
            if q:
                self.search_query = q
                self.action_switch_view_search()
                self.run_worker(self._do_search(q))
        elif cmd.startswith("vol "):
            try:
                vol = int(cmd.split(" ", 1)[1].strip())
                app = self._get_app()
                if app.player:
                    app.player.set_volume(vol)
                    self._on_timer_tick()
            except ValueError:
                player_bar.set_message("Invalid volume. Use: :vol <0-100>", style="bold #ff5555")
        elif cmd.startswith("seek "):
            try:
                sec = float(cmd.split(" ", 1)[1].strip())
                app = self._get_app()
                if app.player:
                    app.player.seek(sec)
            except ValueError:
                player_bar.set_message("Invalid seek seconds. Use: :seek <+/-seconds>", style="bold #ff5555")
        elif cmd in ("help", "h", "?"):
            self.action_show_help()
        else:
            player_bar.set_message(f"Unknown command: :{cmd} (type :help)", style="bold #ffaa00")

    async def _do_search(self, query: str) -> None:
        app = self._get_app()
        player_bar = self.query_one(CmusPlayerBar)
        player_bar.set_message(f"Searching: '{query}'...")
        tracks = await asyncio.to_thread(app.api.search, query, limit=50)
        self._populate_tracks(tracks)
        player_bar.set_message(f"Found {len(tracks)} results for '{query}'")

    def action_show_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_quit_app(self) -> None:
        self._get_app().exit()


# ── Minimal Terminal Login Screen ────────────────────────────


class TerminalLoginScreen(Screen):
    """Terminal-native minimal login prompt."""

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            with Vertical(id="help-box"):
                yield Label("── YMusic CLI Authentication ──", id="help-title")
                yield Label(
                    "You need a Yandex Music OAuth token to access your account.\n"
                    "Get your token at:\n"
                    "https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d\n",
                    classes="help-entry",
                )
                yield Label("Paste OAuth token below and press Enter:", classes="help-category")
                yield Input(placeholder="y0_AgAAAA...", id="login-token-input")
                yield Label("", id="login-msg")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        token = event.value.strip()
        msg = self.query_one("#login-msg", Label)
        if not token:
            msg.update("Token cannot be empty.")
            return

        msg.update("Authenticating with Yandex...")
        self.run_worker(self._do_auth(token))

    async def _do_auth(self, token: str) -> None:
        app: YMusicApp = self.app  # type: ignore
        msg = self.query_one("#login-msg", Label)
        ok = await asyncio.to_thread(app.api.login, token)
        if ok:
            app._init_player()
            app.push_screen(MainScreen())
        else:
            msg.update("❌ Authentication failed. Please check the token.")


# ── Main Application ─────────────────────────────────────────


class YMusicApp(App):
    """YMusic CLI — True Linux Cmus-style TUI."""

    TITLE = "ymusic"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(self, config: Config | None = None) -> None:
        super().__init__()
        self.config = config or Config.load()
        self.api = YMusicAPI(self.config)
        self.player: Player | None = None

    def _init_player(self) -> None:
        self.player = Player(self.api, volume=self.config.volume)
        self.player.on_end(self._on_track_end)

    def _on_track_end(self) -> None:
        if self.player:
            asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(self.player.next_track),
                self._loop,
            )

    def on_mount(self) -> None:
        if self.config.is_authenticated and self.api.login():
            self._init_player()
            self.push_screen(MainScreen())
        else:
            self.push_screen(TerminalLoginScreen())

    def on_unmount(self) -> None:
        if self.player:
            self.config.volume = self.player.state.volume
            self.config.save()
            self.player.shutdown()

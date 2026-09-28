"""Main Textual application for YMusic CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Label, Input, Button, Footer, Header
from textual.containers import Horizontal, Vertical, Container
from textual.screen import Screen
from textual.binding import Binding

from ymusic_cli.config import Config
from ymusic_cli.api import YMusicAPI, TrackInfo
from ymusic_cli.player import Player
from ymusic_cli.tui.widgets import (
    TrackList,
    TrackSelected,
    PlayerBar,
    Sidebar,
    NavItemSelected,
)
from ymusic_cli.tui.screens import PlaylistPickerScreen, HelpScreen


STYLES_PATH = Path(__file__).parent / "styles.tcss"


# ── Login Screen ─────────────────────────────────────────────


class LoginScreen(Screen):
    """Initial screen for token authentication."""

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="login-container"):
            with Vertical(id="login-box"):
                yield Label("🎵 YMusic CLI", id="login-title")
                yield Label("")
                yield Label(
                    "Method 1: Paste your OAuth token below.",
                    id="login-help",
                )
                yield Label(
                    "Get token at:\n"
                    "https://oauth.yandex.ru/authorize?response_type=token"
                    "&client_id=23cabbbdc6cd418abb4b39c32c41195d",
                )
                yield Label("")
                yield Input(
                    placeholder="Paste your OAuth token here...",
                    password=True,
                    id="token-input",
                )
                yield Button("Login with token", variant="primary", id="login-btn")
                yield Label("")
                yield Button(
                    "Login via device code (browser)", variant="default", id="device-auth-btn"
                )
                yield Label("", id="login-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login-btn":
            self._do_token_login()
        elif event.button.id == "device-auth-btn":
            self._do_device_auth()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "token-input":
            self._do_token_login()

    def _do_token_login(self) -> None:
        token_input = self.query_one("#token-input", Input)
        status = self.query_one("#login-status", Label)
        token = token_input.value.strip()
        if not token:
            status.update("⚠ Please enter a token")
            return
        status.update("⏳ Logging in...")
        self.run_worker(self._async_token_login(token))

    async def _async_token_login(self, token: str) -> None:
        status = self.query_one("#login-status", Label)
        app: YMusicApp = self.app  # type: ignore
        success = await asyncio.to_thread(app.api.login, token)
        if success:
            app._init_player()
            app.push_screen(MainScreen())
        else:
            status.update("❌ Login failed. Check your token and try again.")

    def _do_device_auth(self) -> None:
        status = self.query_one("#login-status", Label)
        status.update("⏳ Starting device auth...")
        self.run_worker(self._async_device_auth)

    async def _async_device_auth(self) -> None:
        status = self.query_one("#login-status", Label)
        app: YMusicApp = self.app  # type: ignore

        def on_code(code):
            url = getattr(code, "verification_url", "https://ya.ru/device")
            user_code = getattr(code, "user_code", "???")
            self.app.call_from_thread(
                status.update,
                f"Go to: {url}\nEnter code: {user_code}",
            )

        token = await asyncio.to_thread(app.api.device_auth, on_code_callback=on_code)
        if token:
            app._init_player()
            app.push_screen(MainScreen())
        else:
            status.update("❌ Device auth failed or timed out.")


# ── Main Player Screen ───────────────────────────────────────


class MainScreen(Screen):
    """Main TUI screen with sidebar, track list, and player bar."""

    BINDINGS = [
        Binding("space", "toggle_pause", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Prev"),
        Binding("equals", "volume_up", "Vol+"),
        Binding("minus", "volume_down", "Vol-"),
        Binding("r", "toggle_repeat", "Repeat"),
        Binding("s", "toggle_shuffle", "Shuffle"),
        Binding("l", "like_track", "Like"),
        Binding("d", "dislike_track", "Dislike"),
        Binding("right", "seek_forward", "+5s", show=False),
        Binding("left", "seek_backward", "-5s", show=False),
        Binding("slash", "focus_search", "/Search", show=False),
        Binding("1", "nav_wave", "Wave", show=False),
        Binding("2", "nav_liked", "Liked", show=False),
        Binding("3", "nav_playlists", "Playlists", show=False),
        Binding("4", "nav_search", "Search", show=False),
        Binding("question_mark", "show_help", "Help"),
        Binding("q", "quit_app", "Quit"),
    ]

    current_section: str = "liked"
    _is_wave_mode: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield Sidebar()
            with Vertical(id="main-content"):
                yield Label("❤️  Liked Tracks", id="section-title")
                with Container(id="track-list-container"):
                    yield TrackList(id="track-list")
                with Container(id="search-container"):
                    yield Input(placeholder="Search tracks, artists, albums...", id="search-input")
        yield PlayerBar(id="player-bar-widget")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-container").display = False
        app = self._get_app()
        self.app.title = f"YMusic CLI — {app.api.username}"
        if not app.api.has_plus:
            self.notify(
                "⚠️ No Yandex Plus subscription detected. "
                "Playback may be limited to 30-second previews.",
                timeout=8,
                severity="warning",
            )
        self._load_liked()
        self.set_interval(0.5, self._update_player_bar)

    def _get_app(self) -> YMusicApp:
        return self.app  # type: ignore

    def _update_player_bar(self) -> None:
        """Periodically update the player bar from player state."""
        app = self._get_app()
        if not app.player:
            return
        bar = self.query_one("#player-bar-widget", PlayerBar)
        bar.update_from_player_state(app.player.state)
        # Update playing indicator in track list
        track_list = self.query_one("#track-list", TrackList)
        if app.player.state.current_track:
            target_id = str(app.player.state.current_track.id)
            found_idx = -1
            for i, t in enumerate(track_list.tracks):
                if str(t.id) == target_id:
                    found_idx = i
                    break
            track_list.playing_index = found_idx

    # ── Navigation ──

    def on_nav_item_selected(self, event: NavItemSelected) -> None:
        self.current_section = event.item_id
        self._is_wave_mode = event.item_id == "wave"
        sections = {
            "wave": ("🌊  My Wave", self._load_wave),
            "liked": ("❤️  Liked Tracks", self._load_liked),
            "playlists": ("📁  Playlists", self._load_playlists),
            "search": ("🔍  Search", self._show_search),
        }
        title, loader = sections.get(event.item_id, ("", lambda: None))
        self.query_one("#section-title", Label).update(title)
        self.query_one("#search-container").display = (event.item_id == "search")
        loader()

    def _load_liked(self) -> None:
        self.query_one("#section-title", Label).update("❤️  Liked Tracks — loading...")
        self.run_worker(self._fetch_liked)

    async def _fetch_liked(self) -> None:
        app = self._get_app()
        tracks = await asyncio.to_thread(app.api.get_liked_tracks, limit=100)
        track_list = self.query_one("#track-list", TrackList)
        track_list.tracks = tracks
        self.query_one("#section-title", Label).update(
            f"❤️  Liked Tracks ({len(tracks)})"
        )

    def _load_wave(self) -> None:
        self.query_one("#section-title", Label).update("🌊  My Wave — loading...")
        self.run_worker(self._fetch_wave)

    async def _fetch_wave(self) -> None:
        app = self._get_app()
        tracks = await asyncio.to_thread(app.api.start_wave)
        track_list = self.query_one("#track-list", TrackList)
        track_list.tracks = tracks
        self.query_one("#section-title", Label).update(
            f"🌊  My Wave ({len(tracks)})"
        )

    def _load_playlists(self) -> None:
        self.query_one("#section-title", Label).update("📁  Playlists — loading...")
        self.run_worker(self._fetch_playlists_and_pick)

    async def _fetch_playlists_and_pick(self) -> None:
        app = self._get_app()
        playlists = await asyncio.to_thread(app.api.get_playlists)
        if not playlists:
            track_list = self.query_one("#track-list", TrackList)
            track_list.tracks = []
            self.query_one("#section-title", Label).update("📁  No playlists found")
            return
        self._show_playlist_picker(playlists)

    def _show_playlist_picker(self, playlists) -> None:
        def on_picked(selected) -> None:
            if selected is not None:
                self.run_worker(self._load_selected_playlist(selected))
            else:
                self.query_one("#section-title", Label).update("📁  Playlists")

        self.app.push_screen(PlaylistPickerScreen(playlists), callback=on_picked)

    async def _load_selected_playlist(self, playlist) -> None:
        app = self._get_app()
        name = playlist.title or "Playlist"
        self.query_one("#section-title", Label).update(f"📁  {name} — loading...")
        tracks = await asyncio.to_thread(app.api.get_playlist_tracks, playlist, limit=100)
        track_list = self.query_one("#track-list", TrackList)
        track_list.tracks = tracks
        self.query_one("#section-title", Label).update(
            f"📁  {name} ({len(tracks)})"
        )

    def _show_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            query = event.value.strip()
            if query:
                self.query_one("#section-title", Label).update(
                    f"🔍  Searching: {query}..."
                )
                self.run_worker(self._do_search(query))

    async def _do_search(self, query: str) -> None:
        app = self._get_app()
        tracks = await asyncio.to_thread(app.api.search, query, limit=30)
        track_list = self.query_one("#track-list", TrackList)
        track_list.tracks = tracks
        self.query_one("#section-title", Label).update(
            f'🔍  Results for "{query}" ({len(tracks)})'
        )

    # ── Track selection ──

    def on_track_selected(self, event: TrackSelected) -> None:
        """Handle track selection from list."""
        app = self._get_app()
        if not app.player:
            return
        self.run_worker(self._play_selection(event.track, event.tracks, event.index))

    async def _play_selection(self, track: TrackInfo, tracks: list[TrackInfo], index: int) -> None:
        app = self._get_app()
        if self._is_wave_mode and app.api.radio_session:
            await asyncio.to_thread(app.api.radio_session.feedback_track_started, track)
        await asyncio.to_thread(app.player.set_queue, tracks, index)

    # ── Auto-load more wave tracks ──

    async def _on_track_end_wave(self) -> None:
        """When wave track ends, send feedback and maybe load more."""
        app = self._get_app()
        if not self._is_wave_mode or not app.player or not app.api.radio_session:
            return
        current = app.player.state.current_track
        if current:
            await asyncio.to_thread(
                app.api.radio_session.feedback_track_finished,
                current,
                app.player.state.duration,
            )
        queue = app.player.state.queue
        idx = app.player.state.queue_index
        if idx >= len(queue) - 2:
            more = await asyncio.to_thread(app.api.get_more_wave_tracks)
            if more:
                app.player.state.queue.extend(more)
                track_list = self.query_one("#track-list", TrackList)
                track_list.tracks = list(app.player.state.queue)

    # ── Player controls (keybindings) ──

    def action_toggle_pause(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.toggle_pause()

    def action_next_track(self) -> None:
        app = self._get_app()
        if app.player:
            self.run_worker(self._do_next_track)

    async def _do_next_track(self) -> None:
        app = self._get_app()
        if self._is_wave_mode and app.api.radio_session and app.player.state.current_track:
            await asyncio.to_thread(
                app.api.radio_session.feedback_skip,
                app.player.state.current_track,
                app.player.state.position,
            )
        await asyncio.to_thread(app.player.next_track)
        if self._is_wave_mode:
            await self._on_track_end_wave()

    def action_prev_track(self) -> None:
        app = self._get_app()
        if app.player:
            self.run_worker(self._do_prev_track)

    async def _do_prev_track(self) -> None:
        app = self._get_app()
        await asyncio.to_thread(app.player.prev_track)

    def action_volume_up(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.volume_up()

    def action_volume_down(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.volume_down()

    def action_seek_forward(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.seek(5)

    def action_seek_backward(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.seek(-5)

    def action_toggle_repeat(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.toggle_repeat()

    def action_toggle_shuffle(self) -> None:
        app = self._get_app()
        if app.player:
            app.player.toggle_shuffle()

    def action_like_track(self) -> None:
        self.run_worker(self._do_like_track)

    async def _do_like_track(self) -> None:
        app = self._get_app()
        if app.player and app.player.state.current_track:
            ok = await asyncio.to_thread(app.api.like_track, app.player.state.current_track)
            if ok:
                self.notify("❤️ Liked!", timeout=2)
            else:
                self.notify("Failed to like", timeout=2)

    def action_dislike_track(self) -> None:
        self.run_worker(self._do_dislike_track)

    async def _do_dislike_track(self) -> None:
        app = self._get_app()
        if app.player and app.player.state.current_track:
            ok = await asyncio.to_thread(app.api.dislike_track, app.player.state.current_track)
            if ok:
                self.notify("👎 Disliked (won't recommend)", timeout=2)
                if self._is_wave_mode:
                    await self._do_next_track()
            else:
                self.notify("Failed to dislike", timeout=2)

    def action_focus_search(self) -> None:
        self.on_nav_item_selected(NavItemSelected("search"))

    def action_nav_wave(self) -> None:
        self.on_nav_item_selected(NavItemSelected("wave"))

    def action_nav_liked(self) -> None:
        self.on_nav_item_selected(NavItemSelected("liked"))

    def action_nav_playlists(self) -> None:
        self.on_nav_item_selected(NavItemSelected("playlists"))

    def action_nav_search(self) -> None:
        self.on_nav_item_selected(NavItemSelected("search"))

    def action_show_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_quit_app(self) -> None:
        self._get_app().exit()


# ── Main App ─────────────────────────────────────────────────


class YMusicApp(App):
    """YMusic CLI — TUI player for Yandex Music."""

    TITLE = "YMusic CLI"
    SUB_TITLE = "Yandex Music in your terminal"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: Config | None = None) -> None:
        super().__init__()
        self.config = config or Config.load()
        self.api = YMusicAPI(self.config)
        self.player: Player | None = None

    def _init_player(self) -> None:
        """Initialize the player after successful login."""
        self.player = Player(self.api, volume=self.config.volume)
        self.player.on_end(self._on_track_end)

    def _on_track_end(self) -> None:
        """Handle natural end of track (dispatched from mpv thread)."""
        if self.player:
            # Safely schedule next track on event loop or thread
            asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(self.player.next_track),
                self._loop,
            )

    def on_mount(self) -> None:
        if self.config.is_authenticated and self.api.login():
            self._init_player()
            self.push_screen(MainScreen())
        else:
            self.push_screen(LoginScreen())

    def on_unmount(self) -> None:
        if self.player:
            self.config.volume = self.player.state.volume
            self.config.save()
            self.player.shutdown()

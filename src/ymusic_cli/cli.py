"""Interactive CLI shell for YMusic — like a real terminal application."""

from __future__ import annotations

import select
import sys
import termios
import threading
import time
import tty
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter

from ymusic_cli.config import Config
from ymusic_cli.api import YMusicAPI, TrackInfo
from ymusic_cli.player import Player, check_mpv_available

console = Console(highlight=False)

COMMANDS_HELP = {
    "liked":      "Show liked tracks",
    "wave":       "Start My Wave radio",
    "play N":     "Play track number N from the current list",
    "search Q":   "Search for tracks",
    "playlists":  "List your playlists",
    "open N":     "Open playlist number N",
    "next / n":   "Next track",
    "prev / p":   "Previous track",
    "pause":      "Toggle pause",
    "stop":       "Stop playback",
    "seek +/-N":  "Seek forward/backward N seconds",
    "vol N":      "Set volume (0-100)",
    "vol +/-N":   "Adjust volume",
    "repeat":     "Cycle repeat: off → all → one",
    "shuffle":    "Toggle shuffle",
    "like":       "Like current track",
    "dislike":    "Dislike current track (won't recommend)",
    "now":        "Show now playing",
    "queue":      "Show play queue",
    "status":     "Show account info",
    "help":       "Show this help",
    "quit / q":   "Exit",
}

COMPLETIONS = [
    "liked", "wave", "play", "search", "playlists", "open",
    "next", "prev", "pause", "stop", "seek", "vol", "volume",
    "repeat", "shuffle", "like", "dislike", "now", "queue",
    "status", "help", "quit", "q", "n", "p", "clear",
]


def format_track_line(i: int, t: TrackInfo, playing_id: str | None = None) -> Text:
    """Format a single track as a rich Text line."""
    is_playing = playing_id is not None and str(t.id) == playing_id
    prefix = "▶ " if is_playing else "  "
    style = "bold green" if is_playing else ""

    line = Text()
    line.append(f"{prefix}{i+1:>3}  ", style="dim" if not is_playing else "bold green")
    line.append(f"{t.title}", style=style or "bold")
    line.append(f"  {t.artists}", style=style or "cyan")
    line.append(f"  [{t.album}]", style="dim") if t.album else None
    line.append(f"  {t.duration_str}", style="dim")
    return line


def print_track_table(tracks: list[TrackInfo], title: str, playing_id: str | None = None) -> None:
    """Print a list of tracks as a compact table."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
        title=title,
        title_style="bold",
    )
    table.add_column("#", width=5, justify="right", style="dim")
    table.add_column("Title", ratio=3)
    table.add_column("Artist", ratio=2, style="cyan")
    table.add_column("Album", ratio=2, style="dim")
    table.add_column("Time", width=6, justify="right", style="dim")

    for i, t in enumerate(tracks):
        is_playing = playing_id is not None and str(t.id) == playing_id
        marker = "▶" if is_playing else ""
        num = f"{marker} {i+1}"
        t_style = "bold green" if is_playing else ""
        table.add_row(
            num,
            Text(t.title, style=t_style or "bold"),
            Text(t.artists, style="bold green" if is_playing else "cyan"),
            t.album,
            t.duration_str,
        )

    console.print(table)


def print_now_playing(player: Player) -> None:
    """Print current playback status."""
    s = player.state
    if not s.current_track:
        console.print("[dim]Nothing playing.[/dim]")
        return

    t = s.current_track
    status = "[bold green]▶ PLAYING[/bold green]" if s.is_playing else "[bold yellow]❚❚ PAUSED[/bold yellow]"

    # Progress bar
    width = 40
    filled = int(s.progress * width)
    bar = "━" * filled + "●" + "─" * (width - filled)

    console.print()
    console.print(f"  {status}  [bold]{t.artists}[/bold] — [bold]{t.title}[/bold]")
    if t.album:
        console.print(f"           [dim]{t.album}[/dim]")
    console.print(f"  [cyan]{bar}[/cyan]  {s.position_str} / {s.duration_str}")
    console.print(f"  vol: {s.volume}%  repeat: {s.repeat}  shuffle: {'on' if s.shuffle else 'off'}")
    console.print()


class YMusicShell:
    """Interactive REPL-style music player shell."""

    def __init__(self, config: Config, api: YMusicAPI) -> None:
        self.config = config
        self.api = api
        self.player: Player | None = None
        self.current_tracks: list[TrackInfo] = []
        self.cached_playlists: list[Any] = []
        self.is_wave_mode: bool = False
        self._completer = WordCompleter(COMPLETIONS, ignore_case=True)
        self._status_thread: threading.Thread | None = None
        self._running = True

    def start(self) -> None:
        """Main shell loop."""
        if not check_mpv_available():
            console.print("[red]Error: mpv not installed. sudo pacman -S mpv[/red]")
            sys.exit(1)

        # Login
        if not self.api.is_logged_in:
            if self.config.is_authenticated:
                console.print("[dim]Connecting to Yandex Music...[/dim]")
                if not self.api.login():
                    console.print("[red]Saved token is invalid. Run: ymusic auth[/red]")
                    sys.exit(1)
            else:
                console.print("[red]Not authenticated. Run: ymusic auth[/red]")
                sys.exit(1)

        self.player = Player(self.api, volume=self.config.volume)
        self.player.on_end(self._on_track_end)

        plus = "[green]Plus[/green]" if self.api.has_plus else "[red]No Plus[/red]"
        console.print(f"[bold]ymusic[/bold] v0.2.0 — {self.api.username} ({plus})")
        console.print("[dim]Type 'help' for commands, 'liked' to browse tracks, 'wave' for radio.[/dim]")
        console.print()

        try:
            self._loop()
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self._shutdown()

    def _loop(self) -> None:
        """Main REPL loop."""
        while self._running:
            try:
                raw = pt_prompt(
                    "ymusic> ",
                    completer=self._completer,
                    complete_while_typing=False,
                )
            except (KeyboardInterrupt, EOFError):
                break

            line = raw.strip()
            if not line:
                continue

            parts = line.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            self._dispatch(cmd, arg)

    def _dispatch(self, cmd: str, arg: str) -> None:
        """Route a command."""
        if cmd in ("q", "quit", "exit"):
            self._running = False
        elif cmd == "help":
            self._cmd_help()
        elif cmd == "liked":
            self._cmd_liked()
        elif cmd == "wave":
            self._cmd_wave()
        elif cmd == "play":
            self._cmd_play(arg)
        elif cmd == "search":
            self._cmd_search(arg)
        elif cmd == "playlists":
            self._cmd_playlists()
        elif cmd == "open":
            self._cmd_open(arg)
        elif cmd in ("next", "n"):
            self._cmd_next()
        elif cmd in ("prev", "p"):
            self._cmd_prev()
        elif cmd in ("pause", "c"):
            self._cmd_pause()
        elif cmd == "stop":
            self._cmd_stop()
        elif cmd == "seek":
            self._cmd_seek(arg)
        elif cmd in ("vol", "volume"):
            self._cmd_vol(arg)
        elif cmd == "repeat":
            self._cmd_repeat()
        elif cmd == "shuffle":
            self._cmd_shuffle()
        elif cmd == "like":
            self._cmd_like()
        elif cmd == "dislike":
            self._cmd_dislike()
        elif cmd == "now":
            self._cmd_now()
        elif cmd == "queue":
            self._cmd_queue()
        elif cmd == "status":
            self._cmd_status()
        elif cmd == "clear":
            console.clear()
        else:
            # Try as number — play track N
            try:
                n = int(cmd)
                self._cmd_play(str(n))
            except ValueError:
                console.print(f"[red]Unknown command:[/red] {cmd}. Type 'help'.")

    # ── Commands ─────────────────────────────────────────────

    def _cmd_help(self) -> None:
        table = Table(title="Commands", border_style="dim", show_header=False, padding=(0, 2))
        table.add_column("Command", style="bold green")
        table.add_column("Description")
        for cmd, desc in COMMANDS_HELP.items():
            table.add_row(cmd, desc)
        console.print(table)

    def _cmd_liked(self) -> None:
        console.print("[dim]Loading liked tracks...[/dim]")
        tracks = self.api.get_liked_tracks(limit=100)
        self.current_tracks = tracks
        self.is_wave_mode = False
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(tracks, f"❤️  Liked Tracks ({len(tracks)})", playing_id)

    def _cmd_wave(self) -> None:
        console.print("[dim]Starting My Wave...[/dim]")
        tracks = self.api.start_wave()
        self.current_tracks = tracks
        self.is_wave_mode = True
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(tracks, f"🌊 My Wave ({len(tracks)})", playing_id)
        console.print("[dim]Type a number to play, 'next'/'prev' to navigate.[/dim]")

    def _cmd_play(self, arg: str) -> None:
        if not arg:
            if self.player and self.player.state.current_track and not self.player.state.is_playing:
                self.player.resume()
                console.print("[green]▶ Resumed[/green]")
            else:
                console.print("[dim]Usage: play <N> or just type a track number.[/dim]")
            return

        try:
            n = int(arg)
        except ValueError:
            # Treat as search + play first result
            self._cmd_search(arg)
            if self.current_tracks:
                self._play_index(0)
            return

        self._play_index(n - 1)

    def _play_index(self, idx: int) -> None:
        if not self.current_tracks:
            console.print("[yellow]No tracks loaded. Try 'liked' or 'search <query>'.[/yellow]")
            return
        if idx < 0 or idx >= len(self.current_tracks):
            console.print(f"[red]Invalid track number. Range: 1-{len(self.current_tracks)}[/red]")
            return

        track = self.current_tracks[idx]

        # Wave feedback
        if self.is_wave_mode and self.api.radio_session:
            self.api.radio_session.feedback_track_started(track)

        console.print(f"[dim]Connecting stream...[/dim]")
        ok = self.player.set_queue(self.current_tracks, start_index=idx)
        if ok:
            console.print(f"[green]▶[/green] [bold]{track.artists}[/bold] — {track.title}")
        else:
            console.print(f"[red]Failed to play: {track.title}[/red]")

    def _cmd_search(self, query: str) -> None:
        if not query:
            console.print("[dim]Usage: search <query>[/dim]")
            return
        console.print(f"[dim]Searching '{query}'...[/dim]")
        tracks = self.api.search(query, limit=30)
        self.current_tracks = tracks
        self.is_wave_mode = False
        if not tracks:
            console.print(f"[yellow]No results for '{query}'.[/yellow]")
            return
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(tracks, f"🔍 Search: '{query}' ({len(tracks)})", playing_id)

    def _cmd_playlists(self) -> None:
        console.print("[dim]Loading playlists...[/dim]")
        playlists = self.api.get_playlists()
        self.cached_playlists = playlists
        if not playlists:
            console.print("[yellow]No playlists found.[/yellow]")
            return

        table = Table(title="📁 Playlists", border_style="dim", padding=(0, 1))
        table.add_column("#", width=4, justify="right", style="dim")
        table.add_column("Name", ratio=3, style="bold")
        table.add_column("Tracks", width=8, justify="right")

        for i, pl in enumerate(playlists):
            table.add_row(str(i + 1), pl.title or "Untitled", str(pl.track_count or "?"))

        console.print(table)
        console.print("[dim]Type 'open N' to open a playlist.[/dim]")

    def _cmd_open(self, arg: str) -> None:
        if not arg:
            console.print("[dim]Usage: open <N>[/dim]")
            return
        try:
            n = int(arg)
        except ValueError:
            console.print("[red]Usage: open <number>[/red]")
            return

        if not self.cached_playlists:
            console.print("[yellow]Load playlists first with 'playlists'.[/yellow]")
            return
        if n < 1 or n > len(self.cached_playlists):
            console.print(f"[red]Invalid playlist number. Range: 1-{len(self.cached_playlists)}[/red]")
            return

        pl = self.cached_playlists[n - 1]
        name = pl.title or "Playlist"
        console.print(f"[dim]Loading '{name}'...[/dim]")
        tracks = self.api.get_playlist_tracks(pl, limit=100)
        self.current_tracks = tracks
        self.is_wave_mode = False
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(tracks, f"📁 {name} ({len(tracks)})", playing_id)

    def _cmd_next(self) -> None:
        if not self.player:
            return
        # Wave feedback
        if self.is_wave_mode and self.api.radio_session and self.player.state.current_track:
            self.api.radio_session.feedback_skip(
                self.player.state.current_track, self.player.state.position
            )
        ok = self.player.next_track()
        if ok:
            t = self.player.state.current_track
            console.print(f"[green]▶[/green] [bold]{t.artists}[/bold] — {t.title}")
            self._wave_autoload()
        else:
            console.print("[dim]End of queue.[/dim]")

    def _cmd_prev(self) -> None:
        if not self.player:
            return
        ok = self.player.prev_track()
        if ok:
            t = self.player.state.current_track
            console.print(f"[green]▶[/green] [bold]{t.artists}[/bold] — {t.title}")

    def _cmd_pause(self) -> None:
        if not self.player:
            return
        self.player.toggle_pause()
        if self.player.state.is_playing:
            console.print("[green]▶ Playing[/green]")
        else:
            console.print("[yellow]❚❚ Paused[/yellow]")

    def _cmd_stop(self) -> None:
        if self.player:
            self.player.stop()
            console.print("[dim]Stopped.[/dim]")

    def _cmd_seek(self, arg: str) -> None:
        if not arg or not self.player:
            console.print("[dim]Usage: seek +10, seek -5[/dim]")
            return
        try:
            sec = float(arg)
            self.player.seek(sec)
            time.sleep(0.3)
            console.print(f"[dim]Position: {self.player.state.position_str}[/dim]")
        except ValueError:
            console.print("[red]Usage: seek +10, seek -5[/red]")

    def _cmd_vol(self, arg: str) -> None:
        if not self.player:
            return
        if not arg:
            console.print(f"Volume: {self.player.state.volume}%")
            return
        try:
            arg = arg.strip()
            if arg.startswith("+") or arg.startswith("-"):
                delta = int(arg)
                self.player.set_volume(self.player.state.volume + delta)
            else:
                self.player.set_volume(int(arg))
            console.print(f"Volume: {self.player.state.volume}%")
        except ValueError:
            console.print("[red]Usage: vol 50, vol +10, vol -5[/red]")

    def _cmd_repeat(self) -> None:
        if self.player:
            self.player.toggle_repeat()
            console.print(f"Repeat: {self.player.state.repeat}")

    def _cmd_shuffle(self) -> None:
        if self.player:
            self.player.toggle_shuffle()
            s = "on" if self.player.state.shuffle else "off"
            console.print(f"Shuffle: {s}")

    def _cmd_like(self) -> None:
        if not self.player or not self.player.state.current_track:
            console.print("[dim]Nothing playing.[/dim]")
            return
        t = self.player.state.current_track
        if self.api.like_track(t):
            console.print(f"[green]❤️  Liked: {t.title}[/green]")
        else:
            console.print("[red]Failed to like.[/red]")

    def _cmd_dislike(self) -> None:
        if not self.player or not self.player.state.current_track:
            console.print("[dim]Nothing playing.[/dim]")
            return
        t = self.player.state.current_track
        if self.api.dislike_track(t):
            console.print(f"[yellow]👎 Disliked: {t.title}[/yellow]")
            if self.is_wave_mode:
                self._cmd_next()
        else:
            console.print("[red]Failed to dislike.[/red]")

    def _cmd_now(self) -> None:
        if self.player:
            print_now_playing(self.player)

    def _cmd_queue(self) -> None:
        if not self.player or not self.player.state.queue:
            console.print("[dim]Queue is empty.[/dim]")
            return
        q = self.player.state.queue
        idx = self.player.state.queue_index
        playing_id = str(self.player.state.current_track.id) if self.player.state.current_track else None

        # Show window around current position
        start = max(0, idx - 3)
        end = min(len(q), idx + 12)
        window = q[start:end]

        table = Table(title=f"Queue ({idx+1}/{len(q)})", border_style="dim", padding=(0, 1))
        table.add_column("#", width=5, justify="right", style="dim")
        table.add_column("Title", ratio=3)
        table.add_column("Artist", ratio=2, style="cyan")
        table.add_column("Time", width=6, justify="right", style="dim")

        for i, t in enumerate(window):
            actual_i = start + i
            is_cur = actual_i == idx
            marker = "▶" if is_cur else ""
            st = "bold green" if is_cur else ""
            table.add_row(
                f"{marker} {actual_i+1}",
                Text(t.title, style=st or "bold"),
                Text(t.artists, style="bold green" if is_cur else "cyan"),
                t.duration_str,
            )

        console.print(table)

    def _cmd_status(self) -> None:
        plus = "Active ✓" if self.api.has_plus else "Inactive ✗"
        console.print(f"User:    [bold]{self.api.username}[/bold]")
        console.print(f"Plus:    {plus}")
        if self.player:
            console.print(f"Volume:  {self.player.state.volume}%")
            console.print(f"Repeat:  {self.player.state.repeat}")
            console.print(f"Shuffle: {'on' if self.player.state.shuffle else 'off'}")

    # ── Internals ────────────────────────────────────────────

    def _on_track_end(self) -> None:
        """Auto-next on natural track end (called from mpv thread)."""
        if self.is_wave_mode and self.api.radio_session and self.player.state.current_track:
            self.api.radio_session.feedback_track_finished(
                self.player.state.current_track, self.player.state.duration
            )
        if self.player:
            ok = self.player.next_track()
            if ok:
                t = self.player.state.current_track
                # Print from mpv thread — console is thread-safe in rich
                console.print(f"\n[green]▶[/green] [bold]{t.artists}[/bold] — {t.title}")
            self._wave_autoload()

    def _wave_autoload(self) -> None:
        """Load more wave tracks if near end of queue."""
        if not self.is_wave_mode or not self.api.radio_session or not self.player:
            return
        q = self.player.state.queue
        idx = self.player.state.queue_index
        if idx >= len(q) - 2:
            more = self.api.get_more_wave_tracks()
            if more:
                self.player.state.queue.extend(more)
                self.current_tracks = list(self.player.state.queue)

    def _shutdown(self) -> None:
        if self.player:
            self.config.volume = self.player.state.volume
            self.config.save()
            self.player.shutdown()
        console.print("[dim]Bye.[/dim]")

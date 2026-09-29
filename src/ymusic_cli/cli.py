"""Interactive CLI shell for YMusic — like a real terminal application."""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

from ymusic_cli.config import Config
from ymusic_cli.api import YMusicAPI, TrackInfo
from ymusic_cli.player import Player, check_mpv_available
from ymusic_cli.visualizer import (
    render_banner,
    render_tabs,
    render_now_card,
    run_visualizer,
)

console = Console(highlight=False)

COMMANDS_HELP = {
    "1":          "Категория 1: 🌊 Волна (радио)",
    "2":          "Категория 2: ❤️ Избранное (лайкнутые треки)",
    "3 [N]":      "Категория 3: 📁 Плейлисты (или '3 N' открыть плейлист N)",
    "4 [Q]":      "Категория 4: 🔍 Поиск (или '4 <запрос>')",
    "5":          "Категория 5: 📜 Очередь треков",
    "6":          "Категория 6: 🎤 Текст текущей песни",
    "vis":        "Интерактивный ASCII аудио-спектрограф (Esc/q выход)",
    "play N":     "Воспроизвести трек номер N",
    "now":        "Карточка Now Playing с анимированной кассетой",
    "next / n":   "Следующий трек",
    "prev / p":   "Предыдущий трек",
    "pause":      "Пауза / продолжить",
    "stop":       "Остановить воспроизведение",
    "seek +/-N":  "Перемотка на N секунд",
    "vol N":      "Громкость (0-100, +N, -N)",
    "repeat":     "Режим повтора: off → all → one",
    "shuffle":    "Перемешивание (вкл/выкл)",
    "like":       "Поставить лайк",
    "dislike":    "Дизлайк (не рекомендовать)",
    "status":     "Статус аккаунта и подписки",
    "help":       "Список всех команд",
    "quit / q":   "Выход",
}

_BASE_COMPLETIONS = [
    "1", "2", "3", "4", "5", "6",
    "tab", "t1", "t2", "t3", "t4", "t5", "t6",
    "vis", "visualizer", "lyrics",
    "liked", "wave", "play", "search", "playlists", "open",
    "next", "prev", "pause", "stop", "seek", "vol", "volume",
    "repeat", "shuffle", "like", "dislike", "now", "queue",
    "status", "help", "quit", "q", "n", "p", "clear",
]
COMPLETIONS = _BASE_COMPLETIONS + [f"/{c}" for c in _BASE_COMPLETIONS]


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


def print_track_table(
    tracks: list[TrackInfo],
    title: str,
    playing_id: str | None = None,
    current_index: int | None = None,
    show_all: bool = False,
    console_out: Console | None = None,
) -> None:
    """Print a list of tracks as a compact 3-track sliding window table (Prev, Playing, Next)."""
    out = console_out or console
    if not tracks:
        out.print("[dim]Список треков пуст.[/dim]")
        return

    # Determine currently active index
    cur_idx = 0
    if current_index is not None and 0 <= current_index < len(tracks):
        cur_idx = current_index
    elif playing_id is not None:
        for idx, t in enumerate(tracks):
            if str(t.id) == str(playing_id):
                cur_idx = idx
                break

    # If show_all requested or total tracks <= 3, show all
    if show_all or len(tracks) <= 3:
        indices = list(range(len(tracks)))
    else:
        # 3-track sliding window: previous, current (playing), next
        if cur_idx == 0:
            indices = [0, 1, 2]
        elif cur_idx >= len(tracks) - 1:
            indices = [len(tracks) - 3, len(tracks) - 2, len(tracks) - 1]
        else:
            indices = [cur_idx - 1, cur_idx, cur_idx + 1]

    if len(tracks) > 3 and not show_all:
        display_title = f"{title} [dim]— 3 из {len(tracks)} треков[/dim]"
    else:
        display_title = title

    caption = (
        f"[dim]Позиция: {cur_idx + 1}/{len(tracks)} • "
        f"Команды: [bold]n[/bold] (след), [bold]p[/bold] (пред), [bold]play <номер>[/bold][/dim]"
    )

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
        title=display_title,
        title_style="bold",
        caption=caption if len(tracks) > 1 else None,
    )
    table.add_column("Статус", width=13, justify="center")
    table.add_column("#", width=5, justify="right", style="dim")
    table.add_column("Название", ratio=3)
    table.add_column("Исполнитель", ratio=2, style="cyan")
    table.add_column("Альбом", ratio=2, style="dim")
    table.add_column("Время", width=6, justify="right", style="dim")

    for i in indices:
        t = tracks[i]
        is_playing = playing_id is not None and str(t.id) == str(playing_id)
        is_cur = i == cur_idx

        if is_playing:
            status_text = Text("▶ Играет", style="bold green")
            num_text = Text(f"{i + 1}", style="bold green")
            title_text = Text(t.title, style="bold white")
            artist_text = Text(t.artists, style="bold green")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="bold green")
        elif is_cur:
            status_text = Text("● Выбран", style="bold cyan")
            num_text = Text(f"{i + 1}", style="bold cyan")
            title_text = Text(t.title, style="bold")
            artist_text = Text(t.artists, style="cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        elif i == cur_idx - 1:
            status_text = Text("⏮ Предыдущий", style="dim cyan")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="dim")
            artist_text = Text(t.artists, style="dim cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        elif i < cur_idx:
            status_text = Text("⏮ Ранее", style="dim")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="dim")
            artist_text = Text(t.artists, style="dim")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        elif i == cur_idx + 1:
            status_text = Text("⏭ Следующий", style="dim yellow")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="white")
            artist_text = Text(t.artists, style="cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        else:
            status_text = Text("⏭ Далее", style="dim")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="dim white")
            artist_text = Text(t.artists, style="dim cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")

        table.add_row(
            status_text,
            num_text,
            title_text,
            artist_text,
            album_text,
            time_text,
        )

    out.print(table)


def print_now_playing(player: Player) -> None:
    """Print current playback status."""
    console.print(render_now_card(player))


class YMusicShell:
    """Interactive REPL-style music player shell."""

    def __init__(self, config: Config, api: YMusicAPI) -> None:
        self.config = config
        self.api = api
        self.player: Player | None = None
        self.current_tracks: list[TrackInfo] = []
        self.cached_playlists: list[Any] = []
        self.is_wave_mode: bool = False
        self.active_tab: int = 1
        self._completer = WordCompleter(COMPLETIONS, ignore_case=True)
        self._status_thread: threading.Thread | None = None
        self._running = True

    def start(self, initial_command: str | None = None) -> None:
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

        console.print(
            render_banner(
                username=self.api.username,
                has_plus=self.api.has_plus,
                quality=self.config.quality,
            )
        )
        console.print(render_tabs(self.active_tab))
        console.print()

        if initial_command:
            parts = initial_command.strip().lstrip("/").split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            self._dispatch(cmd, arg)

        try:
            self._loop()
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self._shutdown()

    def _bottom_toolbar(self) -> str:
        s = self.player.state if self.player else None
        tab_names = {1: "Волна", 2: "Избранное", 3: "Плейлисты", 4: "Поиск", 5: "Очередь", 6: "Текст"}
        cur_tab = tab_names.get(self.active_tab, str(self.active_tab))
        if s and s.current_track:
            icon = "▶" if s.is_playing else "❚❚"
            t = s.current_track
            return f" {icon} {t.artists} - {t.title} [{s.position_str}/{s.duration_str}] Vol:{s.volume}% | Категория [{self.active_tab}: {cur_tab}] | Цифры [1-6] категории | 'vis'"
        return f" ■ Idle | Категория [{self.active_tab}: {cur_tab}] | Цифры [1-6]: выбор категорий | 'play <N>', 'help'"

    def _loop(self) -> None:
        """Main REPL loop with thread-safe stdout patching."""
        while self._running:
            try:
                with patch_stdout():
                    raw = pt_prompt(
                        "ymusic> ",
                        completer=self._completer,
                        complete_while_typing=False,
                        bottom_toolbar=self._bottom_toolbar,
                    )
            except (KeyboardInterrupt, EOFError):
                break

            line = raw.strip()
            if not line:
                continue

            if line.startswith("/"):
                line = line[1:].strip()
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
        elif cmd in ("1", "2", "3", "4", "5", "6"):
            self._cmd_tab_num(int(cmd), arg)
        elif cmd in ("t1", "t2", "t3", "t4", "t5", "t6"):
            self._cmd_tab_num(int(cmd[1:]), arg)
        elif cmd in ("tab1", "tab2", "tab3", "tab4", "tab5", "tab6"):
            self._cmd_tab_num(int(cmd[3:]), arg)
        elif cmd in ("tab", "t"):
            self._cmd_tab(arg)
        elif cmd == "help":
            self._cmd_help()
        elif cmd in ("vis", "visualizer"):
            self._cmd_vis()
        elif cmd in ("lyrics", "text", "lyric"):
            self._cmd_lyrics()
        elif cmd == "liked":
            self._cmd_liked(arg)
        elif cmd == "wave":
            self._cmd_wave(arg)
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
            self._cmd_queue(arg)
        elif cmd == "status":
            self._cmd_status()
        elif cmd == "clear":
            console.clear()
            console.print(render_tabs(self.active_tab))
            console.print()
        else:
            # Try as number — play track N (if N > 6 or if play prefix was omitted)
            try:
                n = int(cmd)
                self._cmd_play(str(n))
            except ValueError:
                console.print(f"[red]Неизвестная команда:[/red] {cmd}. Введите 1-6 для выбора категории или 'help'.")

    # ── Commands ─────────────────────────────────────────────

    def _cmd_tab_num(self, tab_id: int, arg: str = "") -> None:
        """Switch category / tab directly by number 1-6."""
        self.active_tab = tab_id
        if tab_id == 1:
            self._cmd_wave(arg)
        elif tab_id == 2:
            self._cmd_liked(arg)
        elif tab_id == 3:
            if arg:
                self._cmd_open(arg)
            else:
                self._cmd_playlists()
        elif tab_id == 4:
            if arg:
                self._cmd_search(arg)
            else:
                console.print(render_tabs(self.active_tab))
                console.print("[dim]Категория 4: Поиск. Введите: 4 <запрос> или search <запрос>[/dim]")
        elif tab_id == 5:
            self._cmd_queue(arg)
        elif tab_id == 6:
            self._cmd_lyrics()

    def _cmd_tab(self, arg: str) -> None:
        """Switch active tab."""
        parts = arg.strip().split(None, 1)
        if not parts:
            console.print(render_tabs(self.active_tab))
            return
        first = parts[0]
        extra_arg = parts[1] if len(parts) > 1 else ""
        try:
            tab_id = int(first)
        except ValueError:
            arg_lower = first.lower()
            mapping = {
                "wave": 1, "волна": 1,
                "liked": 2, "лайки": 2, "избранное": 2,
                "playlists": 3, "playlist": 3, "плейлисты": 3,
                "search": 4, "поиск": 4,
                "queue": 5, "очередь": 5,
                "lyrics": 6, "текст": 6, "text": 6, "lyric": 6,
            }
            tab_id = mapping.get(arg_lower, 0)

        if tab_id < 1 or tab_id > 6:
            console.print("[red]Неверная категория. Доступны: 1-6 (1:Волна, 2:Избранное, 3:Плейлисты, 4:Поиск, 5:Очередь, 6:Текст)[/red]")
            return

        self._cmd_tab_num(tab_id, extra_arg)

    def _cmd_vis(self) -> None:
        """Launch interactive ASCII spectrum visualizer."""
        if not self.player:
            return
        run_visualizer(self.player, self.api, console)
        console.print(render_tabs(self.active_tab))
        console.print()

    def _cmd_lyrics(self) -> None:
        """Display lyrics for the current track."""
        self.active_tab = 6
        if not self.player or not self.player.state.current_track:
            console.print(render_tabs(self.active_tab))
            console.print("[dim]Nothing playing. Start a track to view lyrics.[/dim]")
            return

        t = self.player.state.current_track
        console.print("[dim]Fetching lyrics...[/dim]")
        lyrics = self.api.get_track_lyrics(t)

        console.print(render_tabs(self.active_tab))
        if not lyrics:
            console.print(
                Panel(
                    f"[yellow]No lyrics found for [bold]{t.title}[/bold] by [cyan]{t.artists}[/cyan].[/yellow]",
                    title="🎤 Track Lyrics",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            return

        console.print(
            Panel(
                str(lyrics).strip(),
                title=f"🎤 [bold white]{t.title}[/bold white] — [bold cyan]{t.artists}[/bold cyan]",
                subtitle="[dim]Yandex Music Lyrics[/dim]",
                border_style="magenta",
                padding=(1, 3),
            )
        )

    def _cmd_help(self) -> None:
        console.print(render_tabs(self.active_tab))
        table = Table(title="Commands", border_style="dim", show_header=False, padding=(0, 2))
        table.add_column("Command", style="bold green")
        table.add_column("Description")
        for cmd, desc in COMMANDS_HELP.items():
            table.add_row(cmd, desc)
        console.print(table)

    def _cmd_liked(self, arg: str = "") -> None:
        self.active_tab = 2
        console.print(render_tabs(self.active_tab))
        console.print("[dim]Loading liked tracks...[/dim]")
        tracks = self.api.get_liked_tracks(limit=100)
        self.current_tracks = tracks
        self.is_wave_mode = False
        show_all = (arg.strip().lower() == "all")
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(tracks, "❤️ Избранное", playing_id=playing_id, show_all=show_all)

    def _cmd_wave(self, arg: str = "") -> None:
        self.active_tab = 1
        console.print(render_tabs(self.active_tab))
        console.print("[dim]Starting My Wave...[/dim]")
        tracks = self.api.start_wave()
        self.current_tracks = tracks
        self.is_wave_mode = True
        show_all = (arg.strip().lower() == "all")
        if tracks:
            self._play_index(0)
            playing_id = str(tracks[0].id)
        else:
            playing_id = None
        print_track_table(tracks, "🌊 Моя Волна", playing_id=playing_id, show_all=show_all)

    def _cmd_play(self, arg: str) -> None:
        clean_arg = arg.strip()
        if not clean_arg:
            if self.player and self.player.state.current_track and not self.player.state.is_playing:
                self.player.resume()
                console.print("[green]▶ Resumed[/green]")
            elif self.current_tracks:
                self._play_index(0)
            else:
                console.print("[dim]Usage: play <N> or just type a track number.[/dim]")
            return

        try:
            n = int(clean_arg)
        except ValueError:
            # Treat as search + play first result
            self._cmd_search(clean_arg)
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
        q = query.strip()
        if not q:
            console.print("[dim]Usage: search <query>[/dim]")
            return
        self.active_tab = 4
        console.print(render_tabs(self.active_tab))
        console.print(f"[dim]Searching '{q}'...[/dim]")
        tracks = self.api.search(q, limit=30)
        self.current_tracks = tracks
        self.is_wave_mode = False
        if not tracks:
            console.print(f"[yellow]No results for '{q}'.[/yellow]")
            return
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(tracks, f"🔍 Поиск: '{q}'", playing_id)

    def _cmd_playlists(self) -> None:
        self.active_tab = 3
        console.print(render_tabs(self.active_tab))
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
        parts = arg.strip().split()
        try:
            n = int(parts[0])
        except ValueError:
            console.print("[red]Usage: open <number>[/red]")
            return

        if not self.cached_playlists:
            console.print("[yellow]Load playlists first with 'playlists'.[/yellow]")
            return
        if n < 1 or n > len(self.cached_playlists):
            console.print(f"[red]Invalid playlist number. Range: 1-{len(self.cached_playlists)}[/red]")
            return

        show_all = len(parts) > 1 and parts[1].lower() == "all"
        pl = self.cached_playlists[n - 1]
        name = pl.title or "Playlist"
        self.active_tab = 3
        console.print(render_tabs(self.active_tab))
        console.print(f"[dim]Loading '{name}'...[/dim]")
        tracks = self.api.get_playlist_tracks(pl, limit=100)
        self.current_tracks = tracks
        self.is_wave_mode = False
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(tracks, f"📁 {name}", playing_id, show_all=show_all)

    def _cmd_next(self) -> None:
        if not self.player:
            return
        # Wave feedback
        if self.is_wave_mode and self.api.radio_session and self.player.state.current_track:
            self.api.radio_session.feedback_skip(
                self.player.state.current_track, self.player.state.position
            )
        ok = self.player.next_track()
        if not ok and self.is_wave_mode:
            self._wave_autoload()
            ok = self.player.next_track()
        if ok:
            t = self.player.state.current_track
            if t:
                q = self.player.state.queue
                idx = self.player.state.queue_index
                print_track_table(q, "📜 Очередь", playing_id=str(t.id), current_index=idx)
            self._wave_autoload()
        else:
            console.print("[dim]End of queue.[/dim]")

    def _cmd_prev(self) -> None:
        if not self.player:
            return
        ok = self.player.prev_track()
        if ok:
            t = self.player.state.current_track
            if t:
                q = self.player.state.queue
                idx = self.player.state.queue_index
                print_track_table(q, "📜 Очередь", playing_id=str(t.id), current_index=idx)

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
        if not self.player or not self.player.state.current_track or not self.player.state.is_playing:
            console.print("[dim]Nothing playing.[/dim]")
            return
        clean_arg = arg.strip()
        if not clean_arg:
            console.print("[dim]Usage: seek +10, seek -5[/dim]")
            return
        try:
            sec = float(clean_arg)
            self.player.seek(sec)
            time.sleep(0.3)
            console.print(f"[dim]Position: {self.player.state.position_str}[/dim]")
        except ValueError:
            console.print("[red]Usage: seek +10, seek -5[/red]")
        except Exception as e:
            console.print(f"[red]Seek error:[/red] {e}")

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
            console.print(render_now_card(self.player, self.active_tab))

    def _cmd_queue(self, arg: str = "") -> None:
        self.active_tab = 5
        console.print(render_tabs(self.active_tab))
        if not self.player or not self.player.state.queue:
            console.print("[dim]Queue is empty.[/dim]")
            return
        q = self.player.state.queue
        idx = self.player.state.queue_index
        show_all = (arg.strip().lower() == "all")
        playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
        print_track_table(q, "📜 Очередь", playing_id=playing_id, current_index=idx, show_all=show_all)

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
        if not self.player or self.player._shutting_down:
            return
        if self.is_wave_mode and self.api.radio_session and self.player.state.current_track:
            self.api.radio_session.feedback_track_finished(
                self.player.state.current_track, self.player.state.duration
            )
        ok = self.player.next_track()
        if not ok and self.is_wave_mode:
            self._wave_autoload()
            ok = self.player.next_track()
        if ok and self.player.state.current_track:
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
                self.player.extend_queue(more)
                self.current_tracks = list(self.player.state.queue)

    def _shutdown(self) -> None:
        if self.player:
            self.config.volume = self.player.state.volume
            self.config.save()
            self.player.shutdown()
        console.print("[dim]Bye.[/dim]")

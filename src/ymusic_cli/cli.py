"""Interactive CLI shell for YMusic — clean, fast, and responsive.

Strict, minimalist terminal design with no emojis, automatic console screen
clearing to avoid clutter, and cross-platform compatibility.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


from ymusic_cli.config import Config
from ymusic_cli.api import YMusicAPI, TrackInfo
from ymusic_cli.player import Player, check_mpv_available
from ymusic_cli.auth import run_browser_device_auth
from ymusic_cli.visualizer import (
    render_mini_tabs,
    render_mini_track_bar,
    render_mini_header,
    render_now_card,
)

console = Console(highlight=False)

COMMANDS_HELP = {
    "1":          "Категория 1: Волна (Моя Волна)",
    "2":          "Категория 2: Лайки (Избранные треки)",
    "3 [N]":      "Категория 3: Плейлисты (или '3 N' открыть плейлист N)",
    "4 [Q]":      "Категория 4: Поиск (или '4 <запрос>')",
    "play N":     "Воспроизвести трек номер N",
    "now":        "Карточка Now Playing (компактный статус)",
    "next / n":   "Следующий трек",
    "prev / p":   "Предыдущий трек",
    "pause / c":  "Пауза / продолжить",
    "stop":       "Остановить воспроизведение",
    "seek +/-N":  "Перемотка на N секунд",
    "vol N / +/-": "Громкость (0-100, +N, -N, +, -)",
    "repeat / r": "Режим повтора: off -> all -> one",
    "shuffle / s": "Перемешивание (вкл/выкл)",
    "like / l":   "Поставить лайк [+] ",
    "dislike / d": "Дизлайк [-] (пропустить)",
    "auth / update": "Принудительно обновить токен через браузер",
    "clear / cls": "Очистить экран терминала",
    "status":     "Статус аккаунта и подписки",
    "help":       "Список всех команд",
    "quit / q":   "Выход",
}

_BASE_COMPLETIONS = [
    "1", "2", "3", "4",
    "tab", "t1", "t2", "t3", "t4",
    "liked", "wave", "play", "search", "playlists", "open",
    "next", "prev", "pause", "stop", "seek", "vol", "volume",
    "repeat", "shuffle", "like", "dislike", "now",
    "auth", "update", "token", "update-token", "status", "help", "quit", "q", "n", "p", "clear", "cls",
    "волна", "лайки", "избранное", "поиск", "плейлисты", "выход",
    "с", "т", "з", "д", "в", "к", "ы", "й",
]
COMPLETIONS = _BASE_COMPLETIONS + [f"/{c}" for c in _BASE_COMPLETIONS]


def format_track_line(i: int, t: TrackInfo, playing_id: str | None = None) -> Text:
    """Format a single track as a rich Text line (strictly emoji-free)."""
    is_playing = playing_id is not None and str(t.id) == playing_id
    prefix = "> " if is_playing else "  "
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
    """Print tracks as a compact 3-track sliding window table (Prev, Playing, Next)."""
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
        display_title = f"{title} [dim]- 3 из {len(tracks)} треков[/dim]"
    else:
        display_title = title

    try:
        term_width = out.width or os.get_terminal_size().columns
    except OSError:
        term_width = 80

    caption = (
        f"[dim]Позиция: {cur_idx + 1}/{len(tracks)} | "
        f"Команды: [bold]n[/bold] (след), [bold]p[/bold] (пред), [bold]play <номер>[/bold][/dim]"
    ) if term_width >= 55 else None

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
        title=display_title,
        title_style="bold",
        caption=caption if len(tracks) > 1 else None,
    )

    include_album = term_width >= 72
    include_time = term_width >= 48

    table.add_column("Статус", width=14 if term_width >= 55 else 8, justify="center", no_wrap=True)
    table.add_column("#", width=5 if term_width >= 55 else 3, justify="right", style="dim", no_wrap=True)
    table.add_column("Название", ratio=3, overflow="ellipsis", no_wrap=True)
    table.add_column("Исполнитель", ratio=2, style="cyan", overflow="ellipsis", no_wrap=True)
    if include_album:
        table.add_column("Альбом", ratio=2, style="dim", overflow="ellipsis", no_wrap=True)
    if include_time:
        table.add_column("Время", width=6, justify="right", style="dim", no_wrap=True)

    for i in indices:
        t = tracks[i]
        is_playing = playing_id is not None and str(t.id) == str(playing_id)
        is_cur = i == cur_idx

        if is_playing:
            status_text = Text(">> Играет", style="bold green")
            num_text = Text(f"{i + 1}", style="bold green")
            title_text = Text(t.title, style="bold white")
            artist_text = Text(t.artists, style="bold green")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="bold green")
        elif is_cur:
            status_text = Text("* Выбран", style="bold cyan")
            num_text = Text(f"{i + 1}", style="bold cyan")
            title_text = Text(t.title, style="bold")
            artist_text = Text(t.artists, style="cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        elif i == cur_idx - 1:
            status_text = Text("<< Предыдущий", style="dim cyan")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="dim")
            artist_text = Text(t.artists, style="dim cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        elif i < cur_idx:
            status_text = Text("<< Ранее", style="dim")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="dim")
            artist_text = Text(t.artists, style="dim")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        elif i == cur_idx + 1:
            status_text = Text(">> Следующий", style="dim yellow")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="white")
            artist_text = Text(t.artists, style="cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")
        else:
            status_text = Text(">> Далее", style="dim")
            num_text = Text(f"{i + 1}", style="dim")
            title_text = Text(t.title, style="dim white")
            artist_text = Text(t.artists, style="dim cyan")
            album_text = Text(t.album, style="dim")
            time_text = Text(t.duration_str, style="dim")

        row_parts = [status_text, num_text, title_text, artist_text]
        if include_album:
            row_parts.append(album_text)
        if include_time:
            row_parts.append(time_text)

        table.add_row(*row_parts)

    out.print(table)


class YMusicShell:
    """Rich interactive REPL shell for YMusic with clean screen management and responsive TUI."""

    def __init__(self, config: Config, api: YMusicAPI) -> None:
        self.config = config
        self.api = api
        self.player: Player | None = None
        self.current_tracks: list[TrackInfo] = []
        self.cached_playlists: list[Any] = []
        self.active_tab: int = 1
        self.is_wave_mode: bool = False
        self._running = True
        self._notification: str = ""
        self._custom_view: Any = None
        self._active_playlist_title: str = ""
        self._last_search_query: str = ""
        self._show_all: bool = False
        self._kb = object()

    def set_notification(self, msg: str) -> None:
        self._notification = msg

    def _print_playlists_table(self) -> None:
        if not self.cached_playlists:
            console.print("[yellow]Плейлисты не найдены.[/yellow]")
            return
        table = Table(title="Плейлисты", border_style="dim", padding=(0, 1))
        table.add_column("#", width=4, justify="right", style="dim")
        table.add_column("Название", ratio=3, style="bold")
        try:
            tw = os.get_terminal_size().columns
        except OSError:
            tw = 80
        if tw >= 45:
            table.add_column("Треков", width=8, justify="right")
            for i, pl in enumerate(self.cached_playlists):
                table.add_row(str(i + 1), pl.title or "Без названия", str(pl.track_count or "?"))
        else:
            for i, pl in enumerate(self.cached_playlists):
                table.add_row(str(i + 1), pl.title or "Без названия")
        console.print(table)
        console.print("[dim]Введите 'open N' (или '3 N') чтобы открыть плейлист.[/dim]")

    def _redraw_active_view(self) -> None:
        """Redraw current active category content or custom message view."""
        if self._custom_view is not None:
            console.print(self._custom_view)
            self._custom_view = None
            return

        if self.active_tab == 3:
            if self.current_tracks:
                playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
                cur_idx = self.player.state.queue_index if self.player and self.player.state.current_track else None
                title = f"Плейлист: {self._active_playlist_title}" if self._active_playlist_title else "Плейлист"
                print_track_table(self.current_tracks, title, playing_id=playing_id, current_index=cur_idx, show_all=self._show_all)
            else:
                self._print_playlists_table()
            return

        if self.active_tab == 4:
            if self.current_tracks:
                playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
                cur_idx = self.player.state.queue_index if self.player and self.player.state.current_track else None
                title = f"Поиск: '{self._last_search_query}'" if self._last_search_query else "Поиск"
                print_track_table(self.current_tracks, title, playing_id=playing_id, current_index=cur_idx, show_all=self._show_all)
            else:
                console.print("[dim]Категория 4: Поиск. Введите: 4 <запрос> или search <запрос>[/dim]")
            return

        if self.current_tracks:
            playing_id = str(self.player.state.current_track.id) if self.player and self.player.state.current_track else None
            cur_idx = self.player.state.queue_index if self.player and self.player.state.current_track else None
            title = "Моя Волна" if self.is_wave_mode else "Избранное"
            print_track_table(self.current_tracks, title, playing_id=playing_id, current_index=cur_idx, show_all=self._show_all)
        else:
            console.print("[dim]Категория 1: Волна. Введите '1' для старта радио или '2' для избранного.[/dim]")

    def _clear_view(self, redraw_content: bool = False) -> None:
        """Clear terminal and render compact mini header."""
        if sys.platform == "win32":
            os.system("cls")
        else:
            sys.stdout.write("\033[H\033[2J")
            sys.stdout.flush()
        console.print(render_mini_tabs(self.active_tab))
        if self.player:
            console.print(render_mini_track_bar(self.player))
        console.print()
        if redraw_content:
            self._redraw_active_view()

    def start(self, initial_command: str | None = None) -> None:
        """Launch the shell."""
        if not check_mpv_available():
            console.print("[bold red]Ошибка:[/bold red] mpv не установлен.")
            sys.exit(1)

        self.player = Player(self.api, volume=self.config.volume)
        self.player.on_end(self._on_track_end)

        # Clear screen and display clean header + content
        self._clear_view(redraw_content=True)

        if initial_command:
            parts = initial_command.strip().lstrip("/").split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            self._dispatch(cmd, arg)
            self._clear_view(redraw_content=True)

        try:
            self._loop()
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self._shutdown()

    def _bottom_toolbar(self) -> str:
        s = self.player.state if self.player else None
        tab_names = {1: "Волна", 2: "Лайки", 3: "Плейлисты", 4: "Поиск"}
        cur_tab = tab_names.get(self.active_tab, str(self.active_tab))
        try:
            w = os.get_terminal_size().columns
        except OSError:
            w = 80

        notif = ""
        if self._notification:
            notif = f" | {self._notification}"
            self._notification = ""

        if s and s.current_track:
            icon = "▶" if s.is_playing else "⏸"
            t = s.current_track
            base = f" {icon} {t.artists} - {t.title}"
            pos = f" [{s.position_str}/{s.duration_str}]"
            vol = f" 🔊{s.volume}%"
            tab = f" [{self.active_tab}: {cur_tab}]"

            if w < 50:
                tab = f" [{self.active_tab}]"
                avail = max(6, w - len(vol) - len(tab) - len(notif) - 2)
                if len(base) > avail:
                    base = base[: max(1, avail - 1)] + "…"
                return f"{base}{vol}{tab}{notif}"
            elif w < 72:
                avail = max(6, w - len(pos) - len(vol) - len(tab) - len(notif) - 2)
                if len(base) > avail:
                    base = base[: max(1, avail - 1)] + "…"
                return f"{base}{pos}{vol}{tab}{notif}"
            else:
                avail = w - len(pos) - len(vol) - len(tab) - len(notif) - 2
                if len(base) > avail and avail > 10:
                    base = base[:avail - 1] + "…"
                return f"{base}{pos}{vol}{tab}{notif}"

        if w < 40:
            return f" · Idle [{self.active_tab}]"
        elif w < 60:
            return f" · Idle | [{self.active_tab}: {cur_tab}] | 'help'"
        return f" · Idle | [{self.active_tab}: {cur_tab}] | 1-4: категории | 'help'"

    def _loop(self) -> None:
        """Main REPL loop with native readline support and auto-clean."""
        try:
            import readline
            readline.set_completer_delims(" \t\n/")

            def _readline_completer(text: str, state: int):
                matches = [c for c in COMPLETIONS if c.lower().startswith(text.lower())]
                if state < len(matches):
                    return matches[state]
                return None

            readline.set_completer(_readline_completer)
            readline.parse_and_bind("tab: complete")
        except (ImportError, AttributeError):
            pass

        while self._running:
            prompt_str = f"ymusic [{self._notification}]> " if self._notification else "ymusic> "
            self._notification = ""
            try:
                raw = input(prompt_str)
            except (KeyboardInterrupt, EOFError):
                break

            line = raw.strip()
            if not line:
                self._clear_view(redraw_content=True)
                continue

            if line.startswith("/"):
                line = line[1:].strip()
            if not line:
                self._clear_view(redraw_content=True)
                continue

            parts = line.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            self._dispatch(cmd, arg)

            # Auto-clear and self-refresh window after every console input
            if self._running and cmd not in ("auth", "update", "token", "update-token"):
                self._clear_view(redraw_content=True)

    def _dispatch(self, cmd: str, arg: str) -> None:
        """Route a command."""
        if cmd in ("q", "quit", "exit"):
            self._running = False
        elif cmd in ("1", "2", "3", "4"):
            self._cmd_tab_num(int(cmd), arg)
        elif cmd in ("t1", "t2", "t3", "t4"):
            self._cmd_tab_num(int(cmd[1:]), arg)
        elif cmd in ("tab1", "tab2", "tab3", "tab4"):
            self._cmd_tab_num(int(cmd[3:]), arg)
        elif cmd in ("tab", "t"):
            self._cmd_tab(arg)
        elif cmd == "help":
            self._cmd_help()
        elif cmd in ("liked", "likes"):
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
        elif cmd in ("+", "="):
            self._cmd_vol("+5")
        elif cmd in ("-", "_"):
            self._cmd_vol("-5")
        elif cmd in ("m", "mute"):
            if self.player:
                if self.player.state.volume > 0:
                    self._saved_vol = self.player.state.volume
                    self._cmd_vol("0")
                else:
                    self._cmd_vol(str(getattr(self, "_saved_vol", 50)))
        elif cmd in ("repeat", "r"):
            self._cmd_repeat()
        elif cmd in ("shuffle", "s"):
            self._cmd_shuffle()
        elif cmd in ("like", "l"):
            self._cmd_like()
        elif cmd in ("dislike", "d"):
            self._cmd_dislike()
        elif cmd == "now":
            self._cmd_now()
        elif cmd in ("auth", "update", "token", "update-token"):
            self._cmd_auth(arg)
        elif cmd == "status":
            self._cmd_status()
        elif cmd in ("clear", "cls"):
            self._clear_view(redraw_content=True)
        # Russian keyboard aliases
        elif cmd in ("с",):  # Russian 'с' = latin 'c'
            self._cmd_pause()
        elif cmd in ("т",):  # Russian 'т' = latin 'n' (next)
            self._cmd_next()
        elif cmd in ("з",):  # Russian 'з' = latin 'p' (prev)
            self._cmd_prev()
        elif cmd in ("д",):  # Russian 'д' = latin 'l' (like)
            self._cmd_like()
        elif cmd in ("в",):  # Russian 'в' = latin 'd' (dislike)
            self._cmd_dislike()
        elif cmd in ("к",):  # Russian 'к' = latin 'r' (repeat)
            self._cmd_repeat()
        elif cmd in ("ы",):  # Russian 'ы' = latin 's' (shuffle)
            self._cmd_shuffle()
        elif cmd in ("й",):  # Russian 'й' = latin 'q' (quit)
            self._running = False
        # Russian word commands
        elif cmd in ("волна",):
            self._cmd_wave(arg)
        elif cmd in ("лайки", "избранное"):
            self._cmd_liked(arg)
        elif cmd in ("поиск",):
            self._cmd_search(arg)
        elif cmd in ("плейлисты",):
            self._cmd_playlists()
        elif cmd in ("выход",):
            self._running = False
        else:
            # Try as number — play track N (if N > 4 or if play prefix was omitted)
            try:
                n = int(cmd)
                self._cmd_play(str(n))
            except ValueError:
                self._custom_view = f"[red]Неизвестная команда:[/red] {cmd}. Введите 1-4 для выбора категории или 'help'."

    # ── Commands ─────────────────────────────────────────────

    def _cmd_tab_num(self, tab_id: int, arg: str = "") -> None:
        """Switch category / tab directly by number 1-4."""
        if tab_id < 1 or tab_id > 4:
            self._custom_view = f"[red]Неверная категория {tab_id}. Доступны: 1-4[/red]"
            return
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
                self._custom_view = "[dim]Категория 4: Поиск. Введите: 4 <запрос> или search <запрос>[/dim]"

    def _cmd_tab(self, arg: str) -> None:
        """Switch active tab."""
        parts = arg.strip().split(None, 1)
        if not parts:
            self._custom_view = render_mini_tabs(self.active_tab)
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
            }
            tab_id = mapping.get(arg_lower, 0)

        if tab_id < 1 or tab_id > 4:
            self._custom_view = "[red]Неверная категория. Доступны: 1-4 (1:Волна, 2:Избранное, 3:Плейлисты, 4:Поиск)[/red]"
            return

        self._cmd_tab_num(tab_id, extra_arg)

    def _cmd_help(self) -> None:
        table = Table(title="Команды", border_style="dim", show_header=False, padding=(0, 2))
        table.add_column("Команда", style="bold green")
        table.add_column("Описание")
        for cmd, desc in COMMANDS_HELP.items():
            table.add_row(cmd, desc)
        self._custom_view = table

    def _cmd_liked(self, arg: str = "") -> None:
        self.active_tab = 2
        self.is_wave_mode = False
        self._show_all = (arg.strip().lower() == "all")
        tracks = self.api.get_liked_tracks(limit=100)
        self.current_tracks = tracks

    def _cmd_wave(self, arg: str = "") -> None:
        self.active_tab = 1
        self.is_wave_mode = True
        self._show_all = (arg.strip().lower() == "all")
        tracks = self.api.start_wave()
        self.current_tracks = tracks
        if tracks:
            self._play_index(0)

    def _cmd_play(self, arg: str) -> None:
        clean_arg = arg.strip()
        if not clean_arg:
            if self.player and self.player.state.current_track and not self.player.state.is_playing:
                self.player.resume()
                self.set_notification("[PLAY] Воспроизведение")
            elif self.current_tracks:
                self._play_index(0)
            else:
                self._custom_view = "[dim]Использование: play <N> или введите номер трека.[/dim]"
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
            self._custom_view = "[yellow]Треки не загружены. Попробуйте '1' (Волна) или 'search <запрос>'.[/yellow]"
            return
        if idx < 0 or idx >= len(self.current_tracks):
            self._custom_view = f"[red]Неверный номер трека. Диапазон: 1-{len(self.current_tracks)}[/red]"
            return

        track = self.current_tracks[idx]

        # Wave feedback
        if self.is_wave_mode and self.api.radio_session:
            self.api.radio_session.feedback_track_started(track)

        ok = self.player.set_queue(self.current_tracks, start_index=idx)
        if not ok:
            self._custom_view = f"[red]Не удалось запустить: {track.title}[/red]"

    def _cmd_search(self, query: str) -> None:
        q = query.strip()
        if not q:
            self._custom_view = "[dim]Использование: search <запрос>[/dim]"
            return
        self.active_tab = 4
        self._last_search_query = q
        self.is_wave_mode = False
        self._show_all = False
        tracks = self.api.search(q, limit=30)
        self.current_tracks = tracks
        if not tracks:
            self._custom_view = f"[yellow]Ничего не найдено по запросу '{q}'.[/yellow]"

    def _cmd_playlists(self) -> None:
        self.active_tab = 3
        playlists = self.api.get_playlists()
        self.cached_playlists = playlists
        self.current_tracks = []
        self._active_playlist_title = ""

    def _cmd_open(self, arg: str) -> None:
        if not arg:
            self._custom_view = "[dim]Использование: open <номер>[/dim]"
            return
        parts = arg.strip().split()
        try:
            n = int(parts[0])
        except ValueError:
            self._custom_view = "[red]Использование: open <номер>[/red]"
            return

        if not self.cached_playlists:
            playlists = self.api.get_playlists()
            self.cached_playlists = playlists
            if not playlists:
                self._custom_view = "[yellow]Плейлисты не найдены.[/yellow]"
                return

        if n < 1 or n > len(self.cached_playlists):
            self._custom_view = f"[red]Неверный номер плейлиста. Диапазон: 1-{len(self.cached_playlists)}[/red]"
            return

        show_all = len(parts) > 1 and parts[1].lower() == "all"
        pl = self.cached_playlists[n - 1]
        name = pl.title or "Playlist"
        self.active_tab = 3
        self._active_playlist_title = name
        self._show_all = show_all
        tracks = self.api.get_playlist_tracks(pl, limit=100)
        self.current_tracks = tracks
        self.is_wave_mode = False

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
                self.set_notification(f">> {t.artists} - {t.title}")
            self._wave_autoload()
        else:
            self.set_notification("Конец треков")

    def _cmd_prev(self) -> None:
        if not self.player:
            return
        ok = self.player.prev_track()
        if ok:
            t = self.player.state.current_track
            if t:
                self.set_notification(f"<< {t.artists} - {t.title}")

    def _cmd_pause(self) -> None:
        if not self.player:
            return
        self.player.toggle_pause()
        if self.player.state.is_playing:
            self.set_notification("[PLAY] Воспроизведение")
        else:
            self.set_notification("[PAUSE] Пауза")

    def _cmd_stop(self) -> None:
        if self.player:
            self.player.stop()
            self.set_notification("Остановлено")

    def _cmd_seek(self, arg: str) -> None:
        if not self.player or not self.player.state.current_track or not self.player.state.is_playing:
            self.set_notification("Ничего не играет")
            return
        clean_arg = arg.strip()
        if not clean_arg:
            self.set_notification("Использование: seek +10, seek -5")
            return
        try:
            sec = float(clean_arg)
            self.player.seek(sec)
            time.sleep(0.15)
            self.set_notification(f"Позиция: {self.player.state.position_str}")
        except ValueError:
            self.set_notification("Использование: seek +10, seek -5")
        except Exception as e:
            self.set_notification(f"Ошибка перемотки: {e}")

    def _cmd_vol(self, arg: str) -> None:
        if not self.player:
            return
        if not arg:
            self.set_notification(f"Громкость: {self.player.state.volume}%")
            return
        try:
            arg = arg.strip()
            if arg.startswith("+") or arg.startswith("-"):
                delta = int(arg)
                self.player.set_volume(self.player.state.volume + delta)
            else:
                self.player.set_volume(int(arg))
            self.set_notification(f"🔊 {self.player.state.volume}%")
        except ValueError:
            self.set_notification("Использование: vol 50, vol +10, vol -5")

    def _cmd_repeat(self) -> None:
        if self.player:
            self.player.toggle_repeat()
            self.set_notification(f"Повтор: {self.player.state.repeat}")

    def _cmd_shuffle(self) -> None:
        if self.player:
            self.player.toggle_shuffle()
            s = "вкл" if self.player.state.shuffle else "выкл"
            self.set_notification(f"Перемешивание: {s}")

    def _cmd_like(self) -> None:
        if not self.player or not self.player.state.current_track:
            self.set_notification("Ничего не играет")
            return
        t = self.player.state.current_track
        if self.api.like_track(t):
            self.set_notification(f"[+] Лайк: {t.title}")
        else:
            self.set_notification("Ошибка при установке лайка")

    def _cmd_dislike(self) -> None:
        if not self.player or not self.player.state.current_track:
            self.set_notification("Ничего не играет")
            return
        t = self.player.state.current_track
        if self.api.dislike_track(t):
            self.set_notification(f"[-] Дизлайк: {t.title}")
            if self.is_wave_mode:
                self._cmd_next()
        else:
            self.set_notification("Ошибка при установке дизлайка")

    def _cmd_now(self) -> None:
        if self.player:
            self._custom_view = render_now_card(self.player, self.active_tab, compact=True)

    def _cmd_auth(self, arg: str = "") -> None:
        """Handle updating token via browser or direct input."""
        token = arg.strip()
        if token:
            if self.api.login(token):
                self.config.token = token
                self.config.save()
                console.print(f"[green][OK] Авторизован как: {self.api.username}[/green]")
            else:
                console.print("[red][ERROR] Неверный токен.[/red]")
            return

        console.print("[dim]Запуск автоматической авторизации в браузере...[/dim]")
        if run_browser_device_auth(self.config, auto_exit=False):
            self.api.login()
            self._clear_view(redraw_content=True)
            self.set_notification(f"[OK] Авторизован как: {self.api.username}")

    def _cmd_status(self) -> None:
        plus = "Активен" if self.api.has_plus else "Не активен"
        vol = f"{self.player.state.volume}%" if self.player else "N/A"
        rep = self.player.state.repeat if self.player else "N/A"
        shuf = ("вкл" if self.player.state.shuffle else "выкл") if self.player else "N/A"
        txt = (
            f"Пользователь:  [bold]{self.api.username}[/bold]\n"
            f"Плюс:          {plus}\n"
            f"Громкость:     {vol}\n"
            f"Повтор:        {rep}\n"
            f"Перемешивание: {shuf}"
        )
        self._custom_view = Panel(txt, title="Статус", border_style="cyan", padding=(0, 2))

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
            self.set_notification(f">> {t.artists} - {t.title}")
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
        console.print("[dim]Выход.[/dim]")

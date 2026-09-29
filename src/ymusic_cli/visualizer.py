"""ASCII visualizer, animated banners, and tab styling for YMusic CLI.

Strict, minimalist terminal design with no emojis, compatible with both
Linux and Windows terminals.
"""

from __future__ import annotations

import math
import os
import random
import sys
import time
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from ymusic_cli.player import Player
    from ymusic_cli.api import YMusicAPI


BANNER_LOGO = """
  ██╗   ██╗███╗   ███╗██╗   ██╗███████╗██╗ ██████╗ 
  ╚██╗ ██╔╝████╗ ████║██║   ██║██╔════╝██║██╔════╝ 
   ╚████╔╝ ██╔████╔██║██║   ██║███████╗██║██║      
    ╚██╔╝  ██║╚██╔╝██║██║   ██║╚════██║██║██║      
     ██║   ██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗ 
     ╚═╝   ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝ 
"""

TABS = [
    (1, "Волна", "wave"),
    (2, "Лайки", "liked"),
    (3, "Плейлисты", "playlists"),
    (4, "Поиск", "search"),
    (5, "Очередь", "queue"),
    (6, "Текст", "lyrics"),
]

CASSETTE_REELS = ["(o)", "(*)", "(@)", "(*)"]
EQUALIZER_PULSES = [
    " ▂▃▄▅▆▇█",
    "▂▃▄▅▆▇█▇",
    "▃▄▅▆▇█▇▆",
    "▄▅▆▇█▇▆▅",
    "▅▆▇█▇▆▅▄",
    "▆▇█▆▅▄▃",
    "▇█▇▆▅▄▃▂",
    "█▇▆▅▄▃▂ ",
]


def render_banner(username: str = "", has_plus: bool = True, quality: str = "320k") -> Panel:
    """Render minimalist retro banner with user stats (strictly emoji-free)."""
    logo = Text(BANNER_LOGO, style="bold cyan")
    plus_badge = "[bold green][Plus: Active][/bold green]" if has_plus else "[bold red][Plus: Inactive][/bold red]"
    user_badge = f"[bold white]User: {username}[/bold white]" if username else ""
    hq_badge = f"[bold magenta]HQ {quality}[/bold magenta]"

    info_line = Text.from_markup(f"  {user_badge}   {plus_badge}   {hq_badge}   [dim]v0.2.0[/dim]")

    content = Group(logo, info_line)
    return Panel(
        content,
        border_style="cyan",
        title="[bold yellow]YANDEX MUSIC CLI[/bold yellow]",
        subtitle="[dim]Категории: [1]Волна  [2]Лайки  [3]Плейлисты  [4]Поиск  [5]Очередь  [6]Текст | 'vis' Visualizer[/dim]",
        padding=(0, 2),
    )


def render_tabs(active_tab: int = 1) -> Text:
    """Render top navigation bar with category tabs (strictly emoji-free)."""
    bar = Text()
    bar.append(" ")
    for tab_id, name, _ in TABS:
        if tab_id == active_tab:
            bar.append(f"[{tab_id}] {name} ", style="bold black on cyan")
        else:
            bar.append(f"[{tab_id}]", style="bold cyan")
            bar.append(f" {name} ", style="dim")
    return bar


def render_mini_equalizer(is_playing: bool = True, frame: int = 0) -> str:
    """Render compact pulsing equalizer string."""
    if not is_playing:
        return " ▂    ▂ "
    idx = frame % len(EQUALIZER_PULSES)
    return EQUALIZER_PULSES[idx]


def render_cassette(is_playing: bool, frame: int) -> Text:
    """Render retro cassette ASCII art with animated reels."""
    spin = CASSETTE_REELS[frame % len(CASSETTE_REELS)] if is_playing else " (o) "
    art = Text()
    art.append("  ╔═════════════════════════════╗\n", style="dim cyan")
    art.append("  ║  [===]  ", style="dim cyan")
    art.append(f"{spin}", style="bold cyan" if is_playing else "dim")
    art.append("   ", style="dim cyan")
    art.append(f"{spin}", style="bold cyan" if is_playing else "dim")
    art.append("  [===]  ║\n", style="dim cyan")
    art.append("  ║  ┌───────────────────────┐  ║\n", style="dim cyan")
    art.append("  ╚══╧═══════════════════════╧══╝", style="dim cyan")
    return art


def render_now_card(player: Player, active_tab: int = 1, frame: int = 0) -> Panel:
    """Render rich Now Playing card with animated cassette and audio stats."""
    s = player.state
    if not s.current_track:
        return Panel(
            Text("\n  [-] Nothing currently playing.\n  Type '1' (Wave), '2' (Liked), or 'play <query>' to start.\n", style="dim"),
            title="[bold]Now Playing[/bold]",
            border_style="dim",
            padding=(0, 2),
        )

    t = s.current_track
    is_playing = s.is_playing
    status_icon = "[PLAY]" if is_playing else "[PAUSE]"
    status_style = "bold green" if is_playing else "bold yellow"

    # Progress bar
    bar_width = 18
    pct = s.progress
    filled = int(pct * bar_width)
    bar_chars = "=" * filled + "*" + "-" * max(0, bar_width - filled)

    cassette = render_cassette(is_playing, frame)
    eq = render_mini_equalizer(is_playing, frame)

    info = Text()
    info.append(f"{status_icon}  ", style=status_style)
    info.append(f"{eq}\n", style="bold green" if is_playing else "dim")
    info.append(f"{t.artists}", style="bold cyan")
    info.append(" - ", style="dim")
    info.append(f"{t.title}\n", style="bold white")
    if t.album:
        info.append(f"Album: {t.album}\n", style="dim")
    info.append(f"[{bar_chars}]  {s.position_str} / {s.duration_str}\n", style="bold")
    info.append("320k MP3", style="bold magenta")
    info.append(" | Vol: ", style="dim")
    info.append(f"{s.volume}%", style="bold")
    info.append(" | Repeat: ", style="dim")
    info.append(f"{s.repeat}", style="yellow")
    info.append(" | Shuffle: ", style="dim")
    info.append("on" if s.shuffle else "off", style="green" if s.shuffle else "dim")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column()
    grid.add_row(cassette, info)

    return Panel(
        grid,
        title="[bold cyan]Now Playing[/bold cyan]",
        subtitle=f"[dim]Queue: {s.queue_index + 1}/{len(s.queue)}[/dim]",
        border_style="green" if is_playing else "yellow",
        padding=(0, 1),
    )


def generate_spectrum_frame(t: float, is_playing: bool, num_bars: int = 32, height: int = 10) -> str:
    """Generate multi-band animated audio spectrum bars."""
    if not is_playing:
        rows = []
        for h in reversed(range(1, height + 1)):
            row = "  "
            for _ in range(num_bars):
                row += "  " if h > 1 else "[dim]--[/dim]"
            rows.append(row)
        return "\n".join(rows)

    cols = []
    for i in range(num_bars):
        freq_weight = 1.0 - (i / num_bars) * 0.4
        f1 = math.sin(t * 4.2 + i * 0.35)
        f2 = math.cos(t * 8.1 - i * 0.55)
        f3 = math.sin(t * 2.1 + i * 0.9)
        val = (f1 * 0.45 + f2 * 0.35 + f3 * 0.2 + 1.0) / 2.0
        val *= freq_weight
        val += random.uniform(-0.06, 0.06)
        bar_h = int(max(0.0, min(1.0, val)) * height)
        cols.append(bar_h)

    rows = []
    for h in reversed(range(1, height + 1)):
        row = "  "
        for c in cols:
            if c >= h:
                if h >= height - 2:
                    row += "[bold red]█ [/bold red]"
                elif h >= height - 4:
                    row += "[bold yellow]█ [/bold yellow]"
                elif h >= 3:
                    row += "[cyan]█ [/cyan]"
                else:
                    row += "[bold green]█ [/bold green]"
            elif c == h - 1:
                row += "[dim green]▄ [/dim green]"
            else:
                row += "  "
        rows.append(row)
    return "\n".join(rows)


class KeyPoller:
    """Cross-platform non-blocking single-key reader for Windows and POSIX."""

    def __init__(self) -> None:
        self.is_windows = sys.platform == "win32"
        self.old_settings = None

    def __enter__(self) -> KeyPoller:
        if not sys.stdin.isatty():
            return self
        if not self.is_windows:
            try:
                import termios
                import tty
                self.old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass
        return self

    def __exit__(self, *args) -> None:
        if not self.is_windows and self.old_settings is not None:
            try:
                import termios
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass

    def poll(self, timeout: float = 0.04) -> str | None:
        """Poll for single keypress within timeout seconds."""
        if not sys.stdin.isatty():
            time.sleep(timeout)
            return None

        if self.is_windows:
            try:
                import msvcrt
                start = time.time()
                while time.time() - start < timeout:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        try:
                            return ch.decode("utf-8")
                        except UnicodeDecodeError:
                            return str(ch)
                    time.sleep(0.01)
                return None
            except Exception:
                time.sleep(timeout)
                return None
        else:
            try:
                import select
                rlist, _, _ = select.select([sys.stdin], [], [], timeout)
                if rlist:
                    return sys.stdin.read(1)
            except Exception:
                time.sleep(timeout)
            return None


def run_visualizer(player: Player, api: YMusicAPI, console: Console) -> None:
    """Run interactive real-time ASCII audio visualizer (cross-platform, emoji-free)."""
    if not sys.stdin.isatty():
        frame = generate_spectrum_frame(1.0, player.state.is_playing)
        console.print(frame)
        return

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        with KeyPoller() as poller:
            running = True
            t0 = time.time()
            frame_count = 0

            while running:
                now = time.time()
                elapsed = now - t0
                frame_count += 1

                # Poll keyboard input non-blockingly
                ch = poller.poll(0.04)
                if ch:
                    if ch in ("q", "Q", "\x1b", "\n", "\r"):
                        break
                    elif ch == " ":
                        player.toggle_pause()
                    elif ch in ("n", "N"):
                        player.next_track()
                    elif ch in ("p", "P"):
                        player.prev_track()
                    elif ch in ("+", "="):
                        player.volume_up(5)
                    elif ch in ("-", "_"):
                        player.volume_down(5)
                    elif ch in ("l", "L"):
                        if player.state.current_track:
                            api.like_track(player.state.current_track)
                    elif ch in ("s", "S"):
                        player.toggle_shuffle()
                    elif ch in ("r", "R"):
                        player.toggle_repeat()

                # Render frame
                s = player.state
                status_text = "[PLAYING]" if s.is_playing else "[PAUSED]"
                status_color = "green" if s.is_playing else "yellow"

                try:
                    term_cols = os.get_terminal_size().columns
                except OSError:
                    term_cols = 80
                num_bars = max(16, min(40, (term_cols - 10) // 2))

                spectrum = generate_spectrum_frame(elapsed, s.is_playing, num_bars=num_bars, height=10)

                title = s.current_track.title if s.current_track else "No Track"
                artists = s.current_track.artists if s.current_track else "Unknown Artist"
                pos_str = f"{s.position_str} / {s.duration_str}"
                spin = CASSETTE_REELS[frame_count % len(CASSETTE_REELS)] if s.is_playing else "(o)"

                bar_len = max(15, min(35, term_cols - 45))
                filled = int(s.progress * bar_len)
                progress_line = "=" * filled + "*" + "-" * max(0, bar_len - filled)

                info_text = (
                    f"\n  [bold cyan]{spin} {artists}[/bold cyan] - [bold white]{title}[/bold white]\n"
                    f"  [{status_color}]{status_text}[/{status_color}]  "
                    f"[bold cyan][{progress_line}][/bold cyan]  {pos_str}   Vol: [bold]{s.volume}%[/bold]\n"
                    f"  [dim]Hotkeys: [Space] Pause  [n/p] Next/Prev  [+/-] Vol  [l] Like  [s] Shuffle  [q] Exit[/dim]"
                )

                vis_content = Group(
                    Text.from_markup(spectrum),
                    Text.from_markup(info_text),
                )

                panel = Panel(
                    vis_content,
                    title="[bold cyan]-- YMUSIC LIVE AUDIO SPECTRUM --[/bold cyan]",
                    subtitle="[dim]Press [q] or [Esc] to return to shell[/dim]",
                    border_style="cyan" if s.is_playing else "yellow",
                    padding=(0, 1),
                )

                # Clear screen and draw frame
                if sys.platform == "win32":
                    sys.stdout.write("\033[H")
                else:
                    sys.stdout.write("\033[H\033[J")
                console.print(panel)

    finally:
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()

"""Compact TUI components and now-playing status cards for YMusic CLI."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from ymusic_cli.player import Player


TAB_SPECS = [
    (1, "🌊", "Волна", "Влн", "wave"),
    (2, "❤️", "Лайки", "Лайк", "liked"),
    (3, "📁", "Плейлисты", "Плей", "playlists"),
    (4, "🔍", "Поиск", "Пск", "search"),
]

TABS = [(t[0], t[2], t[4]) for t in TAB_SPECS]


def _terminal_width(width: int | None = None) -> int:
    """Return effective terminal width."""
    if width is not None:
        return width
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def render_mini_tabs(active_tab: int = 1, width: int | None = None) -> Text:
    """Render responsive compact tab bar with emojis."""
    w = _terminal_width(width)
    bar = Text()

    for tab_id, emoji, full_name, abbr, _slug in TAB_SPECS:
        is_active = tab_id == active_tab
        style = "bold black on cyan" if is_active else "dim"

        if w < 38:
            label = f"{tab_id}{emoji} "
        elif w < 72:
            label = f"[{tab_id}]{emoji} "
        elif w < 90:
            label = f"[{tab_id}]{emoji}{abbr} "
        else:
            label = f"[{tab_id}]{emoji}{full_name} "

        bar.append(label, style=style)

    return bar


def render_tabs(active_tab: int = 1) -> Text:
    """Alias for render_mini_tabs for backwards compatibility."""
    return render_mini_tabs(active_tab)


def _format_time(seconds: float) -> str:
    """Format seconds as m:ss."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def render_mini_track_bar(player: "Player", width: int | None = None) -> Text:
    """Render compact 1-line now-playing bar adapting dynamically to terminal width."""
    w = _terminal_width(width)
    s = player.state
    bar = Text()

    if not s.current_track:
        bar.append("· ", style="dim")
        bar.append("No track", style="dim")
        return bar

    is_playing = s.is_playing
    icon = "▶" if is_playing else "⏸"
    icon_style = "bold green" if is_playing else "bold yellow"
    t = s.current_track
    artist_title = f"{t.artists} - {t.title}"
    pos = f"{s.position_str}/{s.duration_str}"
    vol = f"🔊 {s.volume}%"

    bar.append(f"{icon} ", style=icon_style)

    if w < 32:
        avail = max(6, w - 3)
        if len(artist_title) > avail:
            artist_title = artist_title[: max(1, avail - 1)] + "…"
        bar.append(artist_title, style="bold")
        return bar

    if w < 48:
        avail = max(6, w - len(vol) - 4)
        if len(artist_title) > avail:
            artist_title = artist_title[: max(1, avail - 1)] + "…"
        bar.append(artist_title, style="bold")
        bar.append(f" {vol}", style="dim")
        return bar

    if w < 70:
        avail = max(6, w - len(pos) - len(vol) - 6)
        if len(artist_title) > avail:
            artist_title = artist_title[: max(1, avail - 1)] + "…"
        bar.append(artist_title, style="bold")
        bar.append(f" · {vol} {pos}", style="dim")
        return bar

    # Wide: w >= 70
    progress_w = min(12, max(6, (w - 55) // 3))
    pct = s.progress
    filled = int(pct * progress_w)
    bar_chars = "=" * filled + "*" + "-" * max(0, progress_w - filled)

    extra_len = len(pos) + len(vol) + progress_w + 10
    avail = max(10, w - extra_len)
    if len(artist_title) > avail:
        artist_title = artist_title[: max(1, avail - 1)] + "…"

    bar.append(artist_title, style="bold")
    bar.append(f" · {vol} [{bar_chars}] {pos}", style="dim")
    return bar


def render_mini_header(player: "Player", active_tab: int = 1, width: int | None = None) -> Group:
    """Combine mini tabs and mini track bar into a clean 2-line header."""
    tabs = render_mini_tabs(active_tab, width=width)
    track = render_mini_track_bar(player, width=width)
    return Group(tabs, track)


def render_now_card(player: "Player", active_tab: int = 1, frame: int = 0, compact: bool = True) -> Panel:
    """Render sleek, compact Now Playing status card."""
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
    status_icon = "▶" if is_playing else "⏸"
    status_style = "bold green" if is_playing else "bold yellow"

    bar_width = 20
    pct = s.progress
    filled = int(pct * bar_width)
    bar_chars = "=" * filled + "*" + "-" * max(0, bar_width - filled)

    info = Text()
    info.append(f"{status_icon} ", style=status_style)
    info.append(f"{t.artists}", style="bold cyan")
    info.append(" - ", style="dim")
    info.append(f"{t.title}\n", style="bold white")
    if t.album:
        info.append(f"Album: {t.album}\n", style="dim")
    info.append(f"[{bar_chars}]  {s.position_str} / {s.duration_str}", style="bold")
    info.append("  320k MP3", style="bold magenta")
    info.append(f"  🔊 {s.volume}%\n", style="bold")
    info.append(f"Repeat: {s.repeat} | Shuffle: {'on' if s.shuffle else 'off'}", style="dim")

    return Panel(
        info,
        title="[bold cyan]Now Playing[/bold cyan]",
        border_style="green" if is_playing else "yellow",
        padding=(0, 1),
    )

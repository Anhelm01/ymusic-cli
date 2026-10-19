"""Tests for adaptive TUI features, window resizing, and self-cleaning."""

from unittest.mock import MagicMock
from rich.console import Console

from ymusic_cli.api import TrackInfo
from ymusic_cli.config import Config
from ymusic_cli.player import PlayerState
from ymusic_cli.cli import print_track_table, YMusicShell
from ymusic_cli.visualizer import render_mini_tabs, render_mini_track_bar, render_mini_header


def test_responsive_track_table_widths():
    tracks = [
        TrackInfo(id=i, title=f"Track Title {i}", artists=f"Artist {i}", album=f"Album {i}", duration_ms=180000)
        for i in range(1, 10)
    ]

    # Narrow width (< 50 cols)
    c_narrow = Console(record=True, width=45)
    print_track_table(tracks, "My Wave", playing_id="1", console_out=c_narrow)
    out_narrow = c_narrow.export_text()
    assert "Track Title 1" in out_narrow
    # In narrow mode, Album and Time columns are omitted
    assert "Album 1" not in out_narrow

    # Medium width (60 cols)
    c_med = Console(record=True, width=60)
    print_track_table(tracks, "My Wave", playing_id="1", console_out=c_med)
    out_med = c_med.export_text()
    assert "Track Title" in out_med
    assert "3:00" in out_med  # Time included
    assert "Album 1" not in out_med  # Album omitted

    # Wide width (85 cols)
    c_wide = Console(record=True, width=85)
    print_track_table(tracks, "My Wave", playing_id="1", console_out=c_wide)
    out_wide = c_wide.export_text()
    assert "Track Title 1" in out_wide
    assert "Album 1" in out_wide  # Album included
    assert "3:00" in out_wide


def test_responsive_track_bar_breakpoints():
    dummy = MagicMock()
    t = TrackInfo(id=1, title="Very Long Song Title That Might Wrap", artists="Popular Artist Group", album="A", duration_ms=210000)
    s = PlayerState()
    s.current_track = t
    s.is_playing = True
    s.position = 45.0
    s.duration = 210.0
    s.volume = 90
    dummy.state = s

    # Micro width (< 32)
    b_micro = render_mini_track_bar(dummy, width=28)
    assert len(b_micro.plain) <= 28

    # Narrow width (40)
    b_narrow = render_mini_track_bar(dummy, width=40)
    assert "🔊 90%" in b_narrow.plain
    assert len(b_narrow.plain) <= 40

    # Medium width (60)
    b_med = render_mini_track_bar(dummy, width=60)
    assert "0:45/3:30" in b_med.plain
    assert "🔊 90%" in b_med.plain

    # Wide width (90)
    b_wide = render_mini_track_bar(dummy, width=90)
    assert "0:45/3:30" in b_wide.plain
    assert "🔊 90%" in b_wide.plain
    assert "[" in b_wide.plain  # progress bar included


def test_bottom_toolbar_responsiveness():
    dummy = MagicMock()
    t = TrackInfo(id=1, title="Song", artists="Artist", album="A", duration_ms=200000)
    s = PlayerState()
    s.current_track = t
    s.is_playing = True
    s.position = 10.0
    s.duration = 200.0
    s.volume = 80
    dummy.state = s

    api = MagicMock()
    shell = YMusicShell(Config(), api)
    shell.player = dummy
    shell.active_tab = 1

    bar = shell._bottom_toolbar()
    assert "Artist - Song" in bar
    assert "80%" in bar


def test_ctrl_l_clean_redraw():
    api = MagicMock()
    shell = YMusicShell(Config(), api)
    dummy = MagicMock()
    dummy.state = PlayerState()
    shell.player = dummy

    # Should not throw exception when redrawing
    shell._clear_view(redraw_content=True)
    assert shell._kb is not None


def test_four_tabs_only():
    api = MagicMock()
    shell = YMusicShell(Config(), api)
    dummy = MagicMock()
    dummy.state = PlayerState()
    shell.player = dummy

    for i in (1, 2, 3, 4):
        shell._cmd_tab(str(i))
        assert shell.active_tab == i

    # Tab 5 or 6 should not be allowed
    shell._cmd_tab("5")
    assert shell._custom_view is not None
    assert "Неверная категория" in str(shell._custom_view)

    shell._cmd_tab("6")
    assert shell._custom_view is not None
    assert "Неверная категория" in str(shell._custom_view)


def test_commands_set_custom_view_and_notifications():
    api = MagicMock()
    shell = YMusicShell(Config(), api)
    dummy = MagicMock()
    dummy.state = PlayerState()
    dummy.state.current_track = TrackInfo(id=1, title="Song", artists="Artist", album="A", duration_ms=200000)
    shell.player = dummy

    # help command sets custom view
    shell._cmd_help()
    assert shell._custom_view is not None

    # status command sets custom view
    shell._cmd_status()
    assert shell._custom_view is not None

    # pause sets notification
    shell._cmd_pause()
    assert shell._notification != ""

    # vol sets notification
    shell._cmd_vol("+5")
    assert shell._notification != ""


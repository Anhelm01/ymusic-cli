"""Automated tests for mini tabs, status cards, and shell UI."""

from unittest.mock import MagicMock
from rich.console import Console

from ymusic_cli.visualizer import (
    render_tabs,
    render_mini_tabs,
    render_mini_track_bar,
    render_mini_header,
    render_now_card,
    TABS,
    TAB_SPECS,
)
from ymusic_cli.api import TrackInfo
from ymusic_cli.config import Config
from ymusic_cli.player import PlayerState
from ymusic_cli.cli import YMusicShell


def test_tabs():
    assert len(TABS) == 4
    for i in range(1, 5):
        tb = render_tabs(i)
        assert f"[{i}]" in tb.plain


def test_now_card_idle():
    c = Console(record=True)
    dummy = MagicMock()
    dummy.state = PlayerState()
    card = render_now_card(dummy)
    c.print(card)
    assert "Nothing currently playing" in c.export_text()


def test_now_card_playing():
    c = Console(record=True, width=80)
    dummy = MagicMock()
    t = TrackInfo(id=999, title="Cyberpunk 2077", artists="Hyper", album="OST", duration_ms=215000)
    s = PlayerState()
    s.current_track = t
    s.is_playing = True
    s.position = 45.0
    s.duration = 215.0
    s.volume = 85
    s.repeat = "off"
    s.shuffle = False
    s.queue = [t]
    s.queue_index = 0
    dummy.state = s

    card = render_now_card(dummy)
    c.print(card)
    out = c.export_text()
    assert "Hyper" in out
    assert "Cyberpunk 2077" in out
    assert "320k MP3" in out
    assert "0:45 / 3:35" in out


def test_shell_tabs_and_toolbar():
    dummy = MagicMock()
    t = TrackInfo(id=999, title="Cyberpunk 2077", artists="Hyper", album="OST", duration_ms=215000)
    s = PlayerState()
    s.current_track = t
    s.is_playing = True
    s.position = 45.0
    s.duration = 215.0
    s.volume = 85
    dummy.state = s

    api = MagicMock()
    shell = YMusicShell(Config(), api)
    shell.player = dummy

    # Switch tab by id
    shell._cmd_tab("3")
    assert shell.active_tab == 3

    # Switch tab by name
    shell._cmd_tab("search")
    assert shell.active_tab == 4

    # Bottom toolbar
    bar = shell._bottom_toolbar()
    assert "Hyper - Cyberpunk 2077" in bar
    assert "4: Поиск" in bar

    # Test direct digit switching 1-4 via _dispatch
    for num in range(1, 5):
        shell._dispatch(str(num), "")
        assert shell.active_tab == num


def test_mini_ui():
    assert len(TAB_SPECS) == 4
    # Test responsive tabs at various widths
    t_narrow = render_mini_tabs(1, width=30)
    assert "1🌊" in t_narrow.plain
    t_mid = render_mini_tabs(2, width=50)
    assert "[2]❤️" in t_mid.plain
    t_wide = render_mini_tabs(3, width=100)
    assert "[3]📁Плейлисты" in t_wide.plain

    # Test mini track bar
    dummy = MagicMock()
    dummy.state = PlayerState()
    bar_idle = render_mini_track_bar(dummy, width=80)
    assert "No track" in bar_idle.plain

    t = TrackInfo(id=101, title="Track Title", artists="Artist Name", album="Alb", duration_ms=180000)
    dummy.state.current_track = t
    dummy.state.is_playing = True
    dummy.state.position = 30.0
    dummy.state.duration = 180.0
    dummy.state.volume = 75
    bar_playing = render_mini_track_bar(dummy, width=80)
    assert "▶" in bar_playing.plain
    assert "Artist Name" in bar_playing.plain
    assert "75%" in bar_playing.plain

    # Test mini header
    header = render_mini_header(dummy, active_tab=1, width=80)
    assert header is not None


if __name__ == "__main__":
    test_tabs()
    test_now_card_idle()
    test_now_card_playing()
    test_shell_tabs_and_toolbar()
    test_mini_ui()
    print("ALL TESTS PASSED SUCCESSFULLY!")

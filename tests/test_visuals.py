"""Automated tests for visualizer, tabs, banners, cassette art, and lyrics."""

from unittest.mock import MagicMock
from rich.console import Console

from ymusic_cli.visualizer import (
    render_banner,
    render_tabs,
    render_mini_equalizer,
    render_cassette,
    render_now_card,
    generate_spectrum_frame,
    TABS,
)
from ymusic_cli.api import TrackInfo, YMusicAPI
from ymusic_cli.config import Config
from ymusic_cli.player import PlayerState
from ymusic_cli.cli import YMusicShell


def test_banner():
    c = Console(record=True)
    b = render_banner("anhelm", True, "320k")
    c.print(b)
    output = c.export_text()
    assert "anhelm" in output
    assert "Plus: Active" in output
    assert "HQ 320k" in output


def test_tabs():
    assert len(TABS) == 6
    for i in range(1, 7):
        tb = render_tabs(i)
        assert f"[{i}]" in tb.plain


def test_mini_equalizer():
    eq_play = render_mini_equalizer(True, 2)
    eq_pause = render_mini_equalizer(False, 0)
    assert eq_play != eq_pause


def test_cassette():
    c_play = render_cassette(True, 1)
    c_pause = render_cassette(False, 0)
    assert "╔════" in c_play.plain
    assert "╚══╧" in c_pause.plain


def test_spectrum():
    spec_play = generate_spectrum_frame(1.0, True, 16, 6)
    lines_play = spec_play.splitlines()
    assert len(lines_play) == 6

    spec_pause = generate_spectrum_frame(1.0, False, 16, 6)
    lines_pause = spec_pause.splitlines()
    assert len(lines_pause) == 6


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


def test_lyrics_api():
    raw_track = MagicMock()
    raw_track.get_supplement.return_value.lyrics.full_lyrics = "Line 1\nLine 2\nLine 3"
    t = TrackInfo(id=1, title="T", artists="A", album="Alb", duration_ms=1000, _raw=raw_track)
    api = YMusicAPI(Config())
    lyrics = api.get_track_lyrics(t)
    assert lyrics == "Line 1\nLine 2\nLine 3"


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
    api.get_track_lyrics.return_value = "Test song lyrics\nVerse 1"
    shell = YMusicShell(Config(), api)
    shell.player = dummy

    # Switch tab by id
    shell._cmd_tab("3")
    assert shell.active_tab == 3

    # Switch tab by name
    shell._cmd_tab("lyrics")
    assert shell.active_tab == 6

    # Bottom toolbar
    bar = shell._bottom_toolbar()
    assert "Hyper - Cyberpunk 2077" in bar
    assert "6: Текст" in bar

    # Test direct digit switching 1-6 via _dispatch
    for num in range(1, 7):
        shell._dispatch(str(num), "")
        assert shell.active_tab == num


if __name__ == "__main__":
    test_banner()
    test_tabs()
    test_mini_equalizer()
    test_cassette()
    test_spectrum()
    test_now_card_idle()
    test_now_card_playing()
    test_lyrics_api()
    test_shell_tabs_and_toolbar()
    print("ALL TESTS PASSED SUCCESSFULLY!")

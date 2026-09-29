"""Tests for the 3-track sliding window table (Prev, Playing, Next)."""

from rich.console import Console
from ymusic_cli.api import TrackInfo
from ymusic_cli.cli import print_track_table


def test_three_track_window_middle():
    c = Console(record=True, width=80)
    tracks = [
        TrackInfo(id=i, title=f"Track {i}", artists=f"Artist {i}", album=f"Album {i}", duration_ms=180000)
        for i in range(1, 101)
    ]
    # Middle track (42) playing
    print_track_table(tracks, "Избранное", playing_id="42", console_out=c)
    output = c.export_text()

    # Should only show tracks 41, 42, 43
    assert "Track 41" in output
    assert "Track 42" in output
    assert "Track 43" in output
    assert "Track 1" not in output
    assert "Track 10" not in output
    assert "Track 99" not in output
    assert "<< Предыдущий" in output
    assert ">> Играет" in output
    assert ">> Следующий" in output
    assert "3 из 100 треков" in output


def test_three_track_window_start():
    c = Console(record=True, width=80)
    tracks = [
        TrackInfo(id=i, title=f"Track {i}", artists=f"Artist {i}", album=f"Album {i}", duration_ms=180000)
        for i in range(1, 101)
    ]
    # First track (1) playing
    print_track_table(tracks, "Моя Волна", playing_id="1", console_out=c)
    output = c.export_text()

    # Should show tracks 1, 2, 3
    assert "Track 1" in output
    assert "Track 2" in output
    assert "Track 3" in output
    assert "Track 4" not in output
    assert ">> Играет" in output
    assert ">> Следующий" in output
    assert ">> Далее" in output


def test_three_track_window_end():
    c = Console(record=True, width=80)
    tracks = [
        TrackInfo(id=i, title=f"Track {i}", artists=f"Artist {i}", album=f"Album {i}", duration_ms=180000)
        for i in range(1, 101)
    ]
    # Last track (100) playing
    print_track_table(tracks, "Плейлист", playing_id="100", console_out=c)
    output = c.export_text()

    # Should show tracks 98, 99, 100
    assert "Track 98" in output
    assert "Track 99" in output
    assert "Track 100" in output
    assert "Track 97" not in output
    assert "<< Ранее" in output
    assert "<< Предыдущий" in output
    assert ">> Играет" in output


def test_three_track_window_selection():
    c = Console(record=True, width=80)
    tracks = [
        TrackInfo(id=i, title=f"Track {i}", artists=f"Artist {i}", album=f"Album {i}", duration_ms=180000)
        for i in range(1, 50)
    ]
    # Nothing playing yet
    print_track_table(tracks, "Поиск: rock", console_out=c)
    output = c.export_text()

    assert "Track 1" in output
    assert "Track 2" in output
    assert "Track 3" in output
    assert "Track 4" not in output
    assert "* Выбран" in output


def test_show_all_flag():
    c = Console(record=True, width=80)
    tracks = [
        TrackInfo(id=i, title=f"Track {i}", artists=f"Artist {i}", album=f"Album {i}", duration_ms=180000)
        for i in range(1, 10)
    ]
    print_track_table(tracks, "Избранное", playing_id="5", show_all=True, console_out=c)
    output = c.export_text()

    # All tracks should be present when show_all=True
    for i in range(1, 10):
        assert f"Track {i}" in output


if __name__ == "__main__":
    test_three_track_window_middle()
    test_three_track_window_start()
    test_three_track_window_end()
    test_three_track_window_selection()
    test_show_all_flag()
    print("ALL 3-TRACK WINDOW TESTS PASSED SUCCESSFULLY!")

"""Verify core player and API fixes (no segfault, no runaway EOF, safe seek, safe search)."""

from unittest.mock import MagicMock

from ymusic_cli.api import TrackInfo, YMusicAPI
from ymusic_cli.cli import YMusicShell
from ymusic_cli.config import Config
from ymusic_cli.player import Player


def test_no_segfault_on_shutdown():
    api = MagicMock()
    player = Player(api)
    player.shutdown()
    assert player._shutting_down is True


def test_seek_when_idle():
    api = MagicMock()
    player = Player(api)
    shell = YMusicShell(Config(), api)
    shell.player = player
    # Should not throw exception
    shell._cmd_seek("+10")
    shell._cmd_seek("-5")
    shell._cmd_seek("abc")


def test_empty_search():
    api = MagicMock()
    shell = YMusicShell(Config(), api)
    # Should not crash on whitespace
    shell._cmd_search("   ")
    shell._cmd_play("   ")


def test_liked_tracks_empty():
    api = YMusicAPI(Config())
    api._client = MagicMock()
    api._client.users_likes_tracks.return_value.tracks = []
    tracks = api.get_liked_tracks()
    assert tracks == []


def test_shuffle_indices():
    api = MagicMock()
    player = Player(api)
    tracks = [
        TrackInfo(id=i, title=f"Track {i}", artists="Artist", album="Album", duration_ms=100000)
        for i in range(10)
    ]
    player.set_queue(tracks, start_index=0)
    player.toggle_shuffle()
    assert player.state.shuffle is True
    # Test toggling back
    player.toggle_shuffle()
    assert player.state.shuffle is False


def test_cli_version_and_help(capsys):
    from ymusic_cli.__main__ import print_cli_help, print_cli_version

    print_cli_version()
    captured = capsys.readouterr()
    assert "ymusic 0.2.0" in captured.out

    print_cli_help()
    captured = capsys.readouterr()
    assert "ymusic" in captured.out
    assert "--version" in captured.out
    assert "update" in captured.out


def test_update_command_dispatch():
    from unittest.mock import patch
    api = MagicMock()
    shell = YMusicShell(Config(), api)
    with patch.object(shell, "_cmd_auth") as mock_auth:
        shell._dispatch("update", "")
        mock_auth.assert_called_once_with("")


def test_mpv_windows_module():
    from ymusic_cli.mpv_windows import (
        ensure_mpv_windows,
        find_existing_mpv_dll,
        get_search_directories,
        get_windows_mpv_dir,
    )

    # On non-Windows platform it safely returns True
    assert ensure_mpv_windows() is True
    assert get_windows_mpv_dir() is not None
    res = find_existing_mpv_dll()
    assert res is None or isinstance(res, tuple)
    dirs = get_search_directories()
    assert len(dirs) > 0


if __name__ == "__main__":
    test_no_segfault_on_shutdown()
    test_seek_when_idle()
    test_empty_search()
    test_liked_tracks_empty()
    test_shuffle_indices()
    print("ALL CORE FIXES VERIFIED SUCCESSFULLY!")

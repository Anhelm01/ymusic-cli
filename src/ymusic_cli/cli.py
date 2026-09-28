"""Command-line interface (CLI) for YMusic."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time

from ymusic_cli.config import Config
from ymusic_cli.api import YMusicAPI, TrackInfo
from ymusic_cli.player import Player, check_mpv_available


def cmd_status(cfg: Config, api: YMusicAPI) -> None:
    """Print current account and configuration status."""
    print("── YMusic CLI Status ──")
    if not cfg.is_authenticated:
        print("Status:       Not authenticated")
        print("Run:          ymusic auth")
        return

    ok = api.login()
    if not ok:
        print("Status:       Token invalid or expired")
        return

    print(f"User:         {api.username}")
    plus_str = "Active ✓" if api.has_plus else "Inactive ✗ (playback limited)"
    print(f"Yandex Plus:  {plus_str}")
    print(f"Volume:       {cfg.volume}%")
    print(f"Quality:      {cfg.quality}")
    print(f"Config path:  ~/.config/ymusic-cli/config.json")


def cmd_liked(cfg: Config, api: YMusicAPI, limit: int = 100) -> None:
    """Output liked tracks to stdout (ideal for unix pipelines like fzf or grep)."""
    if not api.login():
        print("Error: Not authenticated. Run `ymusic auth` first.", file=sys.stderr)
        sys.exit(1)

    tracks = api.get_liked_tracks(limit=limit)
    for i, t in enumerate(tracks):
        print(f"{i+1:>3}\t{t.artists}\t{t.title}\t{t.duration_str}\t{t.album}")


def cmd_fzf(cfg: Config, api: YMusicAPI) -> None:
    """Select and play a liked track interactively via fzf."""
    if not shutil.which("fzf"):
        print("Error: fzf is not installed. Install with `sudo pacman -S fzf`", file=sys.stderr)
        sys.exit(1)

    if not api.login():
        print("Error: Not authenticated. Run `ymusic auth` first.", file=sys.stderr)
        sys.exit(1)

    print("Fetching liked tracks...", file=sys.stderr)
    tracks = api.get_liked_tracks(limit=150)
    lines = [f"{t.artists} — {t.title} [{t.duration_str}] | {t.album}" for t in tracks]

    proc = subprocess.Popen(
        ["fzf", "--prompt=▶ Select track: ", "--height=40%", "--layout=reverse", "--border"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    selected_line, _ = proc.communicate(input="\n".join(lines))
    if not selected_line or proc.returncode != 0:
        return

    selected_line = selected_line.strip()
    idx = -1
    for i, line in enumerate(lines):
        if line == selected_line:
            idx = i
            break

    if idx >= 0:
        _play_cli_stream(cfg, api, tracks, start_index=idx)


def cmd_play(cfg: Config, api: YMusicAPI, query: str) -> None:
    """Search for tracks and play in the terminal."""
    if not api.login():
        print("Error: Not authenticated. Run `ymusic auth` first.", file=sys.stderr)
        sys.exit(1)

    print(f"Searching for '{query}'...")
    tracks = api.search(query, limit=20)
    if not tracks:
        print(f"No tracks found matching '{query}'.")
        return

    print(f"Found {len(tracks)} tracks. Starting playback:")
    _play_cli_stream(cfg, api, tracks, start_index=0)


def cmd_wave(cfg: Config, api: YMusicAPI) -> None:
    """Stream My Wave (Моя Волна) directly in the terminal."""
    if not api.login():
        print("Error: Not authenticated. Run `ymusic auth` first.", file=sys.stderr)
        sys.exit(1)

    print("Starting 'Моя Волна' (My Wave)...")
    tracks = api.start_wave()
    if not tracks:
        print("Could not start My Wave.")
        return

    _play_cli_stream(cfg, api, tracks, start_index=0, is_wave=True)


def _play_cli_stream(
    cfg: Config,
    api: YMusicAPI,
    tracks: list[TrackInfo],
    start_index: int = 0,
    is_wave: bool = False,
) -> None:
    """Interactive CLI playback loop with hotkeys."""
    if not check_mpv_available():
        print("Error: mpv is required for playback.", file=sys.stderr)
        sys.exit(1)

    player = Player(api, volume=cfg.volume)
    player.set_queue(tracks, start_index=start_index)

    print("\n" + "═" * 60)
    print("Controls: [Space/c] Pause  [n] Next  [p] Prev  [+/-] Vol  [l] Like  [q] Quit")
    print("═" * 60 + "\n")

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def on_end():
        if is_wave and api.radio_session:
            cur = player.state.current_track
            if cur:
                api.radio_session.feedback_track_finished(cur, player.state.duration)
            idx = player.state.queue_index
            if idx >= len(player.state.queue) - 2:
                more = api.get_more_wave_tracks()
                if more:
                    player.state.queue.extend(more)
        player.next_track()

    player.on_end(on_end)

    try:
        tty.setcbreak(fd)
        last_track_id = None

        while True:
            cur = player.state.current_track
            if cur and str(cur.id) != last_track_id:
                last_track_id = str(cur.id)
                if is_wave and api.radio_session:
                    api.radio_session.feedback_track_started(cur)

            status = "▶ PLAYING" if player.state.is_playing else "❚❚ PAUSED "
            track_name = f"{cur.artists} - {cur.title}" if cur else "None"
            time_info = f"{player.state.position_str}/{player.state.duration_str}"
            vol_info = f"vol: {player.state.volume}%"

            # Carriage return single-line update
            sys.stdout.write(f"\r\033[K[{status}] {time_info} │ {track_name} │ {vol_info}")
            sys.stdout.flush()

            # Non-blocking key check (timeout 0.3s)
            rlist, _, _ = select.select([sys.stdin], [], [], 0.3)
            if rlist:
                ch = sys.stdin.read(1)
                if ch in ("q", "\x03", "\x1b"):  # q, Ctrl+C, Esc
                    break
                elif ch in (" ", "c"):
                    player.toggle_pause()
                elif ch in ("n", "b"):
                    if is_wave and api.radio_session and cur:
                        api.radio_session.feedback_skip(cur, player.state.position)
                    player.next_track()
                elif ch in ("p", "z"):
                    player.prev_track()
                elif ch in ("+", "="):
                    player.volume_up(5)
                elif ch in ("-", "_"):
                    player.volume_down(5)
                elif ch in ("l", "a"):
                    if cur:
                        api.like_track(cur)
                        sys.stdout.write(f"\n❤️ Liked '{cur.title}'!\n")
                elif ch == "d":
                    if cur:
                        api.dislike_track(cur)
                        sys.stdout.write(f"\n👎 Disliked '{cur.title}'!\n")
                        player.next_track()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        cfg.volume = player.state.volume
        cfg.save()
        player.shutdown()
        print("\nPlayback stopped.")


def cmd_auth(cfg: Config, api: YMusicAPI, token: str | None = None) -> None:
    """Authenticate with Yandex Music via CLI."""
    if token:
        if api.login(token):
            print(f"✓ Successfully authenticated as: {api.username}")
            return
        else:
            print("✗ Authentication failed. Please check the token.")
            sys.exit(1)

    print("── YMusic CLI Authentication ──\n")
    print("Method 1 (Fastest):")
    print("  1. Open this URL in your browser:")
    print("     https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d")
    print("  2. Authorize and copy the access_token from the address bar.\n")
    tok = input("Paste your token here (or press Enter for Device Code flow): ").strip()
    if tok:
        if api.login(tok):
            print(f"✓ Logged in as: {api.username}")
            return
        else:
            print("✗ Login failed.")
            sys.exit(1)

    print("\nMethod 2: Device Code Flow")
    print("Requesting device code from Yandex...")

    def on_code(code):
        url = getattr(code, "verification_url", "https://ya.ru/device")
        user_code = getattr(code, "user_code", "???")
        print(f"\n  Go to:  {url}")
        print(f"  Code:   {user_code}\n")
        print("Waiting for confirmation in browser...")

    t = api.device_auth(on_code_callback=on_code)
    if t:
        print(f"✓ Successfully authenticated as: {api.username}!")
    else:
        print("✗ Device authentication timed out or failed.")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ymusic",
        description="YMusic CLI — True Linux console player for Yandex Music (cmus-style TUI + CLI).",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ymusic tui
    subparsers.add_parser("tui", help="Launch cmus-style TUI player (default when no args given)")

    # ymusic play
    p_play = subparsers.add_parser("play", help="Search and play a track in terminal")
    p_play.add_argument("query", help="Track, artist, or album to search and play")

    # ymusic wave
    subparsers.add_parser("wave", help="Stream 'Моя Волна' (My Wave) in terminal")

    # ymusic fzf
    subparsers.add_parser("fzf", help="Interactive track search with fzf and playback")

    # ymusic liked
    p_liked = subparsers.add_parser("liked", help="List liked tracks (tab-separated for unix pipelines)")
    p_liked.add_argument("-n", "--limit", type=int, default=100, help="Max tracks to list (default 100)")

    # ymusic status
    subparsers.add_parser("status", help="Show account and subscription status")

    # ymusic auth
    p_auth = subparsers.add_parser("auth", help="Authenticate with Yandex Music")
    p_auth.add_argument("--token", help="Provide OAuth token directly")

    return parser

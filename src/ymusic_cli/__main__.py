"""Entry point for YMusic CLI."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from ymusic_cli.config import Config
from ymusic_cli.api import YMusicAPI
from ymusic_cli.player import check_mpv_available
from ymusic_cli.cli import (
    build_parser,
    cmd_status,
    cmd_liked,
    cmd_fzf,
    cmd_play,
    cmd_wave,
    cmd_auth,
)


def main() -> None:
    """Main CLI / TUI dispatcher."""
    # File-based logging so it doesn't pollute stdout / terminal
    log_dir = Path.home() / ".cache" / "ymusic-cli"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "ymusic.log"),
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()

    cfg = Config.load()
    api = YMusicAPI(cfg)

    # Route subcommands
    if args.command == "status":
        cmd_status(cfg, api)
    elif args.command == "liked":
        cmd_liked(cfg, api, limit=args.limit)
    elif args.command == "fzf":
        cmd_fzf(cfg, api)
    elif args.command == "play":
        cmd_play(cfg, api, query=args.query)
    elif args.command == "wave":
        cmd_wave(cfg, api)
    elif args.command == "auth":
        cmd_auth(cfg, api, token=getattr(args, "token", None))
    else:
        # Default: launch Cmus-style TUI
        if not check_mpv_available():
            print("❌ Error: mpv is not installed or not in PATH.", file=sys.stderr)
            print("Install it with: sudo pacman -S mpv", file=sys.stderr)
            sys.exit(1)

        from ymusic_cli.tui.app import YMusicApp

        app = YMusicApp(cfg)
        app.run()


if __name__ == "__main__":
    main()

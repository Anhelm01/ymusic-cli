"""Entry point for YMusic CLI."""

from __future__ import annotations

import sys


def main() -> None:
    """Run the YMusic CLI TUI application."""
    from ymusic_cli.config import Config
    from ymusic_cli.tui.app import YMusicApp

    config = Config.load()
    app = YMusicApp(config)
    app.run()


if __name__ == "__main__":
    main()

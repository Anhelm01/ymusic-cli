"""Entry point for YMusic CLI."""

from __future__ import annotations

import logging
import sys


def main() -> None:
    """Run the YMusic CLI TUI application."""
    # Set up logging (file-based, doesn't pollute the TUI)
    from pathlib import Path

    log_dir = Path.home() / ".cache" / "ymusic-cli"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "ymusic.log"),
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    log = logging.getLogger("ymusic_cli")

    # Check mpv availability
    from ymusic_cli.player import check_mpv_available

    if not check_mpv_available():
        print("❌ Error: mpv is not installed or not in PATH.")
        print("Install it with your package manager:")
        print("  Arch/Omarchy: sudo pacman -S mpv")
        print("  Ubuntu/Debian: sudo apt install mpv")
        print("  Fedora: sudo dnf install mpv")
        sys.exit(1)

    from ymusic_cli.config import Config
    from ymusic_cli.tui.app import YMusicApp

    config = Config.load()
    log.info("Starting YMusic CLI v%s", "0.1.0")

    app = YMusicApp(config)
    app.run()


if __name__ == "__main__":
    main()

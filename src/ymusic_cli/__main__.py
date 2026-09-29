"""Entry point for YMusic CLI."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main() -> None:
    """Main entry point."""
    # File-based logging
    log_dir = Path.home() / ".cache" / "ymusic-cli"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "ymusic.log"),
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    from ymusic_cli.config import Config
    from ymusic_cli.api import YMusicAPI
    from ymusic_cli.cli import YMusicShell

    # Handle 'ymusic auth' and 'ymusic auth --token X' specially
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        cfg = Config.load()
        api = YMusicAPI(cfg)
        token = None
        if len(sys.argv) > 2:
            token = sys.argv[2]
        _do_auth(cfg, api, token)
        return

    cfg = Config.load()
    api = YMusicAPI(cfg)
    shell = YMusicShell(cfg, api)
    shell.start()


def _do_auth(cfg, api, token: str | None = None) -> None:
    """Handle authentication from CLI."""
    from rich.console import Console
    console = Console()

    if token:
        if api.login(token):
            console.print(f"[green]✓ Authenticated as: {api.username}[/green]")
            return
        else:
            console.print("[red]✗ Token invalid.[/red]")
            sys.exit(1)

    console.print("[bold]ymusic auth[/bold]")
    console.print()
    console.print("Open this URL and authorize:")
    console.print("[cyan]https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d[/cyan]")
    console.print()
    tok = input("Paste token: ").strip()
    if not tok:
        console.print("[red]No token provided.[/red]")
        sys.exit(1)
    if api.login(tok):
        console.print(f"[green]✓ Authenticated as: {api.username}[/green]")
    else:
        console.print("[red]✗ Login failed.[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Entry point for YMusic CLI."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def print_cli_help() -> None:
    """Print command-line usage information."""
    from rich.console import Console

    console = Console()
    console.print("[bold]ymusic[/bold] — Console player for Yandex Music with ASCII visuals & tabs\n")
    console.print("[bold cyan]Usage:[/bold cyan]")
    console.print("  ymusic                     Launch interactive player shell")
    console.print("  ymusic wave                Launch and start My Wave radio immediately")
    console.print("  ymusic liked               Launch and browse liked tracks")
    console.print("  ymusic play <query/number> Launch and play track or search query")
    console.print("  ymusic search <query>      Launch and search for tracks")
    console.print("  ymusic vis                 Launch interactive ASCII spectrum visualizer")
    console.print("  ymusic status              Show account info and exit")
    console.print("  ymusic auth [token]        Authenticate with Yandex Music account")
    console.print("  ymusic --help, -h          Show this help message\n")


def main() -> None:
    """Main entry point."""
    log_dir = Path.home() / ".cache" / "ymusic-cli"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "ymusic.log"),
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    from rich.console import Console
    from ymusic_cli.config import Config
    from ymusic_cli.api import YMusicAPI
    from ymusic_cli.cli import YMusicShell

    args = sys.argv[1:]

    # Handle --help / -h
    if args and args[0] in ("--help", "-h", "help"):
        print_cli_help()
        return

    # Handle 'ymusic auth' and 'ymusic auth <token>'
    if args and args[0] == "auth":
        cfg = Config.load()
        api = YMusicAPI(cfg)
        token = args[1] if len(args) > 1 else None
        _do_auth(cfg, api, token)
        return

    # Handle 'ymusic status'
    if args and args[0] == "status":
        cfg = Config.load()
        api = YMusicAPI(cfg)
        console = Console()
        if not api.login():
            console.print("[red]Not authenticated. Run: ymusic auth[/red]")
            sys.exit(1)
        plus = "[green]Active ✓[/green]" if api.has_plus else "[red]Inactive ✗[/red]"
        console.print(f"User:   [bold]{api.username}[/bold]")
        console.print(f"Plus:   {plus}")
        console.print(f"Volume: {cfg.volume}%")
        return

    # Determine initial command if any
    initial_cmd = None
    if args:
        subcmd = args[0].lower()
        if subcmd in ("wave", "liked", "playlists", "vis", "lyrics"):
            initial_cmd = subcmd
        elif subcmd in ("play", "search") and len(args) > 1:
            initial_cmd = f"{subcmd} {' '.join(args[1:])}"
        elif subcmd == "play":
            initial_cmd = "play"
        else:
            initial_cmd = " ".join(args)

    cfg = Config.load()
    api = YMusicAPI(cfg)
    shell = YMusicShell(cfg, api)
    shell.start(initial_command=initial_cmd)


def _do_auth(cfg: Config, api: YMusicAPI, token: str | None = None) -> None:
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

    console.print("[bold]ymusic auth[/bold]\n")
    console.print("Open this URL in your browser and authorize:")
    console.print(
        "[cyan]https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d[/cyan]\n"
    )
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

# YMusic CLI

<p align="left">
  <strong>English</strong> | <strong><a href="README_RU.md">Русский</a></strong>
</p>

**YMusic CLI** is a modern, fast, and ultra-lightweight (~6.5 MB) console music player for **Yandex Music** featuring a responsive mini-TUI interface, dynamic track bar, 3-track sliding window view, and automated browser authentication.

Cross-platform: first-class support for **Linux** and **Windows** (10 / 11).

---

## Key Features

- **Instant Number Navigation (1–4)**:
  - `1` / `wave` / `волна`: **My Wave** — infinite personalized algorithmic radio stream with automatic background track prefetching.
  - `2` / `liked` / `лайки`: **Favorites** — your personal library of liked tracks.
  - `3` / `playlists` / `плейлисты`: **Playlists** — browse your personal and editorial playlists (`3 <N>` to select).
  - `4` / `search` / `поиск`: **Search** — instant search across tracks, artists, and albums (`4 <query>`).
- **Responsive Adaptive Mini-TUI**:
  - Compact 2-line header adapting dynamically to terminal width (from minimal icon indicators to detailed labels).
  - Clean auto-clearing screen mechanism after each command execution — zero clutter or cloned headers.
- **Bilingual & Single-Key Controls**:
  - Full support for English and Russian keyboard layouts without switching (`c`/`с` for pause, `n`/`т` for next, `p`/`з` for previous, `l`/`д` for like, `d`/`в` for dislike).
- **Intelligent 3-Track Sliding Window Queue**:
  - `<< Previous`
  - `>> Playing`
  - `>> Next`
  - Pass the `all` flag (e.g. `liked all`, `2 all`) to inspect the complete playlist list.
- **Ultra-Compact Standalone Binary**:
  - Optimized to **~6.5 MB** on Linux with zero Python dependencies required.
- **Zero-Friction Device Auth (`auth`)**:
  - Hassle-free login powered by **Device Auth**: the player automatically generates a code, copies it to your clipboard, and launches `https://ya.ru/device` in your default browser.
  - Tokens and settings are stored strictly in the operating system's protected user profile directory with restrictive permissions and are never bundled into release artifacts or repositories.

---

## Requirements

1. **Audio Backend (mpv / libmpv)**: YMusic CLI uses `libmpv` for high-quality, low-latency audio playback with minimal resource usage.
2. *(Optional, only when running from source)*: Python **3.10+** and package manager (`uv` or `pip`).

---

## Step-by-Step Guide for Linux

### Step 1. Install System Audio Backend (mpv)

Install `mpv` and development libraries using your distribution's package manager:

- **Ubuntu / Debian / Linux Mint**:
  ```bash
  sudo apt update
  sudo apt install -y mpv libmpv-dev
  ```
- **Arch Linux / Manjaro**:
  ```bash
  sudo pacman -S mpv
  ```
- **Fedora / RHEL**:
  ```bash
  sudo dnf install -y mpv mpv-libs-devel
  ```
- **openSUSE**:
  ```bash
  sudo zypper install mpv libmpv2
  ```

---

### Step 2. Launching on Linux

#### Option A: Run Pre-built Standalone Binary (No Python required)

1. Download the release package (`ymusic-v0.3.0-linux-x64.tar.gz`) from GitHub Releases:
   ```bash
   tar -xzf ymusic-v0.3.0-linux-x64.tar.gz
   cd ymusic-v0.3.0-linux-x64
   ```
2. Grant execution permissions:
   ```bash
   chmod +x ymusic
   ```
3. *(Recommended)* Install into your user binary path to run `ymusic` anywhere:
   ```bash
   mkdir -p ~/.local/bin
   cp ymusic ~/.local/bin/
   ```
   *(Ensure `~/.local/bin` is in your `$PATH`)*.

4. Start the player:
   ```bash
   ymusic
   ```

#### Option B: Run from Source (via uv or venv)

- **Using uv** (recommended):
  ```bash
  # Install dependencies into virtual environment:
  uv sync

  # Start the player:
  uv run ymusic
  ```

- **Using standard Python venv and pip**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  python3 -m ymusic_cli
  ```

---

## Step-by-Step Guide for Windows

### Step 1. Install Audio Backend (mpv)

The player requires `libmpv` / `mpv.exe` in your system `PATH`:

- **Method 1 (via winget — built into Windows 10/11)**:
  In PowerShell:
  ```powershell
  winget install mpv.net
  # or
  winget install mpv.mpv
  ```
- **Method 2 (via Scoop)**:
  ```powershell
  scoop install mpv
  ```
- **Method 3 (via Chocolatey)**:
  ```powershell
  choco install mpv
  ```
- **Method 4 (Manual download)**:
  1. Download the mpv package from [SourceForge / GitHub](https://sourceforge.net/projects/mpv-player-windows/files/).
  2. Extract `libmpv-2.dll` (or `mpv.exe`) into the same directory as `ymusic.exe`, or add its folder to your system `PATH`.

> [!TIP]
> **Recommended Windows Terminal**: Use the modern **Windows Terminal** (available free from the Microsoft Store). It provides full ANSI 24-bit color support, UTF-8 rendering, and compatibility with Nerd Fonts.

---

### Step 2. Launching on Windows

#### Option A: Run Pre-built Standalone `ymusic.exe`

1. Download and extract `ymusic-v0.3.0-windows-x64.zip`.
2. Open **Windows Terminal** (PowerShell or Command Prompt).
3. Run the executable:
   ```powershell
   .\ymusic.exe
   ```
   *(Or double-click `run.bat` included in the zip package)*.

#### Option B: Run from Source on Windows

```powershell
# Create and activate virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Run interactive CLI
python -m ymusic_cli
```

---

## Authentication (Device Auth)

On first run, the player automatically prompts you to log into your Yandex account:

1. Run the auth command:
   ```bash
   ymusic auth
   ```
2. The player generates a one-time device code (e.g. `ABCD-1234`), **automatically copies it to your clipboard**, and opens the verification page:
   ```
   https://ya.ru/device
   ```
3. In your browser, press **Ctrl+V** (Paste) and authorize the device.
4. The CLI automatically intercepts the token, stores it securely in your configuration, and displays your account username along with Yandex Plus subscription status.

### Alternative Authentication Methods:
If you already possess an OAuth token:
```bash
ymusic auth <YOUR_TOKEN>
```
Or pass it via environment variable:
- **Linux**: `export YANDEX_MUSIC_TOKEN="your_token"`
- **Windows (PowerShell)**: `$env:YANDEX_MUSIC_TOKEN="your_token"`

---

## Commands & Hotkeys Reference

### Terminal Quick Launch Commands:
| Command | Description |
|:---|:---|
| `ymusic` | Start interactive terminal shell |
| `ymusic 1` or `ymusic wave` | Launch "My Wave" immediately on startup |
| `ymusic 2` or `ymusic liked` | Open favorites / liked tracks |
| `ymusic play <query>` | Search and immediately play first matching track |
| `ymusic search <query>` | Search library for tracks, artists, and albums |
| `ymusic status` | Check account info and Plus subscription status |
| `ymusic update` / `auth` | Force re-authentication via browser |
| `ymusic --version` / `-v` | Display version information |
| `ymusic --help` / `-h` | Show CLI flags and options help |

### Interactive Shell Controls:

#### Categories (Single digit input):
- `1` / `wave` / `волна` — **My Wave** (infinite personalized radio stream)
- `2` / `liked` / `лайки` — **Liked** (compact 3-track sliding window of favorites)
- `2 all` — Display full list of liked tracks
- `3` / `playlists` / `плейлисты` — **Playlists** (browse personal and editorial playlists)
- `3 <number>` — Load and start playlist number N
- `4 <query>` / `поиск <query>` — **Search** Yandex Music

#### Playback Hotkeys (Works in English and Russian layouts):
- `c` / `pause` / `с` — Pause or resume playback
- `n` / `next` / `т` — Skip to next track
- `p` / `prev` / `з` — Go back to previous track
- `l` / `like` / `д` — Like current track
- `d` / `dislike` / `в` — Dislike current track
- `now` — Display compact Now Playing info card
- `seek +/-N` — Seek by N seconds (e.g. `seek +30` or `seek -15`)
- `vol <0-100>` — Set volume percentage (e.g. `vol 80`)
- `vol +/-N` — Adjust volume by delta (e.g. `vol +5` or `vol -10`)
- `repeat` — Cycle repeat mode: `off` -> `all` -> `one`
- `shuffle` — Shuffle current playlist
- `stop` — Stop playback completely

#### Shell System Commands:
- `clear` / `cls` — Clear terminal screen
- `status` — Show user profile & Yandex Plus status
- `update` / `auth` — Force browser authentication update
- `help` — Print command reference
- `q` / `quit` / `exit` / `выход` — Exit the player

---

## Building Standalone Executables

You can compile a standalone, single-file binary using `build.py`:

```bash
# Compile and create release bundles:
python build.py --package
```

### Build Artifacts:
- **Linux**: `dist/linux/ymusic` (single ELF binary, ~6.5 MB) and `releases/ymusic-v0.3.0-linux-x64.tar.gz`.
- **Windows**: `dist/windows/ymusic.exe` and `releases/ymusic-v0.3.0-windows-x64.zip`.

> **Build Security Guarantee:**
> Before packaging, `build.py` validates the workspace and blocks any token files, `config.json`, or private user credentials from being included in the resulting binaries or archives.

---

## Configuration & Log Locations

Configuration is stored automatically in the operating system's protected user directory:
- **Linux**: `~/.config/ymusic-cli/config.json` (chmod `0600`)
- **Windows**: `%APPDATA%\ymusic-cli\config.json`
- **Logs**: `~/.cache/ymusic-cli/ymusic.log` (Linux) or `%LOCALAPPDATA%\ymusic-cli\ymusic.log` (Windows).

---

## Troubleshooting

### 1. `Cannot find libmpv` or `mpv is not installed`
- **Linux**: Verify that `libmpv1` or `libmpv2` / `libmpv-dev` package is installed (`sudo apt install libmpv-dev` or `sudo pacman -S mpv`).
- **Windows**: Verify that `libmpv-2.dll` is in your `PATH` or placed directly in the same folder as `ymusic.exe`.

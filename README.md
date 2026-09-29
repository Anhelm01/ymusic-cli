# YMusic CLI

<p align="left">
  <strong>English</strong> | <strong><a href="README_RU.md">Русский</a></strong>
</p>

**YMusic CLI** is a modern, fast, and lightweight console music player for **Yandex Music** featuring an ASCII interface, real-time dynamic spectrum visualizer, retro cassette animation, sliding window queue, and automated browser authentication.

Cross-platform: first-class support for **Linux** and **Windows** (10 / 11).

---

## Key Features

- **Instant Number Navigation (1–6)**:
  - `1` / `wave`: **My Wave** — infinite personalized algorithmic radio stream with automatic background track prefetching.
  - `2` / `liked`: **Favorites** — your personal library of liked tracks.
  - `3` / `playlists`: **Playlists** — browse your personal and editorial playlists (`3 <N>` to select).
  - `4` / `search`: **Search** — instant search across tracks, artists, and albums (`4 <query>`).
  - `5` / `queue`: **Queue** — compact sliding window view of the active playlist.
  - `6` / `lyrics`: **Lyrics** — view synchronized or plain text lyrics for the currently playing track.
- **Intelligent 3-Track Sliding Window Queue**:
  - `<< Previous`
  - `>> Playing`
  - `>> Next`
  - To inspect the complete playlist list at any time, pass the `all` flag (e.g. `liked all`, `5 all`).
- **Interactive Spectrum Visualizer (`vis`)**:
  - Fullscreen terminal ASCII spectrum analyzer with column gravity and decay physics.
  - Real-time playback control hotkeys directly inside the visualizer without leaving the view.
- **Retro Cassette Track Card (`now`)**:
  - Animated retro cassette with spinning reels, precise playback timeline, and track metadata.
- **Zero-Friction Device Auth (`auth`)**:
  - Hassle-free login powered by **Device Auth**: the player automatically generates a code, copies it to your clipboard, and launches `https://ya.ru/device` in your default browser. No manual token inspection in DevTools!
  - Tokens and settings are stored strictly in the operating system's protected user profile directory with restrictive permissions and are never bundled into release artifacts or repositories.
- **Clean Terminal UI**:
  - Automatic screen management on section switching with zero log spam.

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

1. Download the release package (`ymusic-v0.2.0-linux-x64.tar.gz`) from GitHub Releases or locate `dist/linux/ymusic`:
   ```bash
   tar -xzf ymusic-v0.2.0-linux-x64.tar.gz
   cd ymusic-v0.2.0-linux-x64
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
> **Recommended Windows Terminal**: Use the modern **Windows Terminal** (available free from the Microsoft Store). It provides full ANSI 24-bit color support, UTF-8 rendering, and compatibility with Nerd Fonts / Cascadia Code for crisp cassette and equalizer art.

---

### Step 2. Launching on Windows

#### Option A: Run Pre-built Standalone `ymusic.exe`

1. Download and extract `ymusic-v0.2.0-windows-x64.zip`.
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
| `ymusic vis` | Launch directly into interactive spectrum visualizer |
| `ymusic status` | Check account info and Plus subscription status |
| `ymusic update` / `auth` | Force re-authentication via browser |
| `ymusic --version` / `-v` | Display version information |
| `ymusic --help` / `-h` | Show CLI flags and options help |

### Interactive Shell Controls:

#### Categories (Single digit input):
- `1` — **My Wave** (infinite personalized radio stream)
- `2` — **Liked** (compact 3-track sliding window of favorites)
- `2 all` — Display full list of liked tracks
- `3` — **Playlists** (browse personal and editorial playlists)
- `3 <number>` — Load and start playlist number N
- `4 <query>` — **Search** Yandex Music
- `5` — **Queue** (current 3 tracks: Previous / Playing / Next)
- `5 all` — Display entire active playback queue
- `6` — **Lyrics** (synchronized or plain text lyrics)

#### Visual Screens:
- `vis` — Fullscreen ASCII spectrum analyzer with column decay physics.
  - **Visualizer Hotkeys**:
    - `Space` — Pause / Resume playback
    - `n` / `p` — Next / Previous track
    - `+` / `-` — Volume up / down
    - `l` — Toggle Like on current track
    - `s` — Shuffle queue
    - `q` or `Esc` — Exit visualizer back to shell
- `now` — Now Playing card with animated cassette and audio timeline.

#### Playback Commands:
- `play <number>` — Play track by index from current list
- `pause` — Pause or resume playback
- `stop` — Stop playback completely
- `n` / `next` — Skip to next track (in My Wave, streams infinitely)
- `p` / `prev` — Go back to previous track
- `seek +/-N` — Seek by N seconds (e.g. `seek +30` or `seek -15`)
- `vol <0-100>` — Set volume percentage (e.g. `vol 80`)
- `vol +/-N` — Adjust volume by delta (e.g. `vol +5` or `vol -10`)
- `repeat` — Cycle repeat mode: `off` -> `all` -> `one`
- `shuffle` — Shuffle current queue
- `like` / `dislike` — Rate track: Like [+] or Dislike [-]

#### Shell System Commands:
- `clear` / `cls` — Clear terminal screen
- `status` — Show user profile & Yandex Plus status
- `update` / `auth` — Force browser authentication update
- `help` — Print command reference
- `q` / `quit` / `exit` — Exit the player

---

## Building Standalone Executables

You can compile a standalone, single-file binary for your platform using `build.py`:

```bash
# 1. Install build requirements
pip install -r requirements-dev.txt

# 2. Run compilation script
python build.py
```

### Build Artifacts:
- **Linux**: `dist/linux/ymusic` (single ELF binary) and `releases/ymusic-v0.2.0-linux-x64.tar.gz`.
- **Windows**: `dist/windows/ymusic.exe` (single PE32+ executable) and `releases/ymusic-v0.2.0-windows-x64.zip`.

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
- **Linux**: Verify that `libmpv1` or `libmpv2` / `libmpv-dev` package is installed.
- **Windows**: Verify that `libmpv-2.dll` is in your `PATH` or placed directly in the same folder as `ymusic.exe`.

### 2. Garbled characters or question marks on Windows
- Standard `cmd.exe` lacks modern unicode support. Launch **Windows Terminal**.
- In the console, execute: `chcp 65001` (switch active code page to UTF-8).
- Ensure your terminal uses a font with full box-drawing glyphs (e.g. *Cascadia Code*, *JetBrains Mono*, *Fira Code*).

### 3. Linux permission error: `Permission denied: ./ymusic`
Mark the executable file as executable:
```bash
chmod +x ./dist/linux/ymusic
```

### 4. No sound on Linux (PulseAudio / PipeWire)
Verify that `mpv` can play audio on your system:
```bash
mpv --ao=pulse /path/to/sample.mp3
```
If using PipeWire, ensure `pipewire-pulse` is active.

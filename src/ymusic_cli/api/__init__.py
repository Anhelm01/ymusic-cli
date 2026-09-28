"""Yandex Music API wrapper layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from yandex_music import Client, Track, Playlist, Artist, Album

from ymusic_cli.config import Config


@dataclass
class TrackInfo:
    """Simplified track representation for the TUI."""

    id: int | str
    title: str
    artists: str
    album: str
    duration_ms: int
    cover_uri: str | None = None
    _raw: Track | None = field(default=None, repr=False)

    @classmethod
    def from_ym_track(cls, track: Track) -> TrackInfo:
        """Build TrackInfo from a yandex_music.Track object."""
        artists = ", ".join(a.name for a in (track.artists or []))
        album_title = ""
        cover = None
        if track.albums:
            album_title = track.albums[0].title or ""
            if track.albums[0].cover_uri:
                cover = "https://" + track.albums[0].cover_uri.replace("%%", "200x200")
        if not cover and track.cover_uri:
            cover = "https://" + track.cover_uri.replace("%%", "200x200")
        return cls(
            id=track.id,
            title=track.title or "Unknown",
            artists=artists or "Unknown Artist",
            album=album_title,
            duration_ms=track.duration_ms or 0,
            cover_uri=cover,
            _raw=track,
        )

    @property
    def duration_str(self) -> str:
        """Format duration as M:SS."""
        total_sec = self.duration_ms // 1000
        minutes = total_sec // 60
        seconds = total_sec % 60
        return f"{minutes}:{seconds:02d}"


class RadioSession:
    """Manages a Yandex Music rotor (radio/wave) session with feedback loop."""

    def __init__(self, client: Client, seeds: list[str] | None = None) -> None:
        self._client = client
        self._seeds = seeds or ["user:onyourwave"]
        self._session_id: str | None = None
        self._batch_id: str | None = None
        self._sequence: list = []
        self._played_ids: list[str] = []
        self._current_track_id: str | None = None

    def start(self) -> list[TrackInfo]:
        """Start a new radio session and return initial tracks."""
        session = self._client.rotor_session_new(self._seeds)
        self._session_id = session.radio_session_id
        self._batch_id = session.batch_id
        self._sequence = list(session.sequence) if session.sequence else []
        # Notify radio started
        self._client.rotor_session_feedback_radio_started(
            self._session_id, self._batch_id
        )
        return self._extract_tracks()

    def get_more_tracks(self) -> list[TrackInfo]:
        """Fetch next batch of tracks from the radio."""
        if not self._session_id:
            return self.start()
        more = self._client.rotor_session_tracks(
            self._session_id, queue=self._played_ids
        )
        self._sequence = list(more.sequence) if more.sequence else []
        self._batch_id = more.batch_id
        return self._extract_tracks()

    def _extract_tracks(self) -> list[TrackInfo]:
        result = []
        for item in self._sequence:
            if item.track:
                result.append(TrackInfo.from_ym_track(item.track))
        return result

    def feedback_track_started(self, track: TrackInfo) -> None:
        """Send feedback that a track started playing."""
        if not self._session_id:
            return
        self._current_track_id = str(track.id)
        try:
            self._client.rotor_session_feedback_track_started(
                self._session_id, str(track.id), self._batch_id
            )
        except Exception:
            pass

    def feedback_track_finished(self, track: TrackInfo, duration_sec: float) -> None:
        """Send feedback that a track finished playing."""
        if not self._session_id:
            return
        self._played_ids.append(str(track.id))
        try:
            self._client.rotor_session_feedback_track_finished(
                self._session_id, str(track.id), duration_sec, self._batch_id
            )
        except Exception:
            pass

    def feedback_skip(self, track: TrackInfo, played_sec: float) -> None:
        """Send feedback that a track was skipped."""
        if not self._session_id:
            return
        self._played_ids.append(str(track.id))
        try:
            self._client.rotor_session_feedback_skip(
                self._session_id, str(track.id), played_sec, self._batch_id
            )
        except Exception:
            pass


class YMusicAPI:
    """High-level wrapper around yandex-music Client."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._client: Client | None = None
        self._radio_session: RadioSession | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            raise RuntimeError("Not authenticated. Call login() first.")
        return self._client

    def login(self, token: str | None = None) -> bool:
        """Authenticate with Yandex Music.  Returns True on success."""
        tok = token or self.config.token
        if not tok:
            return False
        try:
            self._client = Client(tok).init()
            # Persist token on success
            if token and token != self.config.token:
                self.config.token = token
                self.config.save()
            return True
        except Exception:
            self._client = None
            return False

    def device_auth(self, on_code_callback=None) -> str | None:
        """Perform OAuth Device flow.  Returns access_token or None.

        ``on_code_callback`` receives the device code object with
        ``.verification_url`` and ``.user_code`` attributes.
        """
        try:
            client = Client()
            token_result = client.device_auth(on_code=on_code_callback)
            if token_result and token_result.access_token:
                self.config.token = token_result.access_token
                self.config.save()
                self._client = Client(token_result.access_token).init()
                return token_result.access_token
        except Exception:
            pass
        return None

    @property
    def is_logged_in(self) -> bool:
        return self._client is not None

    @property
    def username(self) -> str:
        if self._client and self._client.me and self._client.me.account:
            name = self._client.me.account.full_name or self._client.me.account.login
            return name or "user"
        return "user"

    @property
    def has_plus(self) -> bool:
        """Check if the user has an active Yandex Plus subscription."""
        try:
            if self._client and self._client.me and self._client.me.plus:
                return bool(self._client.me.plus.has_plus)
        except Exception:
            pass
        return False

    # ── Library ──────────────────────────────────────────────

    def get_liked_tracks(self, limit: int = 50) -> list[TrackInfo]:
        """Fetch user's liked tracks (batch-fetched for efficiency)."""
        likes = self.client.users_likes_tracks()
        if not likes or not likes.tracks:
            return []
        # Batch fetch — much faster than individual fetch_track() calls
        track_ids = [str(t.id) for t in likes.tracks[:limit]]
        tracks = self.client.tracks(track_ids)
        return [TrackInfo.from_ym_track(t) for t in tracks]

    def get_playlists(self) -> list[Playlist]:
        """Get user's playlists."""
        return self.client.users_playlists_list() or []

    def get_playlist_tracks(self, playlist: Playlist, limit: int = 100) -> list[TrackInfo]:
        """Fetch tracks from a specific playlist."""
        uid = self.client.me.account.uid
        full = self.client.users_playlists(playlist.kind, uid)
        if not full or not full.tracks:
            return []
        # Batch fetch for performance
        track_ids = []
        for short in full.tracks[:limit]:
            tid = short.track_id if hasattr(short, "track_id") else short.id
            track_ids.append(str(tid))
        if not track_ids:
            return []
        tracks = self.client.tracks(track_ids)
        return [TrackInfo.from_ym_track(t) for t in tracks]

    def search(self, query: str, limit: int = 20) -> list[TrackInfo]:
        """Search for tracks."""
        result = self.client.search(query, type_="track")
        if not result or not result.tracks or not result.tracks.results:
            return []
        return [TrackInfo.from_ym_track(t) for t in result.tracks.results[:limit]]

    def get_track_url(self, track_info: TrackInfo) -> str | None:
        """Get direct audio stream URL for a track.

        URLs are short-lived (~60s for the XML stage), so always call
        this right before playback starts.
        """
        try:
            track = track_info._raw
            if track is None:
                tracks = self.client.tracks([str(track_info.id)])
                if not tracks:
                    return None
                track = tracks[0]
            # Get download info and pick best quality
            dl_info = track.get_download_info()
            if not dl_info:
                return None
            # Sort by bitrate, prefer higher quality
            dl_info.sort(key=lambda d: d.bitrate_in_kbps, reverse=True)
            # Try to match configured quality
            quality_map = {
                "low": 64,
                "medium": 128,
                "high": 192,
                "lossless": 320,
            }
            target = quality_map.get(self.config.quality, 192)
            # Find best match at or below target
            best = dl_info[0]  # fallback to highest
            for info in dl_info:
                if info.bitrate_in_kbps <= target:
                    best = info
                    break
            return best.get_direct_link()
        except Exception:
            return None

    def like_track(self, track_info: TrackInfo) -> bool:
        """Add a track to liked."""
        try:
            self.client.users_likes_tracks_add(str(track_info.id))
            return True
        except Exception:
            return False

    def unlike_track(self, track_info: TrackInfo) -> bool:
        """Remove a track from liked."""
        try:
            self.client.users_likes_tracks_remove(str(track_info.id))
            return True
        except Exception:
            return False

    def dislike_track(self, track_info: TrackInfo) -> bool:
        """Mark track as 'do not recommend'."""
        try:
            self.client.users_dislikes_tracks_add(str(track_info.id))
            return True
        except Exception:
            return False

    # ── My Wave (Radio) ──────────────────────────────────────

    def start_wave(self, seeds: list[str] | None = None) -> list[TrackInfo]:
        """Start a 'My Wave' radio session and return initial tracks."""
        self._radio_session = RadioSession(self.client, seeds)
        return self._radio_session.start()

    def get_more_wave_tracks(self) -> list[TrackInfo]:
        """Get more tracks from current wave session."""
        if self._radio_session is None:
            return self.start_wave()
        return self._radio_session.get_more_tracks()

    @property
    def radio_session(self) -> RadioSession | None:
        return self._radio_session

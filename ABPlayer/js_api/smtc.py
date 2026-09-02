import os
from datetime import timedelta
from typing import Callable, Optional

from loguru import logger
from winrt.windows.foundation import Uri
from winrt.windows.media import (
    MediaPlaybackStatus,
    MediaPlaybackType,
    SystemMediaTransportControlsButton,
    SystemMediaTransportControlsTimelineProperties,
    interop,
)
from winrt.windows.storage import StorageFile
from winrt.windows.storage.streams import RandomAccessStreamReference

from .js_api import JSApi


class MediaControls:
    def __init__(
        self,
        hwnd,
        on_play: Optional[Callable[[], None]] = None,
        on_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_previous: Optional[Callable[[], None]] = None,
    ):
        self.hwnd = self._normalize_hwnd(hwnd)

        logger.info(f"MediaControls HWND: {hex(self.hwnd)}")

        self.on_play = on_play
        self.on_pause = on_pause
        self.on_next = on_next
        self.on_previous = on_previous

        self._position = 0.0
        self._duration = 0.0

        # Getting SMTC with Windows Media Interop

        self.smtc = interop.get_for_window(self.hwnd)

        logger.info("WinRT SMTC:", self.smtc)
        logger.info("WinRT IsEnabled:", self.smtc.is_enabled)

        self._button_token = None

        self._configure()

    @staticmethod
    def _normalize_hwnd(hwnd) -> int:
        if isinstance(hwnd, int):
            return hwnd

        if hasattr(hwnd, "value"):
            value = hwnd.value

            if value is not None:
                return int(value)

        try:
            return int(hwnd)
        except (TypeError, ValueError):
            raise TypeError(f"Cannot convert HWND to integer: {hwnd!r}")

    def _configure(self):
        logger.info("Configuring SMTC")
        self.smtc.is_enabled = True
        self.smtc.is_play_enabled = True
        self.smtc.is_pause_enabled = True
        self.smtc.is_next_enabled = True
        self.smtc.is_previous_enabled = True

        self._button_token = self.smtc.add_button_pressed(
            self._on_button_pressed
        )

    def _on_button_pressed(self, sender, args):
        button = args.button

        if button == SystemMediaTransportControlsButton.PLAY:
            if self.on_play:
                self.on_play()

        elif button == SystemMediaTransportControlsButton.PAUSE:
            if self.on_pause:
                self.on_pause()

        elif button == SystemMediaTransportControlsButton.NEXT:
            if self.on_next:
                self.on_next()

        elif button == SystemMediaTransportControlsButton.PREVIOUS:
            if self.on_previous:
                self.on_previous()

    @property
    def playback_status(self):
        return self.smtc.playback_status

    @playback_status.setter
    def playback_status(self, value):
        self.smtc.playback_status = value

    def play(self):
        self.smtc.playback_status = MediaPlaybackStatus.PLAYING

    def pause(self):
        self.smtc.playback_status = MediaPlaybackStatus.PAUSED

        self.set_timeline(position=self._position, duration=self._duration)

    def stop(self):
        self.smtc.playback_status = MediaPlaybackStatus.STOPPED

    def close(self):
        self.smtc.playback_status = MediaPlaybackStatus.CLOSED

    @property
    def is_enabled(self):
        return self.smtc.is_enabled

    @is_enabled.setter
    def is_enabled(self, value):
        self.smtc.is_enabled = bool(value)

    @property
    def is_play_enabled(self):
        return self.smtc.is_play_enabled

    @is_play_enabled.setter
    def is_play_enabled(self, value):
        self.smtc.is_play_enabled = bool(value)

    @property
    def is_pause_enabled(self):
        return self.smtc.is_pause_enabled

    @is_pause_enabled.setter
    def is_pause_enabled(self, value):
        self.smtc.is_pause_enabled = bool(value)

    @property
    def is_next_enabled(self):
        return self.smtc.is_next_enabled

    @is_next_enabled.setter
    def is_next_enabled(self, value):
        self.smtc.is_next_enabled = bool(value)

    @property
    def is_previous_enabled(self):
        return self.smtc.is_previous_enabled

    @is_previous_enabled.setter
    def is_previous_enabled(self, value):
        self.smtc.is_previous_enabled = bool(value)

    def update_playback(
        self,
        position: float,
        duration: float,
        playing: bool,
    ):
        self.set_timeline(position=position, duration=duration)

        if playing:
            self.play()
        else:
            self.pause()

    def set_metadata(self, title, artist="", album="", thumbnail=""):
        updater = self.smtc.display_updater

        updater.type = MediaPlaybackType.MUSIC

        updater.music_properties.title = title
        updater.music_properties.artist = artist
        updater.music_properties.album_title = album
        if thumbnail.startswith("http"):
            updater.thumbnail = RandomAccessStreamReference.create_from_uri(
                Uri(thumbnail)
            )
        else:
            updater.thumbnail = RandomAccessStreamReference.create_from_file(
                StorageFile.get_file_from_path_async(
                    os.path.abspath(
                        os.path.join(os.environ["books_folder"], thumbnail)
                    )
                ).get()
            )

        updater.update()

    def set_timeline(
        self, position: float, duration: float, start_time: float = 0.0
    ):
        self._position = position
        self._duration = duration

        properties = SystemMediaTransportControlsTimelineProperties()

        properties.start_time = timedelta(seconds=start_time)
        properties.end_time = timedelta(seconds=duration)
        properties.position = timedelta(seconds=position)

        self.smtc.update_timeline_properties(properties)

    def set_position(
        self,
        position: float,
        duration: Optional[float] = None,
    ):
        if duration is None:
            duration = position

        self.set_timeline(position=position, duration=duration)

    def update(
        self,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        thumbnail: Optional[str] = None,
        position: Optional[float] = None,
        duration: Optional[float] = None,
        playing: Optional[bool] = None,
    ):
        if (
            title is not None
            or artist is not None
            or album is not None
            or thumbnail is not None
        ):
            self.set_metadata(
                title=title,
                artist=artist,
                album=album,
                thumbnail=thumbnail,
            )

        if position is not None and duration is not None:
            self.set_timeline(
                position=position,
                duration=duration,
            )

        if playing is not None:
            if playing:
                self.play()
            else:
                self.pause()

    def close_controls(self):
        if self._button_token is not None:
            try:
                self.smtc.remove_button_pressed(self._button_token)
            except Exception as e:
                logger.info(
                    "Failed to remove ButtonPressed:",
                    e,
                )

            self._button_token = None

        try:
            self.smtc.is_enabled = False
        except Exception:
            pass


class MediaApi(JSApi):
    def __init__(self) -> None:
        self.media = MediaControls(
            self._window.native.Handle.ToInt64(),
            on_play=self._on_play,
            on_pause=self._on_pause,
            on_next=self._on_next,
            on_previous=self._on_previous,
        )

    def _on_play(self):
        self.evaluate_js("""
            (() => {
                if (window.player) {
                    player.play();
                }
            })()
        """)

    def _on_pause(self):
        self.evaluate_js("""
            (() => {
                if (window.player) {
                    player.pause();
                }
            })()
        """)

    def _on_next(self):
        self.evaluate_js("""
            (() => {
                if (window.player && typeof player.next === "function") {
                    player.next();
                }
            })()
        """)

    def _on_previous(self):
        self.evaluate_js("""
            (() => {
                if (window.player && typeof player.previous === "function") {
                    player.previous();
                }
            })()
        """)

    def sync_position(self, position: float, duration: float):
        self.media.sync_position(position=position, duration=duration)

    def set_media_metadata(
        self, title: str, artist: str = "", album: str = "", thumbnail: str = ""
    ):
        self.media.set_metadata(
            title=title,
            artist=artist,
            album=album,
            thumbnail=thumbnail,
        )

    def update_playback(
        self,
        position: float,
        duration: float,
        playing: bool,
    ):
        self.media.update_playback(
            position=position,
            duration=duration,
            playing=playing,
        )

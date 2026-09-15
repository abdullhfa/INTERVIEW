"""
AI Interview Coach - Audio Capture Manager

Captures the interviewer's system/loopback audio. Live coaching deliberately
does not open the candidate microphone.

Provides audio device enumeration and configuration using PyAudioWPatch.
"""

from __future__ import annotations
import logging
import asyncio
import numpy as np
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from app.config import settings

logger = logging.getLogger(__name__)


class AudioChannel(str, Enum):
    INTERVIEWER = "INTERVIEWER"
    CANDIDATE = "CANDIDATE"


@dataclass
class AudioDevice:
    """Represents an audio device."""
    index: int
    name: str
    channels: int
    sample_rate: float
    is_input: bool
    is_loopback: bool = False
    host_api: str = ""
    is_default: bool = False


@dataclass
class AudioConfig:
    """Current audio configuration."""
    mic_device: Optional[AudioDevice] = None
    loopback_device: Optional[AudioDevice] = None
    sample_rate: int = 16000
    channels: int = 1
    chunk_ms: int = 32


class CaptureManager:
    """
    Manages system/loopback capture for live coaching.

    Microphone capture remains available only to callers that explicitly pass
    a callback; the live interview path never does so.
    """

    def __init__(self):
        self._config = AudioConfig(sample_rate=settings.audio_sample_rate)
        self._pyaudio_instance = None
        self._mic_stream = None
        self._loopback_stream = None
        self._keepalive_stream = None
        self._is_capturing = False
        self._capture_owner: Optional[str] = None
        self._mic_callback: Optional[Callable] = None
        self._loopback_callback: Optional[Callable] = None
        self._active_loopback_name: str = ""
        self._active_output_name: str = ""

    @property
    def active_loopback_name(self) -> str:
        return self._active_loopback_name

    @property
    def active_output_name(self) -> str:
        return self._active_output_name

    def _get_pyaudio(self):
        if self._pyaudio_instance is None:
            import pyaudiowpatch as pyaudio
            self._pyaudio_instance = pyaudio.PyAudio()
        return self._pyaudio_instance

    def refresh_devices(self) -> None:
        """Refresh PortAudio's device snapshot after output-device changes."""
        if self._is_capturing or self._pyaudio_instance is None:
            return
        try:
            self._pyaudio_instance.terminate()
        except Exception as exc:
            logger.warning("Failed to refresh audio devices cleanly: %s", exc)
        finally:
            self._pyaudio_instance = None

    def is_loopback_stream_active(self) -> bool:
        """True when the WASAPI loopback stream is open and PortAudio reports active."""
        stream = self._loopback_stream
        if stream is None:
            return False
        try:
            return bool(stream.is_active())
        except Exception:
            return False

    def _resolve_default_wasapi_pair(self) -> tuple[Optional[dict], Optional[dict]]:
        """
        Resolve the current Windows default WASAPI output and its matching loopback.

        Matching follows the official PyAudioWPatch example: find the loopback whose
        name contains the default output device name.
        """
        import pyaudiowpatch as pyaudio

        p = self._get_pyaudio()
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except Exception:
            logger.warning("WASAPI host API is not available")
            return None, None

        try:
            output = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        except Exception as exc:
            logger.warning("Could not read default WASAPI output: %s", exc)
            return None, None

        if output.get("isLoopbackDevice"):
            return None, output

        output_name = str(output.get("name", ""))
        loopback = None
        for candidate in p.get_loopback_device_info_generator():
            candidate_name = str(candidate.get("name", ""))
            if output_name and output_name in candidate_name:
                loopback = candidate
                break
            # Fallback: strip [Loopback] and compare case-insensitively.
            base = candidate_name.removesuffix(" [Loopback]").casefold()
            if base == output_name.casefold():
                loopback = candidate
                break

        if loopback is None:
            # Last resort: first available WASAPI loopback.
            for candidate in p.get_loopback_device_info_generator():
                loopback = candidate
                break

        return output, loopback

    def _resolve_loopback_device_info(self) -> tuple[Optional[dict], Optional[dict]]:
        """
        Resolve output + loopback for capture.

        Explicit user selection is honored when the saved index is still a loopback;
        otherwise fall back to the live Windows default output.
        """
        import pyaudiowpatch as pyaudio

        p = self._get_pyaudio()
        output, default_loopback = self._resolve_default_wasapi_pair()

        selected = self._config.loopback_device
        if selected is not None:
            try:
                info = p.get_device_info_by_index(selected.index)
                if info.get("isLoopbackDevice"):
                    # Prefer matching the selected loopback back to its render device.
                    selected_base = str(info.get("name", "")).removesuffix(" [Loopback]")
                    matched_output = output
                    if output is None or selected_base.casefold() != str(
                        output.get("name", "")
                    ).casefold():
                        for i in range(p.get_device_count()):
                            candidate = p.get_device_info_by_index(i)
                            if (
                                candidate.get("maxOutputChannels", 0) > 0
                                and not candidate.get("isLoopbackDevice", False)
                                and str(candidate.get("name", "")).casefold()
                                == selected_base.casefold()
                            ):
                                matched_output = candidate
                                break
                    return matched_output, info
                logger.warning(
                    "Saved loopback index %s is no longer a loopback device; using Windows default",
                    selected.index,
                )
            except Exception as exc:
                logger.warning(
                    "Saved loopback index %s is stale (%s); using Windows default",
                    selected.index,
                    exc,
                )

        return output, default_loopback

    def _start_wasapi_keepalive(self, output_device: Optional[dict]) -> None:
        """
        Keep a near-silent WASAPI render stream open on the capture output device.

        Windows loopback often delivers zero callbacks until some client is actively
        rendering to that device. An inaudible keepalive prevents false 'no audio'
        stalls before the meeting starts playing.
        """
        if output_device is None:
            return
        try:
            import pyaudiowpatch as pyaudio

            p = self._get_pyaudio()
            channels = max(1, int(output_device.get("maxOutputChannels") or 2))
            rate = int(output_device.get("defaultSampleRate") or 48000)
            frames = 1024
            # Amplitude is far below audible levels but keeps the shared WASAPI
            # engine producing loopback samples.
            amplitude = np.float32(1e-5)

            def keepalive_callback(_in_data, frame_count, _time_info, _status):
                tone = (
                    amplitude
                    * np.sin(
                        2.0
                        * np.pi
                        * 40.0
                        * np.arange(frame_count, dtype=np.float32)
                        / float(rate)
                    )
                ).astype(np.float32)
                if channels > 1:
                    payload = np.column_stack([tone] * channels).reshape(-1)
                else:
                    payload = tone
                return (payload.tobytes(), pyaudio.paContinue)

            self._keepalive_stream = p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=rate,
                frames_per_buffer=frames,
                output=True,
                output_device_index=int(output_device["index"]),
                stream_callback=keepalive_callback,
            )
            self._keepalive_stream.start_stream()
            self._active_output_name = str(output_device.get("name", ""))
            logger.info(
                "WASAPI keepalive started on output device %s (%s)",
                output_device.get("index"),
                self._active_output_name,
            )
        except Exception as exc:
            logger.warning("Could not start WASAPI keepalive: %s", exc)
            self._keepalive_stream = None

    @staticmethod
    def _device_chunk_samples(
        device_sample_rate: int,
        target_sample_rate: int,
        target_chunk_samples: int,
    ) -> int:
        """Return native frames needed to produce one complete target-rate chunk."""
        return max(
            1,
            round(target_chunk_samples * device_sample_rate / target_sample_rate),
        )

    @staticmethod
    def _resample_audio(
        audio: np.ndarray,
        source_sample_rate: int,
        target_sample_rate: int,
    ) -> np.ndarray:
        """Resample a mono chunk while preserving its intended time duration."""
        if source_sample_rate == target_sample_rate:
            return audio.astype(np.float32, copy=False)
        if len(audio) == 0:
            return np.empty(0, dtype=np.float32)

        new_len = max(1, round(len(audio) * target_sample_rate / source_sample_rate))
        resampled = np.asarray(
            np.interp(
                np.linspace(0, len(audio) - 1, new_len),
                np.arange(len(audio)),
                audio,
            ),
            dtype=np.float32,
        )
        return resampled.reshape(-1)

    def list_input_devices(self) -> list[AudioDevice]:
        """List available microphone devices."""
        try:
            import pyaudiowpatch as pyaudio
            p = self._get_pyaudio()
            result = []
            
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev["maxInputChannels"] > 0 and not dev.get("isLoopbackDevice", False):
                    try:
                        host_api = p.get_host_api_info_by_index(dev["hostApi"])["name"]
                    except Exception:
                        host_api = "Unknown"
                        
                    result.append(AudioDevice(
                        index=i,
                        name=dev["name"],
                        channels=dev["maxInputChannels"],
                        sample_rate=dev["defaultSampleRate"],
                        is_input=True,
                        is_loopback=False,
                        host_api=host_api,
                    ))
            return result
        except Exception as e:
            logger.error(f"Failed to list input devices: {e}")
            return []

    def list_output_devices(self) -> list[AudioDevice]:
        """List available output devices (for loopback capture)."""
        try:
            p = self._get_pyaudio()
            result = []
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev["maxOutputChannels"] > 0:
                    try:
                        host_api = p.get_host_api_info_by_index(dev["hostApi"])["name"]
                    except Exception:
                        host_api = "Unknown"
                        
                    result.append(AudioDevice(
                        index=i,
                        name=dev["name"],
                        channels=dev["maxOutputChannels"],
                        sample_rate=dev["defaultSampleRate"],
                        is_input=False,
                        host_api=host_api,
                    ))
            return result
        except Exception as e:
            logger.error(f"Failed to list output devices: {e}")
            return []

    def list_loopback_devices(self) -> list[AudioDevice]:
        """List WASAPI loopback devices for system audio capture."""
        try:
            import pyaudiowpatch as pyaudio
            p = self._get_pyaudio()
            result = []
            default_output_name = ""
            try:
                wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_output = p.get_device_info_by_index(
                    wasapi_info["defaultOutputDevice"]
                )
                default_output_name = str(default_output.get("name", "")).casefold()
            except Exception:
                logger.warning("Could not determine the default WASAPI output device")

            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice", False):
                    loopback_base_name = str(dev["name"]).removesuffix(
                        " [Loopback]"
                    ).casefold()
                    result.append(AudioDevice(
                        index=i,
                        name=dev["name"],
                        channels=dev["maxInputChannels"],
                        sample_rate=dev["defaultSampleRate"],
                        is_input=True,
                        is_loopback=True,
                        host_api="WASAPI",
                        is_default=(
                            bool(default_output_name)
                            and loopback_base_name == default_output_name
                        ),
                    ))

            return result
        except ImportError:
            logger.warning("PyAudioWPatch not available for loopback capture")
            return []
        except Exception as e:
            logger.error(f"Failed to list loopback devices: {e}")
            return []

    def configure(
        self,
        mic_device_index: Optional[int] = None,
        loopback_device_index: Optional[int] = None,
    ):
        """Configure audio devices."""
        if mic_device_index is not None:
            devices = self.list_input_devices()
            selected = next((dev for dev in devices if dev.index == mic_device_index), None)
            if selected is None:
                raise ValueError(f"Microphone device {mic_device_index} is not available")
            self._config.mic_device = selected

        if loopback_device_index is None:
            # Null means follow the current Windows default output. Reset any
            # explicit device retained from an earlier browser session.
            self._config.loopback_device = None
        else:
            devices = self.list_loopback_devices()
            selected = next((dev for dev in devices if dev.index == loopback_device_index), None)
            if selected is None:
                logger.warning(
                    "Loopback device %s is no longer available; using Windows default output",
                    loopback_device_index,
                )
                self._config.loopback_device = None
                return
            self._config.loopback_device = selected

    async def start_capture(
        self,
        on_mic_audio: Optional[Callable[[np.ndarray], None]],
        on_loopback_audio: Callable[[np.ndarray], None],
        *,
        owner_id: str,
    ):
        """
        Start loopback capture and only open a microphone when explicitly asked.
        """
        if self._is_capturing:
            await self.stop_capture()

        # Refresh the PortAudio device snapshot before opening streams so a
        # headphone/speaker switch is reflected in loopback indices.
        self.refresh_devices()

        self._capture_owner = owner_id
        self._mic_callback = on_mic_audio
        self._loopback_callback = on_loopback_audio
        self._is_capturing = True

        if on_mic_audio is not None:
            await self._start_mic_capture()

        # Start loopback capture
        await self._start_loopback_capture()

        if self._loopback_stream is None:
            await self.stop_capture(owner_id=owner_id)
            raise RuntimeError(
                "Interviewer audio could not start. Select the loopback device where the meeting sound is playing."
            )

        logger.info(
            "System loopback audio capture started (loopback=%s output=%s)",
            self._active_loopback_name or "unknown",
            self._active_output_name or "unknown",
        )

    async def _start_mic_capture(self):
        """Start microphone capture using pyaudiowpatch."""
        try:
            import pyaudiowpatch as pyaudio
            p = self._get_pyaudio()
            
            device_idx = self._config.mic_device.index if self._config.mic_device else None
            
            if device_idx is None:
                try:
                    default_device = p.get_default_input_device_info()
                    device_idx = default_device["index"]
                except Exception:
                    pass
            
            if device_idx is None:
                logger.warning("No microphone device found")
                return

            device_info = p.get_device_info_by_index(device_idx)
            target_rate = int(device_info["defaultSampleRate"])
            device_chunk_samples = self._device_chunk_samples(
                target_rate,
                self._config.sample_rate,
                settings.audio_chunk_samples,
            )

            def mic_callback(in_data, frame_count, time_info, status):
                if self._mic_callback and self._is_capturing:
                    audio = np.frombuffer(in_data, dtype=np.float32)
                    
                    if device_info["maxInputChannels"] > 1:
                        audio = audio.reshape(-1, device_info["maxInputChannels"]).mean(axis=1)

                    audio = self._resample_audio(
                        audio,
                        target_rate,
                        self._config.sample_rate,
                    )
                        
                    self._mic_callback(audio)
                return (None, pyaudio.paContinue)

            self._mic_stream = p.open(
                format=pyaudio.paFloat32,
                channels=device_info["maxInputChannels"],
                rate=target_rate,
                frames_per_buffer=device_chunk_samples,
                input=True,
                input_device_index=device_idx,
                stream_callback=mic_callback,
            )
            self._mic_stream.start_stream()
            logger.info(
                "Mic capture started (device=%s native_rate=%s native_chunk=%s target_chunk=%s)",
                device_idx,
                target_rate,
                device_chunk_samples,
                settings.audio_chunk_samples,
            )

        except Exception as e:
            logger.error(f"Failed to start mic capture: {e}")

    async def _start_loopback_capture(self):
        """Start WASAPI loopback capture for system audio."""
        try:
            import pyaudiowpatch as pyaudio

            output_device, loopback_device = self._resolve_loopback_device_info()
            if loopback_device is None:
                logger.warning("No loopback device found")
                return

            device_idx = int(loopback_device["index"])
            device_info = loopback_device
            target_rate = int(device_info["defaultSampleRate"])
            channels = max(1, int(device_info["maxInputChannels"]))
            device_chunk_samples = self._device_chunk_samples(
                target_rate,
                self._config.sample_rate,
                settings.audio_chunk_samples,
            )

            # Start keepalive first so the render graph is already producing
            # samples when loopback capture opens.
            self._start_wasapi_keepalive(output_device)

            def loopback_callback(in_data, frame_count, time_info, status):
                if self._loopback_callback and self._is_capturing:
                    audio = np.frombuffer(in_data, dtype=np.float32)
                    if channels > 1:
                        audio = audio.reshape(-1, channels).mean(axis=1)

                    audio = self._resample_audio(
                        audio,
                        target_rate,
                        self._config.sample_rate,
                    )
                    self._loopback_callback(audio)
                return (None, pyaudio.paContinue)

            p = self._get_pyaudio()
            self._loopback_stream = p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=target_rate,
                frames_per_buffer=device_chunk_samples,
                input=True,
                input_device_index=device_idx,
                stream_callback=loopback_callback,
            )
            self._loopback_stream.start_stream()
            self._active_loopback_name = str(device_info.get("name", ""))
            logger.info(
                "Loopback capture started (device=%s name=%s native_rate=%s native_chunk=%s target_chunk=%s)",
                device_idx,
                self._active_loopback_name,
                target_rate,
                device_chunk_samples,
                settings.audio_chunk_samples,
            )

        except ImportError:
            logger.warning("PyAudioWPatch not installed — loopback disabled")
        except Exception as e:
            logger.error(f"Failed to start loopback capture: {e}")

    async def stop_capture(self, *, owner_id: Optional[str] = None):
        """Stop all audio capture."""
        if owner_id is not None and owner_id != self._capture_owner:
            return
        self._is_capturing = False

        if self._mic_stream:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception as e:
                logger.error(f"Error stopping mic: {e}")
            self._mic_stream = None

        if self._loopback_stream:
            try:
                self._loopback_stream.stop_stream()
                self._loopback_stream.close()
            except Exception as e:
                logger.error(f"Error stopping loopback: {e}")
            self._loopback_stream = None

        if self._keepalive_stream:
            try:
                self._keepalive_stream.stop_stream()
                self._keepalive_stream.close()
            except Exception as e:
                logger.error(f"Error stopping keepalive: {e}")
            self._keepalive_stream = None

        self._active_loopback_name = ""
        self._active_output_name = ""
        self._capture_owner = None
        self._mic_callback = None
        self._loopback_callback = None


capture_manager = CaptureManager()

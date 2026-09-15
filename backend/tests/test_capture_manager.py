import unittest
from unittest.mock import AsyncMock, Mock

import numpy as np

from app.audio.capture_manager import AudioDevice, CaptureManager


class CaptureManagerRegressionTests(unittest.TestCase):
    def test_48khz_device_produces_complete_512_sample_vad_chunk(self):
        native_samples = CaptureManager._device_chunk_samples(48000, 16000, 512)
        native_audio = np.linspace(-0.5, 0.5, native_samples, dtype=np.float32)

        resampled = CaptureManager._resample_audio(native_audio, 48000, 16000)

        self.assertEqual(native_samples, 1536)
        self.assertEqual(len(resampled), 512)
        self.assertEqual(resampled.dtype, np.float32)

    def test_44100hz_device_rounding_still_produces_complete_vad_chunk(self):
        native_samples = CaptureManager._device_chunk_samples(44100, 16000, 512)
        native_audio = np.ones(native_samples, dtype=np.float32)

        resampled = CaptureManager._resample_audio(native_audio, 44100, 16000)

        self.assertEqual(native_samples, 1411)
        self.assertEqual(len(resampled), 512)

class CaptureOwnershipRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_output_selection_clears_stale_explicit_device(self):
        manager = CaptureManager()
        manager._config.loopback_device = AudioDevice(
            index=10,
            name="Old speakers [Loopback]",
            channels=2,
            sample_rate=48000,
            is_input=True,
            is_loopback=True,
        )

        manager.configure(loopback_device_index=None)

        self.assertIsNone(manager._config.loopback_device)

    async def test_missing_saved_loopback_falls_back_to_windows_default(self):
        manager = CaptureManager()
        manager.list_loopback_devices = Mock(return_value=[])

        manager.configure(loopback_device_index=10)

        self.assertIsNone(manager._config.loopback_device)

    async def test_loopback_only_capture_never_opens_microphone(self):
        manager = CaptureManager()
        manager._start_mic_capture = AsyncMock()

        async def start_loopback():
            manager._loopback_stream = object()

        manager._start_loopback_capture = AsyncMock(side_effect=start_loopback)
        await manager.start_capture(
            on_mic_audio=None,
            on_loopback_audio=lambda _audio: None,
            owner_id="loopback-only",
        )

        manager._start_mic_capture.assert_not_awaited()
        manager._start_loopback_capture.assert_awaited_once()

    async def test_stale_owner_cannot_stop_new_capture(self):
        manager = CaptureManager()
        manager._is_capturing = True
        manager._capture_owner = "new-connection"

        await manager.stop_capture(owner_id="old-connection")

        self.assertTrue(manager._is_capturing)
        self.assertEqual(manager._capture_owner, "new-connection")


if __name__ == "__main__":
    unittest.main()

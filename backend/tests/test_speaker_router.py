import unittest

import numpy as np

from app.audio.speaker_router import SpeakerRouter
from app.audio.vad_engine import SpeechState, VADResult


class _FakeVAD:
    def __init__(self, results):
        self._results = iter(results)
        self.is_speaking = False
        self._sample_rate = 16000

    def process_chunk(self, _audio):
        result = next(self._results)
        self.is_speaking = result.state in {
            SpeechState.SPEECH_DETECTED,
            SpeechState.SPEECH_CONTINUING,
        }
        return result

    def reset(self):
        self.is_speaking = False


class SpeakerRouterRegressionTests(unittest.TestCase):
    def test_interviewer_uses_current_states_and_keeps_preroll(self):
        # Disable post-roll so FINALIZED flushes immediately in this unit test.
        router = SpeakerRouter(post_roll_ms=0)
        router._interviewer_vad = _FakeVAD([
            VADResult(SpeechState.SILENCE, 0.8, True),
            VADResult(SpeechState.SPEECH_DETECTED, 0.9, True, 250),
            VADResult(SpeechState.SPEECH_CONTINUING, 0.9, True, 400),
            VADResult(SpeechState.UTTERANCE_FINALIZED, 0.1, False, 500),
        ])
        utterances = []
        router.set_callbacks(
            on_interviewer_utterance=lambda audio, duration: utterances.append((audio, duration))
        )

        chunk = np.ones(512, dtype=np.float32)
        for _ in range(4):
            router.process_interviewer_audio(chunk)

        self.assertEqual(len(utterances), 1)
        self.assertEqual(len(utterances[0][0]), 4 * len(chunk))
        self.assertEqual(utterances[0][1], 500)


if __name__ == "__main__":
    unittest.main()

import unittest

from app.services.transcript_aggregator import TranscriptAggregator


class TranscriptAggregatorRegressionTests(unittest.TestCase):
    def test_duplicate_ignores_case_and_punctuation(self):
        aggregator = TranscriptAggregator(dedup_window_s=20)

        self.assertFalse(aggregator.is_duplicate("What is artificial intelligence?"))
        self.assertTrue(aggregator.is_duplicate("what is artificial intelligence"))


if __name__ == "__main__":
    unittest.main()
